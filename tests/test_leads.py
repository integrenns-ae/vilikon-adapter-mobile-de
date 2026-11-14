import json
from datetime import UTC, datetime, timedelta

from mobilede_adapter import leads as lead_lib
from mobilede_adapter.texts import Texts


async def test_sync_follows_the_cursor_and_merges_per_lead(service, fake):
    assert await service.sync_leads() == 3
    store = service.store
    assert store.cursor == "c1" and set(store.leads) == {"lead-1", "lead-2"}
    assert [e["type"] for e in store.leads["lead-1"]["events"]] == ["MessagingLeadSubmitted", "BuyerReplied"]
    assert await service.sync_leads() == 0  # the last page again: nothing twice


async def test_store_survives_a_restart_and_is_private(service, settings):
    await service.sync_leads()
    again = lead_lib.LeadStore(settings.data_dir)
    assert again.cursor == "c1" and len(again.leads) == 2
    assert oct(store_mode := (settings.data_dir / "leads.json").stat().st_mode)[-3:] == "600", store_mode


async def test_old_leads_are_forgotten(service):
    await service.sync_leads()
    service.store.prune(datetime.now(UTC) + timedelta(days=31))
    assert service.store.leads == {}


async def test_vilikon_lead_format(service):
    await service.sync_leads()
    t = Texts("de")
    first = lead_lib.to_vilikon(service.store.leads["lead-1"], t)
    assert first["standard"] == "vilikon.lead/1" and first["externe_id"] == "mobilede-lead-1"
    assert first["kontakt"] == {"name": "Erika Muster", "email": "erika@example.com", "telefon": "+49 301234567"}
    assert first["anliegen"]["betreff"] == "Anfrage zu Musterwagen M3 (Inserat 207648, interne Nummer MF-207648)"
    assert "Probefahrt" in first["anliegen"]["nachricht"] and "Inzahlungnahme" not in first["anliegen"]["nachricht"]
    call = lead_lib.to_vilikon(service.store.leads["lead-2"], t)
    assert call["anliegen"]["betreff"].startswith("Verpasster Anruf") and "telefon" not in call["kontakt"]


async def test_follow_ups_are_only_later_events(service):
    await service.sync_leads()
    ups = service.store.follow_ups(datetime.now(UTC) - timedelta(days=3))
    assert [u["id"] for u in ups] == ["e3"]


async def test_list_leads_for_employees(service):
    result = await service.list_leads()
    lead = next(x for x in result["leads"] if x["lead_id"] == "lead-1")
    assert lead["buyer"]["name"] == "Erika Muster" and lead["events"][1]["text"] == "Passt Samstag?"
    json.dumps(result)  # plain data, ready for any client


async def test_set_lead_status(service, fake):
    plan = await service.plan_set_lead_status("mobilede-lead-1", "sold")
    await plan.run()
    assert fake.lead_status["lead-1"]["newStatus"] == "SOLD"
