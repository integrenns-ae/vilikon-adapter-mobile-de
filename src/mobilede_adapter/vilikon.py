"""The Vilikon front: the same functions as HTTP paths under /ki/, as Vilikon's standards describe them.

- `vilikon.modul/1` (MODULE.json): functions for employees. Every write is `"freigabe": true`, so the cockpit shows
  the owner a card first and only his yes calls the path, with the header `X-Vilikon-Freigabe`. A write without that
  header is refused; the same header twice does the work once.
- `vilikon.kanal/1`: `GET ki/kanal/leads` hands new inquiries to the cockpit's lead intake.
- `ki/ereignisse`: what happens on a known inquiry (the buyer answered, asked again, a missed call) becomes a case.
- `ki/karte`: a small dashboard card. Answers from local data only, within the cockpit's 5 seconds.
Errors are `{"fehler": "..."}` with a 4xx/5xx status, in plain language.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import leads as lead_lib
from .client import ApiError
from .guard import Plan
from .service import BadId, Service, UserError

APPROVAL = "x-vilikon-freigabe"
LEAD_MARGIN = timedelta(days=1)  # the cockpit counts each externe_id once: rather deliver too much than too little
EVENT_WINDOW = timedelta(days=3)  # the cockpit counts each event id once and takes at most 5 per call
MAX_LEADS = 100
MAX_EVENTS = 20


class Approvals:
    """The approvals already carried out, so a repeated call with the same card does nothing twice."""

    def __init__(self, data_dir: Path) -> None:
        self.file = Path(data_dir) / "approvals.json"

    def _read(self) -> dict[str, str]:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def get(self, approval: str) -> str | None:
        return self._read().get(approval)

    def put(self, approval: str, text: str) -> None:
        done = self._read()
        done[approval] = text
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(list(done.items())[-500:]), ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.file)


def routes(service: Service) -> list[Route]:
    t = service.t
    approvals = Approvals(service.settings.data_dir)

    def error(e: Exception) -> JSONResponse:
        status = 400 if isinstance(e, UserError | BadId) else 502
        if isinstance(e, ApiError) and e.status in (401, 403, 404, 409):
            status = {401: 502, 403: 403, 404: 404, 409: 409}[e.status]
        return JSONResponse({"fehler": service.explain(e)}, status_code=status)

    async def body(request: Request) -> dict:
        try:
            data = await request.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def read(call: Callable[[Request], Awaitable[Any]]):
        async def handler(request: Request) -> JSONResponse:
            try:
                return JSONResponse(await call(request))
            except Exception as e:
                return error(e)

        return handler

    def write(make: Callable[[Request, dict], Awaitable[Plan]]):
        async def handler(request: Request) -> JSONResponse:
            approval = request.headers.get(APPROVAL, "").strip()
            if not approval:
                return JSONResponse({"fehler": t("approval_needed")}, status_code=403)
            done = approvals.get(approval)
            if done is not None:
                return JSONResponse({"text": done})
            try:
                plan = await make(request, await body(request))
                text = await plan.run()
            except Exception as e:
                return error(e)
            approvals.put(approval, text)
            return JSONResponse({"text": text})

        return handler

    def p(request: Request, name: str) -> str:
        return request.path_params[name]

    def q(request: Request, name: str, default: str = "") -> str:
        return request.query_params.get(name, default)

    # ---------- the cockpit's own calls ----------

    async def channel_leads(request: Request) -> dict:
        await service.sync_leads()
        since = lead_lib.parse_time(q(request, "seit"))
        found = service.store.since(since - LEAD_MARGIN if since else None)
        return {"leads": [lead_lib.to_vilikon(x, t) for x in found[-MAX_LEADS:]]}

    async def events(request: Request) -> dict:
        await service.sync_leads()
        out = []
        for e in service.store.follow_ups(datetime.now(UTC) - EVENT_WINDOW)[:MAX_EVENTS]:
            event, lead = e["event"], e["lead"]
            name = lead_lib.buyer(lead["first"].get("data") or {})["name"] or t("event_buyer")
            kind = lead_lib.FOLLOW_UPS[e["type"]]
            title = {
                "buyer_reply": "event_reply_title",
                "resubmission": "event_resubmit_title",
                "missed_call": "event_missed_call_title",
            }[kind]
            out.append(
                {
                    "id": e["id"],
                    "art": kind,
                    "titel": f"{t(title, name=name)}: {lead_lib.subject(lead['first'], t)}"[:300],
                    "text": lead_lib.message(event, t),
                    "data": {"lead_id": lead["id"]},
                }
            )
        return {"ereignisse": out}

    async def card(request: Request) -> dict:
        week = datetime.now(UTC) - timedelta(days=7)
        recent = service.store.since(week)
        return {
            "zahl": str(len(recent)),
            "text": t("card_text"),
            "ton": "warn" if recent else "neutral",
            "zeilen": [
                {
                    "text": lead_lib.buyer(x["first"].get("data") or {})["name"] or "?",
                    "wert": lead_lib.vehicle((x["first"].get("data") or {}), t)[:60],
                }
                for x in recent[-8:][::-1]
            ],
        }

    async def page(request: Request) -> HTMLResponse:
        return HTMLResponse(
            f'<!doctype html><meta charset="utf-8"><title>{escape(t("page_title"))}</title>'
            f'<link rel="stylesheet" href="/api/kit/farben.css"><body style="font-family:system-ui;padding:16px">'
            f"<h1>{escape(t('page_title'))}</h1><p>{escape(t('page_ok'))}</p>"
        )

    async def check(request: Request) -> dict:
        return await service.check()

    return [
        Route("/", page),
        Route("/ki/pruefen", read(check)),
        Route("/ki/kanal/leads", read(channel_leads)),
        Route("/ki/ereignisse", read(events)),
        Route("/ki/karte", read(card)),
        # reads for employees
        Route("/ki/seller", read(lambda r: service.seller_info())),
        Route(
            "/ki/ads", read(lambda r: service.list_ads(q(r, "search"), int(q(r, "limit", "50") or 50))), methods=["GET"]
        ),
        Route("/ki/ads/{ad_id}", read(lambda r: service.get_ad(p(r, "ad_id")))),
        Route("/ki/ads/{ad_id}/statistics", read(lambda r: service.ad_statistics(p(r, "ad_id")))),
        Route("/ki/ads/{ad_id}/price-rating", read(lambda r: service.price_rating(p(r, "ad_id")))),
        Route("/ki/price-rating-preview", read(_preview_price(service)), methods=["POST"]),
        Route("/ki/ratings", read(lambda r: service.list_ratings())),
        Route("/ki/ratings/overview", read(lambda r: service.rating_overview())),
        Route("/ki/leads", read(lambda r: service.list_leads(q(r, "since"), int(q(r, "limit", "50") or 50)))),
        # writes, each only after the owner's approval
        Route(
            "/ki/ads", write(lambda r, b: service.plan_create_ad(b.get("ad") or {}, b.get("images"))), methods=["POST"]
        ),
        Route(
            "/ki/ads/{ad_id}/price",
            write(lambda r, b: service.plan_change_price(p(r, "ad_id"), b.get("price"))),
            methods=["PUT"],
        ),
        Route(
            "/ki/ads/{ad_id}/reserved",
            write(lambda r, b: service.plan_set_reserved(p(r, "ad_id"), bool(b.get("reserved")))),
            methods=["PUT"],
        ),
        Route("/ki/ads/{ad_id}/renew", write(lambda r, b: service.plan_renew_ad(p(r, "ad_id"))), methods=["POST"]),
        Route("/ki/ads/{ad_id}/delete", write(lambda r, b: service.plan_delete_ad(p(r, "ad_id"))), methods=["POST"]),
        Route(
            "/ki/ads/{ad_id}/images",
            write(lambda r, b: service.plan_set_images(p(r, "ad_id"), b.get("images") or [])),
            methods=["PUT"],
        ),
        Route(
            "/ki/ads/{ad_id}/direct-offer",
            write(lambda r, b: service.plan_send_direct_offer(p(r, "ad_id"), b.get("text", ""), _int(b.get("days")))),
            methods=["PUT"],
        ),
        Route(
            "/ki/ads/{ad_id}/rating-invite",
            write(lambda r, b: service.plan_invite_rating(p(r, "ad_id"), b.get("buyer_email", ""))),
            methods=["POST"],
        ),
        Route(
            "/ki/ratings/{rating_id}/reply",
            write(lambda r, b: service.plan_reply_rating(p(r, "rating_id"), b.get("comment", ""))),
            methods=["PUT"],
        ),
        Route(
            "/ki/leads/{lead_id}/status",
            write(lambda r, b: service.plan_set_lead_status(p(r, "lead_id"), b.get("status", ""))),
            methods=["PUT"],
        ),
    ]


def _preview_price(service: Service):
    async def call(request: Request) -> dict:
        try:
            data = await request.json()
        except ValueError:
            data = {}
        return await service.preview_price_rating((data or {}).get("ad") or {})

    return call


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
