"""Inquiries from the Lead API, kept locally so they can be handed on more than once and merged per lead.

mobile.de offers no push: the adapter polls `GET /lead-api/sellers/{id}/events` with an opaque cursor and keeps
the cursor in DATA_DIR. Several events belong to one lead (first inquiry, the buyer's reply, a call). A lead is
kept for RETENTION_DAYS after it arrived, then forgotten: it lives on in the system it was handed to.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .texts import Texts

RETENTION_DAYS = 30
MAX_PAGES = 20
FOLLOW_UPS = {
    "BuyerReplied": "buyer_reply",
    "MessagingLeadResubmitted": "resubmission",
    "PhoneCallReceived": "missed_call",
}
STATUSES = ("IN_PROGRESS", "SOLD", "NOT_INTERESTED", "SPAM")
_WISHES = {
    "testdrive": "wish_test_drive",
    "tradein": "wish_trade_in",
    "delivery": "wish_delivery",
    "financing": "wish_financing",
    "leasing": "wish_leasing",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_time(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


class LeadStore:
    def __init__(self, data_dir: Path) -> None:
        self.file = Path(data_dir) / "leads.json"
        self.lock = asyncio.Lock()
        self.cursor: str | None = None
        self.leads: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.cursor = raw.get("cursor") or None
        self.leads = raw.get("leads") or {}

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"cursor": self.cursor, "leads": self.leads}, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)  # buyers' contact data
        tmp.replace(self.file)

    def seen(self) -> set[str]:
        return {e["id"] for lead in self.leads.values() for e in lead["events"]}

    def add(self, event: dict, received: str) -> bool:
        """One event from mobile.de. Returns False if it was known already."""
        eid, lid = str(event.get("eventId") or ""), str(event.get("leadId") or "")
        if not eid or not lid or eid in self.seen():
            return False
        lead = self.leads.get(lid)
        first = lead is None
        if first:
            lead = self.leads[lid] = {"id": lid, "received": received, "first": event, "events": []}
        lead["events"].append(
            {
                "id": eid,
                "type": event.get("eventType"),
                "at": event.get("occurredAt"),
                "received": received,
                "first": first,
                **({} if first else {"event": event}),
            }
        )
        return True

    def prune(self, now: datetime) -> None:
        limit = now - timedelta(days=RETENTION_DAYS)
        self.leads = {k: v for k, v in self.leads.items() if (parse_time(v["received"]) or now) >= limit}

    async def sync(self, fetch, now: datetime | None = None) -> int:
        """Fetch what is new since the stored cursor; `fetch(cursor)` returns one page of the events endpoint."""
        async with self.lock:
            now = now or datetime.now(UTC)
            received, new, cursor = now.isoformat(timespec="seconds"), 0, self.cursor
            for _ in range(MAX_PAGES):
                page = await fetch(cursor)
                events = page.get("events") or []
                new += sum(self.add(e, received) for e in events if isinstance(e, dict))
                nxt = page.get("nextCursor")
                if nxt:
                    self.cursor = nxt
                if not nxt or not events or nxt == cursor:
                    break
                cursor = nxt
            self.prune(now)
            self.save()
            return new

    def since(self, since: datetime | None) -> list[dict]:
        leads = sorted(self.leads.values(), key=lambda x: x["received"])
        if since is None:
            return leads
        return [x for x in leads if (parse_time(x["received"]) or since) >= since]

    def follow_ups(self, since: datetime) -> list[dict]:
        """Events on a lead that was known before: the buyer answered, asked again, or called and nobody answered."""
        out = []
        for lead in self.leads.values():
            for e in lead["events"]:
                if e["first"] or e["type"] not in FOLLOW_UPS or (parse_time(e["received"]) or since) < since:
                    continue
                if e["type"] == "PhoneCallReceived" and (e.get("event") or {}).get("data", {}).get("answered"):
                    continue
                out.append({**e, "lead": lead})
        return sorted(out, key=lambda x: x["received"])


# ---------- what an event says, for people ----------


def buyer(data: dict) -> dict:
    b = data.get("potentialBuyer") or {}
    name = (b.get("name") or " ".join(x for x in (b.get("firstName"), b.get("lastName")) if x)).strip()
    phone = b.get("phone")
    if isinstance(phone, dict):
        phone = " ".join(str(x) for x in (phone.get("prefix") or phone.get("countryCode"), phone.get("number")) if x)
    return {"name": name, "email": (b.get("email") or "").strip(), "phone": str(phone or "").strip()}


def vehicle(data: dict, t: Texts) -> str:
    v = data.get("vehicle") or {}
    what = " ".join(str(x) for x in (v.get("make"), v.get("model")) if x).strip() or t("lead_vehicle_unknown")
    refs = [t("lead_ad", id=v["mobileAdId"])] if v.get("mobileAdId") else []
    if v.get("internalNumber"):
        refs.append(t("lead_internal", id=v["internalNumber"]))
    return f"{what} ({', '.join(refs)})" if refs else what


def _wishes(data: dict, t: Texts) -> list[str]:
    found: list[str] = []

    def walk(d: dict, depth: int) -> None:
        for k, v in d.items():
            key = _WISHES.get(str(k).lower().replace("_", "").replace("-", ""))
            if key and v and t(key) not in found:
                found.append(t(key))
            elif isinstance(v, dict) and depth < 2:
                walk(v, depth + 1)

    walk(data.get("potentialBuyer") or {}, 0)
    return found


def _summary(data: dict) -> str:
    for k, v in data.items():
        if isinstance(v, dict):
            s = _summary(v)
            if s:
                return s
        elif "summary" in str(k).lower() and isinstance(v, str):
            return v.strip()
    return ""


def message(event: dict, t: Texts) -> str:
    data = event.get("data") or {}
    lines = [str(data.get("text") or "").strip()]
    if event.get("eventType") == "PhoneCallReceived":
        lines.append(
            t(
                "lead_call",
                answered=t("lead_call_answered" if data.get("answered") else "lead_call_missed"),
                seconds=data.get("durationInSeconds") or 0,
                number=data.get("callerMaskedPhoneNumber") or "?",
            )
        )
        if _summary(data):
            lines.append(t("lead_call_summary", text=_summary(data)))
    leasing = data.get("leasing") or data.get("leasingConditions") or {}
    if isinstance(leasing, dict) and leasing:
        rate = leasing.get("grossRate") or leasing.get("netRate") or leasing.get("rate")
        lines.append(
            t(
                "lead_leasing",
                months=leasing.get("term") or leasing.get("contractTerm") or "?",
                mileage=leasing.get("mileage") or leasing.get("annualMileage") or "?",
                rate=rate or "?",
            )
        )
    wishes = _wishes(data, t)
    if wishes:
        lines.append(t("lead_wishes", list=", ".join(wishes)))
    if str(data.get("source") or "").upper() == "KLEINANZEIGEN":
        lines.append(t("lead_from_kleinanzeigen"))
    return "\n".join(x for x in lines if x)


def subject(event: dict, t: Texts) -> str:
    data, kind = event.get("data") or {}, event.get("eventType")
    if kind == "PhoneCallReceived":
        key = "lead_subject_call" if data.get("answered") else "lead_subject_missed_call"
    else:
        key = "lead_subject_leasing" if kind == "LeasingLeadSubmitted" else "lead_subject"
    return t(key, vehicle=vehicle(data, t))


def to_vilikon(lead: dict, t: Texts) -> dict:
    """One lead in Vilikon's lead format (`vilikon.lead/1`)."""
    event = lead["first"]
    b = buyer(event.get("data") or {})
    phone = b["phone"] if "X" not in b["phone"].upper() else ""  # a masked number helps nobody
    contact = {k: v for k, v in (("name", b["name"]), ("email", b["email"]), ("telefon", phone)) if v}
    return {
        "standard": "vilikon.lead/1",
        "externe_id": f"mobilede-{lead['id']}",
        "art": "anfrage",
        "kontakt": contact,
        "anliegen": {"betreff": subject(event, t)[:200], "nachricht": message(event, t)[:6000]},
    }


def summary(lead: dict, t: Texts) -> dict:
    """One lead for an employee or an MCP client: who, about what, what happened since."""
    event = lead["first"]
    return {
        "lead_id": lead["id"],
        "received": lead["received"],
        "buyer": buyer(event.get("data") or {}),
        "subject": subject(event, t),
        "message": message(event, t),
        "events": [
            {"type": e["type"], "at": e["at"], **({"text": message(e["event"], t)} if e.get("event") else {})}
            for e in lead["events"]
        ],
    }
