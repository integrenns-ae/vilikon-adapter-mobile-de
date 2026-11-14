"""A thin client for the mobile.de Seller API and Lead API. HTTP basic auth with the dealer's own API user.

It knows paths, headers, retries and how mobile.de reports errors; it knows nothing about what a request means.
Docs: https://services.mobile.de/docs/seller-api.html and https://services.mobile.de/docs/lead-api.html
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Settings

SELLER_JSON = "application/vnd.de.mobile.api+json"
RETRIES = (1.0, 3.0)  # waits before the 2nd and 3rd attempt on 5xx or a dropped connection
MAX_RETRY_AFTER = 10.0


@dataclass
class ApiError(Exception):
    """An answer from mobile.de that is not a success. `keys` are the error keys from its body."""

    status: int
    errors: list[dict] = field(default_factory=list)
    detail: str = ""

    def __str__(self) -> str:
        return f"mobile.de {self.status}: {[e.get('key') for e in self.errors] or self.detail}"


class Unreachable(Exception):
    pass


@dataclass
class Answer:
    status: int
    data: Any
    headers: httpx.Headers


class MobileClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.base_url,
            auth=httpx.BasicAuth(settings.user, settings.password),
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": "vilikon-adapter-mobile-de"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        content: bytes | None = None,
        content_type: str | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        accept: str = SELLER_JSON,
        ok: tuple[int, ...] = (200, 201, 204),
    ) -> Answer:
        head = {"Accept": accept, **(headers or {})}
        if json is not None:
            head["Content-Type"] = content_type or SELLER_JSON
        elif content is not None and content_type:
            head["Content-Type"] = content_type
        for attempt in range(len(RETRIES) + 1):
            try:
                r = await self._http.request(method, path, json=json, content=content, params=params, headers=head)
            except httpx.TransportError as e:
                if attempt < len(RETRIES):
                    await asyncio.sleep(RETRIES[attempt])
                    continue
                raise Unreachable(type(e).__name__) from e
            if r.status_code >= 500 and attempt < len(RETRIES):
                await asyncio.sleep(_retry_after(r) or RETRIES[attempt])
                continue
            break
        if r.status_code not in ok:
            raise ApiError(r.status_code, _errors(r), r.text[:300] if not _errors(r) else "")
        return Answer(r.status_code, _body(r), r.headers)

    # ---------- Seller API ----------

    async def sellers(self) -> list[dict]:
        return (await self.request("GET", "/seller-api/sellers")).data.get("sellers") or []

    async def seller(self, seller_id: str) -> dict:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}")).data

    async def ads(self, seller_id: str) -> list[dict]:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}/ads")).data.get("ads") or []

    async def ad(self, seller_id: str, ad_id: str) -> dict:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}/ads/{ad_id}")).data

    async def create_ad(self, seller_id: str, ad: dict, request_id: str) -> tuple[str, bool]:
        """Returns (mobileAdId, created). A repeat with the same request id answers 303: the ad exists already."""
        a = await self.request(
            "POST",
            f"/seller-api/sellers/{seller_id}/ads",
            json=ad,
            headers={"X-Mobile-Insertion-Request-Id": request_id},
            ok=(201, 303),
        )
        location = a.headers.get("Location", "")
        return location.rstrip("/").rsplit("/", 1)[-1], a.status == 201

    async def update_ad(self, seller_id: str, ad_id: str, ad: dict) -> None:
        await self.request("PUT", f"/seller-api/sellers/{seller_id}/ads/{ad_id}", json=ad)

    async def delete_ad(self, seller_id: str, ad_id: str) -> None:
        await self.request("DELETE", f"/seller-api/sellers/{seller_id}/ads/{ad_id}")

    async def renew_ad(self, seller_id: str, ad_id: str) -> None:
        await self.request("POST", f"/seller-api/sellers/{seller_id}/ads/{ad_id}/vehicle-attribute/renewal-date")

    async def upload_image(self, data: bytes) -> dict:
        """One JPG; returns {"ref", "hash"} to put into an ad's `images`."""
        a = await self.request("POST", "/seller-api/images", content=data, content_type="image/jpeg")
        return {"ref": a.data.get("ref"), **({"hash": a.data["hash"]} if a.data.get("hash") else {})}

    async def set_images(self, seller_id: str, ad_id: str, refs: list[dict]) -> None:
        await self.request("PUT", f"/seller-api/sellers/{seller_id}/ads/{ad_id}/images", json={"images": refs})

    async def statistic(self, seller_id: str, ad_id: str) -> dict:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}/ads/{ad_id}/statistic")).data

    async def price_rating(self, seller_id: str, ad_id: str) -> dict:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}/ads/{ad_id}/price-rating")).data

    async def preview_price_rating(self, seller_id: str, ad: dict) -> dict:
        return (await self.request("POST", f"/seller-api/sellers/{seller_id}/ads/price-rating", json=ad)).data

    async def direct_offer(self, seller_id: str, ad_id: str, text: str, days: int) -> None:
        await self.request(
            "PUT",
            f"/seller-api/sellers/{seller_id}/ads/{ad_id}/direct-offer",
            json={"offerText": text, "validForDays": days},
        )

    async def rating_overview(self, seller_id: str) -> dict:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}/rating/overview")).data

    async def ratings(self, seller_id: str) -> Any:
        return (await self.request("GET", f"/seller-api/sellers/{seller_id}/rating/ratings")).data

    async def reply_rating(self, seller_id: str, rating_id: str, comment: str) -> None:
        await self.request(
            "PUT", f"/seller-api/sellers/{seller_id}/rating/ratings/{rating_id}/comment", json={"comment": comment}
        )

    async def invite_rating(self, seller_id: str, ad_id: str, email: str) -> None:
        await self.request(
            "POST", f"/seller-api/sellers/{seller_id}/rating/invites/{ad_id}", json={"buyerEmail": email}
        )

    # ---------- Lead API ----------

    async def lead_status_check(self) -> dict:
        return (await self.request("GET", "/lead-api/status", accept="application/json")).data

    async def lead_events(self, seller_id: str, cursor: str | None) -> dict:
        params = {"cursor": cursor} if cursor else None
        return (
            await self.request("GET", f"/lead-api/sellers/{seller_id}/events", params=params, accept="application/json")
        ).data

    async def set_lead_status(self, seller_id: str, lead_id: str, status: str, occurred_at: str) -> None:
        await self.request(
            "POST",
            f"/lead-api/sellers/{seller_id}/leads/{lead_id}/status",
            json={"newStatus": status, "occurredAt": occurred_at},
            content_type="application/json",
            accept="application/json",
        )


def _body(r: httpx.Response) -> Any:
    if not r.content:
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


def _errors(r: httpx.Response) -> list[dict]:
    body = _body(r)
    errors = body.get("errors") if isinstance(body, dict) else None
    return [e for e in errors if isinstance(e, dict)] if isinstance(errors, list) else []


def _retry_after(r: httpx.Response) -> float:
    try:
        return min(float(r.headers.get("Retry-After", "")), MAX_RETRY_AFTER)
    except ValueError:
        return 0.0
