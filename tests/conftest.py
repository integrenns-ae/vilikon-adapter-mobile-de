"""A stand-in for mobile.de, shaped after the examples in its documentation. All data is invented."""

from __future__ import annotations

import base64
import json
import re

import httpx
import pytest

from mobilede_adapter.config import Settings
from mobilede_adapter.service import Service

PASSWORD = "geheim-Passwort-4711"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SELLER = "12"


def ad(ad_id: str, make: str, model: str, price: str, **extra) -> dict:
    return {
        "mobileAdId": ad_id,
        "mobileSellerId": SELLER,
        "vehicleClass": "Car",
        "category": "Limousine",
        "make": make,
        "model": model,
        "modelDescription": f"{model} Musterausstattung",
        "condition": "USED",
        "firstRegistration": "202003",
        "mileage": 48000,
        "internalNumber": f"MF-{ad_id}",
        "price": {
            "consumerPriceGross": price,
            "consumerPriceNet": f"{float(price) / 1.19:.2f}",
            "vatRate": "19.00",
            "type": "FIXED",
            "currency": "EUR",
        },
        "images": [{"ref": "https://img.example/1.jpg"}],
        **extra,
    }


def event(eid: str, lid: str, kind: str, at: str, **data) -> dict:
    return {"occurredAt": at, "eventId": eid, "eventType": kind, "leadId": lid, "data": data}


BUYER = {
    "name": "Erika Muster",
    "email": "erika@example.com",
    "phone": {"prefix": "+49", "number": "301234567"},
    "testDrive": {"requested": True},
    "tradeIn": None,
}
VEHICLE = {"mobileAdId": "207648", "make": "Musterwagen", "model": "M3", "internalNumber": "MF-207648"}


REFDATA = {
    "/refdata/sites/GERMANY/classes/Car/makes": [
        {"name": "MUSTERWAGEN", "description": "Musterwagen"},
        {"name": "BEISPIEL", "description": "Beispiel Motors"},
    ],
    "/refdata/sites/GERMANY/classes/Car/makes/MUSTERWAGEN/models": [
        {"name": "M3", "description": "M3"},
        {"name": "M5", "description": "M5 Kombi"},
    ],
    "/refdata/fuels": [{"name": "PETROL", "description": "Benzin"}, {"name": "DIESEL", "description": "Diesel"}],
}


