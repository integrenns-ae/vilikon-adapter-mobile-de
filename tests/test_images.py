"""Photos handed over for a listing and mobile.de's reference data."""

import base64
import io
import os

import pytest
from PIL import Image
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mobilede_adapter import images, vilikon
from mobilede_adapter.images import ImageError, ImageStore, to_jpeg
from mobilede_adapter.service import UserError


def photo(fmt: str = "PNG", size=(800, 600), noise: bool = False, color: str = "silver", **save) -> bytes:
    img = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)) if noise else Image.new("RGB", size, color)
    out = io.BytesIO()
    img.save(out, fmt, **save)
    return out.getvalue()


def test_every_photo_becomes_an_upright_jpg_without_metadata():
    exif = Image.Exif()
    exif[0x0112] = 6  # taken sideways
    exif[0x8825] = {2: (48.0, 12.0, 0.0)}  # a location
    jpg, w, h = to_jpeg(photo("JPEG", (800, 600), exif=exif.tobytes()))
    assert jpg.startswith(b"\xff\xd8\xff") and (w, h) == (600, 800)
    assert not Image.open(io.BytesIO(jpg)).getexif()
    assert to_jpeg(photo("PNG"))[0].startswith(b"\xff\xd8\xff")


def test_heic_from_a_phone():
    pytest.importorskip("pillow_heif")
    jpg, w, h = to_jpeg(photo("HEIF", (640, 480)))
    assert jpg.startswith(b"\xff\xd8\xff") and (w, h) == (640, 480)


def test_a_big_photo_shrinks_below_two_mb():
    big = photo("PNG", (3000, 2400), noise=True)
    assert len(big) > images.MAX_BYTES
    jpg, w, h = to_jpeg(big)
    assert len(jpg) <= images.MAX_BYTES and max(w, h) <= images.MAX_EDGE


def test_no_image_and_too_big_are_refused():
    with pytest.raises(ImageError) as e:
        to_jpeg(b"%PDF-1.7 kein Bild")
    assert e.value.key == "image_unreadable"
    with pytest.raises(ImageError) as e:
        to_jpeg(b"\x00" * (images.MAX_INPUT + 1))
    assert e.value.key == "image_input_too_big"


def test_store_keeps_a_photo_for_a_week(tmp_path):
    store = ImageStore(tmp_path)
    out = store.add(photo())
    assert images.ID.match(out["image"]) and store.get(out["image"]).startswith(b"\xff\xd8")
    assert store.add(photo())["image"] == out["image"]  # the same photo twice is one
    for bad in ("img-0000000000000000", "../approvals", ""):
        with pytest.raises(ImageError):
            store.get(bad)
    old = tmp_path / "images" / f"{out['image']}.jpg"
    os.utime(old, (0, 0))
    store.add(photo(size=(320, 240)))
    assert not old.exists()


async def test_a_staged_photo_goes_into_the_listing_only_with_the_approval(service, fake):
    c = TestClient(Starlette(routes=vilikon.routes(service)))
    r = c.post("/ki/images", files={"datei": ("golf-1.png", photo(), "image/png")})
    assert r.status_code == 200, r.text
    image_id = r.json()["image"]
    assert image_id in r.json()["text"] and not fake.images  # nothing at mobile.de yet
    raw = c.post("/ki/images", content=photo("JPEG", color="navy"), headers={"Content-Type": "image/jpeg"})
    assert raw.status_code == 200 and raw.json()["image"] != image_id
    assert c.post("/ki/images", files={"x": ("leer.jpg", b"", "image/jpeg")}).status_code == 400
    ad = {"vehicleClass": "Car", "make": "MUSTERWAGEN", "model": "M3", "price": {"consumerPriceGross": "18900"}}
    body = {"ad": ad, "images": [{"image": image_id}, raw.json()["image"]]}
    assert c.post("/ki/ads", json=body).status_code == 403  # no approval, no listing
    r = c.post("/ki/ads", json=body, headers={vilikon.APPROVAL: "f-1"})
    assert r.status_code == 200, r.text
    assert len(fake.images) == 2 and all(i.startswith(b"\xff\xd8") for i in fake.images)
    unknown = {"ad": ad, "images": [{"image": "img-0000000000000000"}]}
    r = c.post("/ki/ads", json=unknown, headers={vilikon.APPROVAL: "f-2"})
    assert r.status_code == 400 and "noch einmal" in r.json()["fehler"]


async def test_mcp_stage_image_from_a_path_or_base64(service, tmp_path):
    from mobilede_adapter import mcp_server

    server = mcp_server.build(service)
    f = tmp_path / "foto.png"
    f.write_bytes(photo())
    from test_fronts import result_data

    by_path = result_data(await server.call_tool("stage_image", {"path": str(f)}))
    by_b64 = result_data(await server.call_tool("stage_image", {"base64": base64.b64encode(photo()).decode()}))
    assert by_path["image"] == by_b64["image"]
    assert "error" in result_data(await server.call_tool("stage_image", {"path": str(tmp_path / "fehlt.jpg")}))


async def test_reference_data_with_the_sellers_site(service, fake):
    makes = await service.reference_data("makes", search="beispiel")
    assert makes == {"kind": "makes", "values": [{"name": "BEISPIEL", "description": "Beispiel Motors"}], "more": 0}
    models = await service.reference_data("models", make="musterwagen")
    assert [v["name"] for v in models["values"]] == ["M3", "M5"]
    assert [v["name"] for v in (await service.reference_data("fuels"))["values"]] == ["PETROL", "DIESEL"]
    calls = len(fake.calls)
    await service.reference_data("fuels", search="diesel")
    assert len([x for x in fake.calls[calls:] if x.url.path.startswith("/refdata/")]) == 0  # cached for a day
    for kind, make in (("models", ""), ("../seller-api", ""), ("makes", "VW/../x")):
        with pytest.raises(UserError):
            await service.reference_data(kind, make=make)
    c = TestClient(Starlette(routes=vilikon.routes(service)))
    r = c.get("/ki/reference/models", params={"make": "MUSTERWAGEN", "search": "kombi"})
    assert r.json()["values"] == [{"name": "M5", "description": "M5 Kombi"}]
