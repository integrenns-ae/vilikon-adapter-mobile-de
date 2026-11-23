import base64

import httpx
import pytest
from conftest import JPEG, PASSWORD, SELLER

from mobilede_adapter.config import Settings
from mobilede_adapter.service import Service, UserError


async def test_seller_is_found_and_check_covers_both_apis(service):
    info = await service.seller_info()
    assert info["seller_id"] == SELLER and info["max_images"] == 3
    result = await service.check()
    assert result["ok"] and result["leads"] and "Autohaus Muster GmbH" in result["text"]


async def test_missing_credentials_are_one_sentence(tmp_path):
    s = Service(Settings(data_dir=tmp_path))
    with pytest.raises(UserError, match="Zugangsdaten"):
        await s.seller_info()
    await s.aclose()


async def test_wrong_password_never_shows_the_password(settings, fake, tmp_path):
    bad = Service(
        Settings(user="api-user", password="falsch-" + PASSWORD, data_dir=tmp_path),
        transport=httpx.MockTransport(fake.handler),
    )
    with pytest.raises(Exception) as e:
        await bad.seller_info()
    text = bad.explain(e.value)
    assert "Passwort" in text and PASSWORD not in text and PASSWORD not in repr(bad.settings)
    await bad.aclose()


async def test_list_and_search(service):
    all_ads = await service.list_ads()
    assert all_ads["total"] == 2 and all_ads["ads"][0]["price"] == 12990.0
    hit = await service.list_ads("beispiel b5")
    assert hit["found"] == 1 and hit["ads"][0]["reserved"] is True


async def test_reads(service):
    assert (await service.ad_statistics("207648"))["parkings"] == 5
    assert (await service.price_rating("207648"))["label"] == "GOOD_PRICE"
    assert (await service.get_ad("231922"))["make"] == "Beispiel"


async def test_package_limit_is_explained(service):
    with pytest.raises(Exception) as e:
        await service.rating_overview()
    assert "Gold" in service.explain(e.value)


def test_an_unknown_error_key_is_named(service):
    from mobilede_adapter.client import ApiError

    assert service.explain(ApiError(500, [{"key": "internal"}])) == "mobile.de meldet: internal"


async def test_change_price_sends_the_whole_ad_and_follows_vat(service, fake):
    plan = await service.plan_change_price("207648", 11990)
    assert "12.990 € → 11.990 €" in plan.preview
    assert fake.ads["207648"]["price"]["consumerPriceGross"] == "12990.00"  # nothing changed by preparing
    assert "11.990 €" in await plan.run()
    changed = fake.ads["207648"]
    assert changed["price"]["consumerPriceGross"] == "11990.00" and changed["price"]["consumerPriceNet"] == "10075.63"
    assert changed["make"] == "Musterwagen" and changed["images"]  # the rest of the listing went back unchanged


async def test_invalid_values_are_refused_before_mobile_de(service, fake):
    before = len(fake.calls)
    for call in (
        lambda: service.plan_change_price("207648", 0),
        lambda: service.plan_send_direct_offer("207648", "Ruf an: 0301234567", 3),
        lambda: service.plan_send_direct_offer("207648", "Gutes Angebot", 20),
        lambda: service.plan_set_lead_status("lead-1", "DONE"),
        lambda: service.plan_reply_rating("r1", ""),
        lambda: service.plan_change_price("../sellers", 100),
    ):
        with pytest.raises(Exception) as e:
            await call()
        assert service.explain(e.value)
    assert all(c.method != "PUT" for c in fake.calls[before:])


async def test_reserve_renew_delete(service, fake):
    await (await service.plan_set_reserved("207648", True)).run()
    assert fake.ads["207648"]["reserved"] is True
    await (await service.plan_renew_ad("207648")).run()
    assert fake.calls[-1].url.path.endswith("/vehicle-attribute/renewal-date")
    plan = await service.plan_delete_ad("231922")
    assert "nicht rückgängig" in plan.preview
    await plan.run()
    assert "231922" not in fake.ads


async def test_create_ad_with_images_once(service, fake):
    new = {
        "vehicleClass": "Car",
        "make": "Musterwagen",
        "model": "M1",
        "price": {"consumerPriceGross": "9990.00", "currency": "EUR"},
    }
    images = [{"url": "https://img.example/a.jpg"}, {"base64": base64.b64encode(JPEG).decode()}]
    plan = await service.plan_create_ad(new, images)
    assert "9.990 €" in plan.preview and "2" in plan.preview
    assert "angelegt" in await plan.run()
    again = await (await service.plan_create_ad(new, images)).run()
    assert "schon" in again and len(fake.created) == 1  # the same request id: mobile.de answers 303
    created = next(a for a in fake.ads.values() if a.get("model") == "M1")
    assert [i["ref"] for i in created["images"]] == ["https://img.example/new-1.jpg", "https://img.example/new-2.jpg"]


async def test_images_are_checked(service):
    with pytest.raises(UserError, match="JPG"):
        await service.plan_set_images("207648", [{"base64": base64.b64encode(b"GIF89a....").decode()}])
    with pytest.raises(UserError, match="höchstens 3"):
        await service.plan_set_images("207648", [{"base64": base64.b64encode(JPEG).decode()}] * 4)
    with pytest.raises(UserError, match="url"):
        await service.plan_set_images("207648", [{"url": "http://img.example/a.jpg"}])


async def test_retry_on_server_error(service, fake):
    fake.fail_next = [503]
    assert (await service.list_ads())["total"] == 2


async def test_english_texts(settings, fake):
    s = Service(
        Settings(user="api-user", password=PASSWORD, data_dir=settings.data_dir, lang="en"),
        transport=httpx.MockTransport(fake.handler),
    )
    plan = await s.plan_change_price("207648", 11990)
    assert "€12,990 → €11,990" in plan.preview
    await s.aclose()