class FakeMobile:
    def __init__(self) -> None:
        self.sellers = [
            {
                "mobileSellerId": SELLER,
                "customerNumber": "8",
                "companyName": "Autohaus Muster GmbH",
                "siteId": "GERMANY",
                "settings": {"maxImages": 3},
            }
        ]
        self.ads = {
            "207648": ad("207648", "Musterwagen", "M3", "12990.00"),
            "231922": ad("231922", "Beispiel", "B5", "21500.00", reserved=True),
        }
        self.pages = [
            {
                "version": "2025-04-16",
                "nextCursor": "c1",
                "events": [
                    event(
                        "e1",
                        "lead-1",
                        "MessagingLeadSubmitted",
                        "2026-11-10T09:00:00Z",
                        text="Ist der Wagen noch da?",
                        potentialBuyer=BUYER,
                        source="MOBILE",
                        vehicle=VEHICLE,
                    ),
                    event(
                        "e2",
                        "lead-2",
                        "PhoneCallReceived",
                        "2026-11-10T10:00:00Z",
                        answered=False,
                        durationInSeconds=30,
                        callerMaskedPhoneNumber="+49176345XXXX",
                        vehicle=VEHICLE,
                    ),
                ],
                "warnings": [],
            },
            {
                "version": "2025-04-16",
                "events": [
                    event("e3", "lead-1", "BuyerReplied", "2026-11-10T11:00:00Z", text="Passt Samstag?"),
                ],
                "warnings": [],
            },
        ]
        self.calls: list[httpx.Request] = []
        self.images: list[bytes] = []
        self.created: dict[str, str] = {}
        self.lead_status: dict[str, dict] = {}
        self.fail_next: list[int] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.fail_next:
            return httpx.Response(self.fail_next.pop(0), json={"errors": [{"key": "internal"}]})
        if request.url.host == "img.example":
            return httpx.Response(200, content=JPEG)
        auth = base64.b64decode(request.headers["Authorization"].split()[1]).decode()
        if auth != f"api-user:{PASSWORD}":
            return httpx.Response(401)
        m, path = request.method, request.url.path
        body = (
            json.loads(request.content)
            if request.content and "json" in request.headers.get("content-type", "")
            else None
        )
        if path.startswith("/refdata/"):
            values = REFDATA.get(path)
            return httpx.Response(200, json={"values": values}) if values is not None else httpx.Response(404)
        if path == "/seller-api/sellers":
            return httpx.Response(200, json={"sellers": self.sellers})
        if path == f"/seller-api/sellers/{SELLER}":
            return httpx.Response(200, json=self.sellers[0])
        if path == f"/seller-api/sellers/{SELLER}/ads" and m == "GET":
            return httpx.Response(200, json={"ads": list(self.ads.values())})
        if path == f"/seller-api/sellers/{SELLER}/ads" and m == "POST":
            rid = request.headers["X-Mobile-Insertion-Request-Id"]
            if rid in self.created:
                return httpx.Response(
                    303, headers={"Location": f"/seller-api/sellers/{SELLER}/ads/{self.created[rid]}"}
                )
            new = str(300000 + len(self.created))
            self.created[rid] = new
            self.ads[new] = {**body, "mobileAdId": new}
            return httpx.Response(
                201, headers={"Location": f"https://services.mobile.de/seller-api/sellers/{SELLER}/ads/{new}"}
            )
        if path == "/seller-api/images":
            if not request.content.startswith(b"\xff\xd8"):
                return httpx.Response(400, json={"errors": [{"key": "not-a-jpeg-file"}]})
            self.images.append(request.content)
            return httpx.Response(201, json={"ref": f"https://img.example/new-{len(self.images)}.jpg", "hash": "h"})
        if path == f"/seller-api/sellers/{SELLER}/ads/price-rating":
            return httpx.Response(200, json={"label": "REASONABLE_PRICE"})
        a = re.match(rf"^/seller-api/sellers/{SELLER}/ads/(\w+)(/.*)?$", path)
        if a:
            aid, rest = a.group(1), a.group(2) or ""
            if aid not in self.ads:
                return httpx.Response(404)
            if rest == "" and m == "GET":
                return httpx.Response(200, json=self.ads[aid])
            if rest == "" and m == "PUT":
                if set(body) < {"make", "price", "vehicleClass"}:
                    return httpx.Response(
                        400, json={"errors": [{"key": "missing-value", "args": [{"key": "path", "value": "make"}]}]}
                    )
                self.ads[aid] = body
                return httpx.Response(200)
            if rest == "" and m == "DELETE":
                del self.ads[aid]
                return httpx.Response(200)
            if rest == "/statistic":
                return httpx.Response(
                    200, json={"impressions": 32, "parkings": 5, "emails": 2, "calls": 3, "whatsapp": 4}
                )
            if rest == "/price-rating":
                return httpx.Response(200, json={"label": "GOOD_PRICE"})
            if rest == "/vehicle-attribute/renewal-date":
                return httpx.Response(204)
            if rest == "/images" and m == "PUT":
                self.ads[aid]["images"] = body["images"]
                return httpx.Response(200)
            if rest == "/direct-offer":
                return httpx.Response(200)
        if path == f"/seller-api/sellers/{SELLER}/rating/overview":
            return httpx.Response(403)  # below the Gold package
        if path == f"/seller-api/sellers/{SELLER}/rating/ratings/r1/comment":
            return httpx.Response(200)
        if path.startswith(f"/seller-api/sellers/{SELLER}/rating/invites/"):
            return httpx.Response(200)
        if path == "/lead-api/status":
            return httpx.Response(200, json={"status": "UP"})
        if path == f"/lead-api/sellers/{SELLER}/events":
            cursor = request.url.params.get("cursor")
            index = {None: 0, "c1": 1}.get(cursor, 2)
            page = self.pages[index] if index < len(self.pages) else {"events": []}
            return httpx.Response(200, json=page)
        s = re.match(rf"^/lead-api/sellers/{SELLER}/leads/([\w-]+)/status$", path)
        if s and m == "POST":
            self.lead_status[s.group(1)] = body
            return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture
def fake() -> FakeMobile:
    return FakeMobile()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(user="api-user", password=PASSWORD, data_dir=tmp_path, writes="confirm")


@pytest.fixture
async def service(settings, fake, monkeypatch):
    monkeypatch.setattr("mobilede_adapter.client.RETRIES", (0, 0))
    s = Service(settings, transport=httpx.MockTransport(fake.handler))
    yield s
    await s.aclose()
