"""What the adapter can do, in the dealer's terms. Both fronts (MCP and Vilikon's ki/ paths) call only this.

Reads return data. Writes return a Plan (guard.py): the checks and the current state come first, the change only
when the plan is run. mobile.de wants the whole listing on every update, so a change is always: fetch the listing,
change one field, send it back complete.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from . import leads as lead_lib
from .client import ApiError, MobileClient, Unreachable
from .config import Settings
from .guard import Plan
from .images import ImageError, ImageStore
from .leads import LeadStore
from .texts import Texts

MAX_IMAGE_BYTES = 2_097_152
REFDATA_KIND = re.compile(r"^[a-z]{3,30}$")
REFDATA_NAME = re.compile(r"^[A-Za-z0-9_-]{1,60}$")
REFDATA_CACHE_S = 86400
MAX_REFDATA = 60
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?:\+|\b0)\d[\d\s/().-]{5,}\d")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserError(Exception):
    """A sentence for the person who asked; nothing happened at mobile.de."""


class BadId(Exception):
    """An id that cannot be one of mobile.de's."""


class Service:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.t = Texts(settings.lang)
        self.client = MobileClient(settings, transport=transport)
        self._image_http = httpx.AsyncClient(timeout=30.0, transport=transport, follow_redirects=True)
        self.store = LeadStore(settings.data_dir)
        self.images = ImageStore(settings.data_dir)
        self._refdata: dict[str, tuple[float, list[dict]]] = {}
        self._seller_id = settings.seller_id

    async def aclose(self) -> None:
        await self.client.aclose()
        await self._image_http.aclose()

    # ---------- errors ----------

    def explain(self, e: Exception) -> str:
        """Any failure as one sentence. Never contains the password: mobile.de's answers do not echo it."""
        t = self.t
        if isinstance(e, UserError):
            return str(e)
        if isinstance(e, ImageError):
            return t(e.key)
        if isinstance(e, BadId):
            return t("id_invalid", id=str(e))
        if isinstance(e, Unreachable):
            return t("unreachable", error=str(e))
        if not isinstance(e, ApiError):
            return t("http_5xx")
        for err in e.errors:
            key = str(err.get("key") or "")
            path = next((str(a.get("value")) for a in err.get("args") or [] if a.get("key") == "path"), key)
            if key == "invalid-value":
                return t("invalid_value", path=path)
            if "missing" in key or "mandatory" in key:
                return t("missing_value", path=path)
            if key == "not-a-jpeg-file":
                return t("not_a_jpeg")
            if key.startswith("images-per-ad-limit"):
                return t("too_many_images")
            if key == "concurrent-update-error":
                return t("concurrent_update")
            if key:
                return t("error_key", key=key)
        if e.status in (401, 403, 404, 409):
            return t(f"http_{e.status}")
        return t("http_5xx") if e.status >= 500 else t("http_other", status=e.status)

    # ---------- the dealer ----------

    async def seller_id(self) -> str:
        if not self.settings.configured:
            raise UserError(self.t("not_configured"))
        if self._seller_id:
            return self._seller_id
        sellers = await self.client.sellers()
        if not sellers:
            raise UserError(self.t("no_seller"))
        if len(sellers) > 1:
            raise UserError(self.t("several_sellers", ids=", ".join(str(s.get("mobileSellerId")) for s in sellers)))
        self._seller_id = str(sellers[0].get("mobileSellerId"))
        return self._seller_id

    async def seller_info(self) -> dict:
        sid = await self.seller_id()
        s = await self.client.seller(sid)
        return {
            "seller_id": sid,
            "name": s.get("companyName") or s.get("name") or "",
            "customer_number": s.get("customerNumber") or "",
            "max_images": (s.get("settings") or {}).get("maxImages"),
            "settings": s.get("settings") or {},
        }

    async def check(self) -> dict:
        """Whether the credentials work, for both APIs."""
        info = await self.seller_info()
        text = self.t("check_ok", name=info["name"] or "?", id=info["seller_id"])
        try:
            await self.client.lead_status_check()
            leads_ok = True
        except ApiError as e:
            if e.status not in (401, 403):
                raise
            leads_ok = False
        return {"ok": True, "leads": leads_ok, "text": text if leads_ok else f"{text} {self.t('check_leads_off')}"}

    # ---------- listings: read ----------

    def label(self, ad: dict) -> str:
        what = " ".join(str(x) for x in (ad.get("make"), ad.get("modelDescription") or ad.get("model")) if x)
        ref = ad.get("internalNumber") or ad.get("mobileAdId")
        return f"{what or '?'} ({ref})" if ref else (what or "?")

    def compact(self, ad: dict) -> dict:
        price = ad.get("price") or {}
        return {
            "ad_id": str(ad.get("mobileAdId") or ""),
            "label": self.label(ad),
            "price": _number(price.get("consumerPriceGross")),
            "currency": price.get("currency") or "EUR",
            "mileage": ad.get("mileage"),
            "first_registration": ad.get("firstRegistration"),
            "condition": ad.get("condition"),
            "reserved": bool(ad.get("reserved")),
            "internal_number": ad.get("internalNumber"),
            "images": len(ad.get("images") or []),
            "created": ad.get("creationDate"),
            "modified": ad.get("modificationDate"),
        }

    async def list_ads(self, search: str = "", limit: int = 50) -> dict:
        ads = await self.client.ads(await self.seller_id())
        words = [w for w in search.lower().split() if w]
        hits = [a for a in ads if all(w in json.dumps(self.compact(a), ensure_ascii=False).lower() for w in words)]
        limit = max(1, min(int(limit or 50), 500))
        return {"total": len(ads), "found": len(hits), "ads": [self.compact(a) for a in hits[:limit]]}

    async def get_ad(self, ad_id: str) -> dict:
        return await self.client.ad(await self.seller_id(), _id(ad_id))

    async def ad_statistics(self, ad_id: str) -> dict:
        """Not stored anywhere: mobile.de allows these numbers only for the listing's lifetime, not aggregated."""
        return await self.client.statistic(await self.seller_id(), _id(ad_id))

    async def price_rating(self, ad_id: str) -> dict:
        return await self.client.price_rating(await self.seller_id(), _id(ad_id))

    async def preview_price_rating(self, ad: dict) -> dict:
        return await self.client.preview_price_rating(await self.seller_id(), _ad_payload(ad, self.t))

    # ---------- ratings: read ----------

    async def rating_overview(self) -> dict:
        return await self.client.rating_overview(await self.seller_id())

    async def list_ratings(self) -> Any:
        return await self.client.ratings(await self.seller_id())

    # ---------- leads: read ----------

    async def sync_leads(self) -> int:
        sid = await self.seller_id()
        return await self.store.sync(lambda cursor: self.client.lead_events(sid, cursor))

    async def list_leads(self, since: str = "", limit: int = 50) -> dict:
        await self.sync_leads()
        found = self.store.since(lead_lib.parse_time(since) if since else None)
        limit = max(1, min(int(limit or 50), 200))
        return {"found": len(found), "leads": [lead_lib.summary(x, self.t) for x in found[-limit:]]}

    async def reference_data(self, kind: str, make: str = "", vehicle_class: str = "Car", search: str = "") -> dict:
        """mobile.de's fixed values: `makes` and `models` (of `make`) of a vehicle class, its `categories`, or a table
        such as `fuels`, `gearboxes`, `colors`. An ad takes the `name`, never the description."""
        kind = kind.strip().lower()
        cls = vehicle_class.strip() or "Car"
        if not REFDATA_KIND.match(kind) or not REFDATA_NAME.match(cls) or (make and not REFDATA_NAME.match(make)):
            raise UserError(self.t("refdata_invalid"))
        if kind == "models" and not make:
            raise UserError(self.t("refdata_make_missing"))
        site = await self._site()
        prefix = f"/refdata/sites/{site}" if site else "/refdata"
        path = {
            "makes": f"{prefix}/classes/{cls}/makes",
            "models": f"{prefix}/classes/{cls}/makes/{make.upper()}/models",
            "categories": f"/refdata/classes/{cls}/categories",
        }.get(kind, f"/refdata/{kind}")
        values = await self._refdata_values(path)
        words = [w for w in re.split(r"\W+", search.lower()) if w]
        hits = [v for v in values if all(w in f"{v['name']} {v['description']}".lower() for w in words)]
        return {"kind": kind, "values": hits[:MAX_REFDATA], "more": max(0, len(hits) - MAX_REFDATA)}

    async def _site(self) -> str:
        try:
            s = await self.client.seller(await self.seller_id())
        except Exception:  # reference data needs no account; without one the general tables count
            return ""
        site = str(s.get("siteId") or "")
        return site if REFDATA_NAME.match(site) else ""

    async def _refdata_values(self, path: str) -> list[dict]:
        hit = self._refdata.get(path)
        if hit and time.monotonic() - hit[0] < REFDATA_CACHE_S:
            return hit[1]
        lang = "en" if self.settings.lang == "en" else "de"
        data = (await self.client.request("GET", path, headers={"Accept-Language": lang})).data or {}
        values = [
            {"name": str(v.get("name") or ""), "description": str(v.get("description") or "")}
            for v in (data.get("values") or [])
            if isinstance(v, dict) and v.get("name")
        ]
        self._refdata[path] = (time.monotonic(), values)
        return values

    def stage_image(self, data: bytes) -> dict:
        """Keep a photo for a listing; the id goes into create_ad or set_images as {"image": id}."""
        out = self.images.add(data)
        return out | {"text": self.t("image_staged", image=out["image"], width=out["width"], height=out["height"])}

    # ---------- writes: each returns a Plan ----------

    async def _ad_for_change(self, ad_id: str) -> tuple[str, str, dict]:
        sid, aid = await self.seller_id(), _id(ad_id)
        return sid, aid, await self.client.ad(sid, aid)

    async def plan_change_price(self, ad_id: str, price: float) -> Plan:
        new = _number(price)
        if new is None or new <= 0:
            raise UserError(self.t("price_invalid"))
        sid, aid, ad = await self._ad_for_change(ad_id)
        old_price = ad.get("price")
        if not isinstance(old_price, dict) or _number(old_price.get("consumerPriceGross")) is None:
            raise UserError(self.t("ad_has_no_price"))
        cur = old_price.get("currency") or "EUR"
        changed = copy.deepcopy(ad)
        changed["price"] = _with_gross(old_price, new)
        label, old, new_text = (
            self.label(ad),
            self.t.money(_number(old_price["consumerPriceGross"]), cur),
            self.t.money(new, cur),
        )

        async def run() -> str:
            await self.client.update_ad(sid, aid, changed)
            return self.t("done_price", ad=label, new=new_text)

        return Plan(self.t("preview_price", ad=label, old=old, new=new_text), run)

    async def plan_set_reserved(self, ad_id: str, reserved: bool) -> Plan:
        sid, aid, ad = await self._ad_for_change(ad_id)
        changed = {**ad, "reserved": bool(reserved)}
        label, which = self.label(ad), "on" if reserved else "off"

        async def run() -> str:
            await self.client.update_ad(sid, aid, changed)
            return self.t(f"done_reserved_{which}", ad=label)

        return Plan(self.t(f"preview_reserved_{which}", ad=label), run)

    async def plan_renew_ad(self, ad_id: str) -> Plan:
        sid, aid, ad = await self._ad_for_change(ad_id)
        label = self.label(ad)

        async def run() -> str:
            await self.client.renew_ad(sid, aid)
            return self.t("done_renew", ad=label)

        return Plan(self.t("preview_renew", ad=label), run)

    async def plan_delete_ad(self, ad_id: str) -> Plan:
        sid, aid, ad = await self._ad_for_change(ad_id)
        label = self.label(ad)

        async def run() -> str:
            await self.client.delete_ad(sid, aid)
            return self.t("done_delete", ad=label)

        return Plan(self.t("preview_delete", ad=label), run)

    async def plan_send_direct_offer(self, ad_id: str, text: str, days: int) -> Plan:
        text = (text or "").strip()
        if not 3 <= len(text) <= 1000:
            raise UserError(self.t("offer_length"))
        try:
            text.encode("latin-1")
        except UnicodeEncodeError:
            raise UserError(self.t("offer_latin1")) from None
        if _CONTACT.search(text):
            raise UserError(self.t("offer_contact"))
        if not isinstance(days, int) or not 1 <= days <= 14:
            raise UserError(self.t("offer_days"))
        sid, aid, ad = await self._ad_for_change(ad_id)
        label = self.label(ad)

        async def run() -> str:
            await self.client.direct_offer(sid, aid, text, days)
            return self.t("done_offer", ad=label)

        return Plan(self.t("preview_offer", ad=label, days=days, text=text), run)

    async def plan_reply_rating(self, rating_id: str, comment: str) -> Plan:
        comment = (comment or "").strip()
        if not 1 <= len(comment) <= 1000:
            raise UserError(self.t("comment_length"))
        sid, rid = await self.seller_id(), _id(rating_id)

        async def run() -> str:
            await self.client.reply_rating(sid, rid, comment)
            return self.t("done_reply", id=rid)

        return Plan(self.t("preview_reply", id=rid, text=comment), run)

    async def plan_invite_rating(self, ad_id: str, buyer_email: str) -> Plan:
        email = (buyer_email or "").strip()
        if not _EMAIL.match(email):
            raise UserError(self.t("email_invalid"))
        sid, aid, ad = await self._ad_for_change(ad_id)
        label = self.label(ad)

        async def run() -> str:
            await self.client.invite_rating(sid, aid, email)
            return self.t("done_invite", email=email)

        return Plan(self.t("preview_invite", email=email, ad=label), run)

    async def plan_set_lead_status(self, lead_id: str, status: str) -> Plan:
        status = (status or "").strip().upper()
        if status not in lead_lib.STATUSES:
            raise UserError(self.t("status_invalid", values=", ".join(lead_lib.STATUSES)))
        sid, lid = await self.seller_id(), _id(lead_id.removeprefix("mobilede-"))

        async def run() -> str:
            await self.client.set_lead_status(sid, lid, status, datetime.now(UTC).isoformat(timespec="seconds"))
            return self.t("done_status", id=lid, status=status)

        return Plan(self.t("preview_status", id=lid, status=status), run)

    async def plan_set_images(self, ad_id: str, images: list) -> Plan:
        sid, aid, ad = await self._ad_for_change(ad_id)
        blobs = await self._load_images(images)
        await self._check_count(len(blobs))
        label = self.label(ad)

        async def run() -> str:
            refs = [await self.client.upload_image(b) for b in blobs]  # one after the other, as mobile.de asks
            await self.client.set_images(sid, aid, refs)
            return self.t("done_images", ad=label, count=len(refs))

        return Plan(self.t("preview_images", ad=label, count=len(blobs)), run)

    async def plan_create_ad(self, ad: dict, images: list | None = None) -> Plan:
        payload = _ad_payload(ad, self.t)
        sid = await self.seller_id()
        blobs = await self._load_images(images or [], required=False)
        await self._check_count(len(blobs))
        # The same listing with the same images gets the same id: a repeat after a timeout creates nothing twice.
        request_id = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode() + b"".join(hashlib.sha256(b).digest() for b in blobs)
        ).hexdigest()[:32]
        label = self.label(payload)
        price = self.t.money(
            _number(payload["price"].get("consumerPriceGross")), payload["price"].get("currency") or "EUR"
        )

        async def run() -> str:
            refs = [await self.client.upload_image(b) for b in blobs]
            ad_id, created = await self.client.create_ad(
                sid, {**payload, **({"images": refs} if refs else {})}, request_id
            )
            return self.t("done_create" if created else "done_create_existing", ad=label, id=ad_id)

        return Plan(self.t("preview_create", ad=label, price=price, count=len(blobs)), run)

    # ---------- images ----------

    async def _check_count(self, count: int) -> None:
        maximum = (await self.seller_info())["max_images"]
        if isinstance(maximum, int) and count > maximum:
            raise UserError(self.t("image_max", max=maximum, count=count))

    async def _load_images(self, images: list, required: bool = True) -> list[bytes]:
        if not images:
            if required:
                raise UserError(self.t("images_missing"))
            return []
        out = []
        for item in images:
            if isinstance(item, str):
                item = {"image": item} if item.startswith("img-") else {"url": item}
            item = item or {}
            if item.get("image"):
                data = self.images.get(item["image"])
            elif item.get("base64"):
                try:
                    data = base64.b64decode(str(item["base64"]).split(",", 1)[-1], validate=True)
                except (binascii.Error, ValueError):
                    raise UserError(self.t("image_source")) from None
            elif str(item.get("url") or "").startswith("https://"):
                try:
                    r = await self._image_http.get(item["url"])
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    raise UserError(self.t("image_fetch", error=type(e).__name__)) from None
                data = r.content
            else:
                raise UserError(self.t("image_source"))
            if len(data) > MAX_IMAGE_BYTES:
                raise UserError(self.t("image_too_big"))
            if not data.startswith(b"\xff\xd8\xff"):
                raise UserError(self.t("not_a_jpeg"))
            out.append(data)
        return out


