"""The two fronts: MCP tools with the write guard, and Vilikon's ki/ paths with the approval header."""

import json
from pathlib import Path

from conftest import PASSWORD
from starlette.testclient import TestClient

from mobilede_adapter import mcp_server, vilikon
from mobilede_adapter.config import Settings
from mobilede_adapter.guard import Plan, WriteGuard
from mobilede_adapter.texts import CATALOGS, Texts

ROOT = Path(__file__).resolve().parents[1]


def result_data(r) -> dict:
    if getattr(r, "structured_content", None):
        data = r.structured_content
        return data.get("result", data) if isinstance(data, dict) else data
    return json.loads(r.content[0].text)


async def test_guard_confirm_flow():
    done = []

    async def plan() -> Plan:
        async def run() -> str:
            done.append(1)
            return "ok"

        return Plan("Vorschau", run)

    g = WriteGuard("confirm", Texts("de"))
    first = await g.apply("x", {"a": 1}, plan)
    assert first["done"] is False and first["preview"] == "Vorschau" and not done
    wrong_args = await g.apply("x", {"a": 2}, plan, first["confirmation"])
    assert wrong_args["done"] is False and not done
    ok = await g.apply("x", {"a": 1}, plan, first["confirmation"])
    assert ok == {"done": True, "text": "ok"} and done == [1]
    reused = await g.apply("x", {"a": 1}, plan, first["confirmation"])
    assert reused["done"] is False and done == [1]  # a code works once


async def test_guard_off_and_expiry():
    async def plan() -> Plan:
        raise AssertionError("never prepared when writes are off")

    assert (await WriteGuard("off", Texts("de")).apply("x", {}, plan))["done"] is False
    now = [0.0]

    async def plan2() -> Plan:
        async def run() -> str:
            return "ok"

        return Plan("p", run)

    g = WriteGuard("confirm", Texts("de"), clock=lambda: now[0])
    code = (await g.apply("x", {}, plan2))["confirmation"]
    now[0] = 601
    assert (await g.apply("x", {}, plan2, code))["done"] is False


async def test_mcp_tools_and_a_confirmed_write(service, fake):
    server = mcp_server.build(service)
    names = {tool.name for tool in await server.list_tools()}
    assert {"list_ads", "list_leads", "change_price", "create_ad", "set_lead_status", "delete_ad"} <= names
    listed = result_data(await server.call_tool("list_ads", {}))
    assert listed["total"] == 2
    first = result_data(await server.call_tool("change_price", {"ad_id": "207648", "price": 11990}))
    assert first["done"] is False and fake.ads["207648"]["price"]["consumerPriceGross"] == "12990.00"
    done = result_data(
        await server.call_tool(
            "change_price", {"ad_id": "207648", "price": 11990, "confirmation": first["confirmation"]}
        )
    )
    assert done["done"] is True and fake.ads["207648"]["price"]["consumerPriceGross"] == "11990.00"


async def test_mcp_errors_are_sentences(service):
    server = mcp_server.build(service)
    out = result_data(await server.call_tool("get_ad", {"ad_id": "999"}))
    assert "gehört nicht" in out["error"] and PASSWORD not in json.dumps(out)


def ki_client(service) -> TestClient:
    from starlette.applications import Starlette

    return TestClient(Starlette(routes=vilikon.routes(service)))


async def test_ki_reads_channel_events_and_card(service):
    c = ki_client(service)
    leads = c.get("/ki/kanal/leads").json()["leads"]
    assert {x["externe_id"] for x in leads} == {"mobilede-lead-1", "mobilede-lead-2"}
    events = c.get("/ki/ereignisse", params={"seit": "2026-11-10T00:00:00+00:00"}).json()["ereignisse"]
    assert [e["art"] for e in events] == ["buyer_reply"] and events[0]["data"] == {"lead_id": "lead-1"}
    card = c.get("/ki/karte").json()
    assert card["zahl"] == "2" and len(card["zeilen"]) == 2
    assert c.get("/ki/ads", params={"search": "M3"}).json()["found"] == 1
    assert c.get("/ki/ads/999").status_code == 404 and "fehler" in c.get("/ki/ads/999").json()


async def test_ki_writes_need_the_approval_and_run_once(service, fake):
    c = ki_client(service)
    refused = c.put("/ki/ads/207648/price", json={"price": 11990})
    assert refused.status_code == 403 and fake.ads["207648"]["price"]["consumerPriceGross"] == "12990.00"
    head = {"X-Vilikon-Freigabe": "f-1"}
    ok = c.put("/ki/ads/207648/price", json={"price": 11990}, headers=head)
    assert ok.status_code == 200 and "11.990 €" in ok.json()["text"]
    puts = sum(1 for x in fake.calls if x.method == "PUT")
    again = c.put("/ki/ads/207648/price", json={"price": 11990}, headers=head)
    assert again.json() == ok.json() and sum(1 for x in fake.calls if x.method == "PUT") == puts
    bad = c.put("/ki/ads/207648/direct-offer", json={"text": "x", "days": 3}, headers={"X-Vilikon-Freigabe": "f-2"})
    assert bad.status_code == 400 and "Zeichen" in bad.json()["fehler"]


def test_texts_have_the_same_keys():
    assert set(CATALOGS["de"]) == set(CATALOGS["en"])


def test_vilikon_files_match_the_routes(service):
    paths = {r.path for r in vilikon.routes(service)}
    for f in (ROOT / "MODULE.json", ROOT / "vilikon/en/MODULE.json"):
        modul = json.loads(f.read_text())
        assert modul["standard"] == "vilikon.modul/1" and modul["schluessel"] == "mobilede"
        rights = {r["key"] for r in modul["rechte"]}
        for fn in modul["funktionen"]:
            assert "/" + fn["pfad"] in paths, fn["name"]
            assert fn["recht"] in rights and fn["methode"] in ("GET", "POST", "PUT", "PATCH")
            assert bool(fn.get("freigabe")) is (fn["methode"] != "GET" and fn["name"] != "preview_price_rating"), fn[
                "name"
            ]
        assert modul["anschluesse"][0]["standard"] == "vilikon.kanal/1"
    de, en = (json.loads((ROOT / p).read_text()) for p in ("MODULE.json", "vilikon/en/MODULE.json"))
    assert [f["name"] for f in de["funktionen"]] == [f["name"] for f in en["funktionen"]]


def test_mcp_refuses_a_public_address_without_token(tmp_path):
    import pytest

    from mobilede_adapter.app import http_app

    with pytest.raises(SystemExit):
        http_app(Settings(host="0.0.0.0", data_dir=tmp_path))
    assert http_app(Settings(host="0.0.0.0", token="t", data_dir=tmp_path)) is not None