# ---------- helpers ----------


def _id(value: Any) -> str:
    """mobile.de ids are numbers or simple tokens; nothing else gets into a path."""
    s = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", s):
        raise BadId(s[:40])
    return s


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _like(original: Any, value: float) -> Any:
    """Keep mobile.de's own type: prices may come as strings ("12990.00") or as numbers."""
    return f"{value:.2f}" if isinstance(original, str) else (int(value) if value == int(value) else round(value, 2))


def _with_gross(price: dict, gross: float) -> dict:
    out = dict(price)
    out["consumerPriceGross"] = _like(price.get("consumerPriceGross"), gross)
    vat = _number(price.get("vatRate"))
    if vat is not None and "consumerPriceNet" in price:
        out["consumerPriceNet"] = _like(price.get("consumerPriceNet"), round(gross / (1 + vat / 100), 2))
    return out


def _ad_payload(ad: dict, t: Texts) -> dict:
    if not isinstance(ad, dict):
        raise UserError(t("ad_invalid"))
    price = ad.get("price") if isinstance(ad.get("price"), dict) else {}
    if not ad.get("vehicleClass") or not ad.get("make") or _number(price.get("consumerPriceGross")) is None:
        raise UserError(t("ad_invalid"))
    return {k: v for k, v in ad.items() if k not in ("mobileAdId", "images")}
