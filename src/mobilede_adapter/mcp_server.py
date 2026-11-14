"""The MCP front: every function of service.py as a tool, for any MCP client.

Reads answer right away. Writes go through the WriteGuard: with MOBILE_DE_WRITES=confirm the first call returns a
preview and a code, the second call with the same values and `confirmation` carries it out.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .guard import Plan, WriteGuard
from .service import Service

INSTRUCTIONS = (
    "Tools for one car dealer's account at mobile.de: listings, prices, statistics, ratings and customer inquiries "
    "(leads). Reading is free. Every change returns a preview and a confirmation code first unless the operator "
    "switched confirmations off; show the preview to the person and call again with `confirmation` only after they "
    "agreed. Prices are gross consumer prices in the listing's currency. Never put buyers' contact data anywhere "
    "the person did not ask for."
)
READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


def build(service: Service) -> MCPServer:
    server = MCPServer(name="mobile.de", instructions=INSTRUCTIONS, version="0.1.0")
    guard = WriteGuard(service.settings.writes, service.t)

    async def safe(call: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await call()
        except Exception as e:  # every failure becomes one sentence; nothing else leaves the adapter
            return {"error": service.explain(e)}

    async def write(name: str, args: dict, plan: Callable[[], Awaitable[Plan]], confirmation: str) -> Any:
        return await safe(lambda: guard.apply(name, args, plan, confirmation))

    # ---------- read ----------

    @server.tool(annotations=READ)
    async def check_connection() -> dict:
        """Check that the API user works for the Seller API and the Lead API."""
        return await safe(service.check)

    @server.tool(annotations=READ)
    async def seller_info() -> dict:
        """The dealer account: id, name, customer number and settings such as the maximum images per listing."""
        return await safe(service.seller_info)

    @server.tool(annotations=READ)
    async def list_ads(search: str = "", limit: int = 50) -> dict:
        """The dealer's listings in short form. `search` keeps only listings containing every word (make, model,
        internal number, ...)."""
        return await safe(lambda: service.list_ads(search, limit))

    @server.tool(annotations=READ)
    async def get_ad(ad_id: str) -> dict:
        """One listing with every field mobile.de keeps."""
        return await safe(lambda: service.get_ad(ad_id))

    @server.tool(annotations=READ)
    async def ad_statistics(ad_id: str) -> dict:
        """Impressions, parkings, e-mails, calls and WhatsApp contacts of one listing. Needs a permission mobile.de
        grants on request. Do not store these numbers beyond the listing's lifetime."""
        return await safe(lambda: service.ad_statistics(ad_id))

    @server.tool(annotations=READ)
    async def price_rating(ad_id: str) -> dict:
        """mobile.de's price label for one listing (GOOD_PRICE, REASONABLE_PRICE, INCREASED_PRICE, ...)."""
        return await safe(lambda: service.price_rating(ad_id))

    @server.tool(annotations=READ)
    async def preview_price_rating(ad: dict) -> dict:
        """The price label a listing would get, before it exists. `ad` in mobile.de's listing format."""
        return await safe(lambda: service.preview_price_rating(ad))

    @server.tool(annotations=READ)
    async def rating_overview() -> dict:
        """The dealer's rating at mobile.de in summary. Needs at least the Gold package."""
        return await safe(service.rating_overview)

    @server.tool(annotations=READ)
    async def list_ratings() -> Any:
        """The dealer's individual ratings with their ids, for replying."""
        return await safe(service.list_ratings)

    @server.tool(annotations=READ)
    async def list_leads(since: str = "", limit: int = 50) -> dict:
        """Customer inquiries (leads) with the buyer's contact data, the vehicle and everything that happened since:
        replies, calls. `since` is an ISO time; empty means everything from the last 30 days."""
        return await safe(lambda: service.list_leads(since, limit))

    # ---------- write ----------

    @server.tool(annotations=WRITE)
    async def change_price(ad_id: str, price: float, confirmation: str = "") -> dict:
        """Set the gross consumer price of a listing. The net price follows the listing's VAT rate."""
        args = {"ad_id": ad_id, "price": price}
        return await write("change_price", args, lambda: service.plan_change_price(ad_id, price), confirmation)

    @server.tool(annotations=WRITE)
    async def set_reserved(ad_id: str, reserved: bool, confirmation: str = "") -> dict:
        """Mark a listing as reserved, or remove the mark."""
        args = {"ad_id": ad_id, "reserved": reserved}
        return await write("set_reserved", args, lambda: service.plan_set_reserved(ad_id, reserved), confirmation)

    @server.tool(annotations=WRITE)
    async def renew_ad(ad_id: str, confirmation: str = "") -> dict:
        """Renew a listing so that it shows as new in the search again. mobile.de may charge for it."""
        return await write("renew_ad", {"ad_id": ad_id}, lambda: service.plan_renew_ad(ad_id), confirmation)

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_ad(ad_id: str, confirmation: str = "") -> dict:
        """Delete a listing with all its images. Cannot be undone."""
        return await write("delete_ad", {"ad_id": ad_id}, lambda: service.plan_delete_ad(ad_id), confirmation)

    @server.tool(annotations=WRITE)
    async def create_ad(ad: dict, images: list[dict] | None = None, confirmation: str = "") -> dict:
        """Create a listing. `ad` in mobile.de's listing format, at least vehicleClass, make and
        price.consumerPriceGross. `images`: each {"url": "https://..."} or {"base64": "..."}, JPG up to 2 MB, in
        the order they should appear."""
        args = {"ad": ad, "images": images or []}
        return await write("create_ad", args, lambda: service.plan_create_ad(ad, images), confirmation)

    @server.tool(annotations=DESTRUCTIVE)
    async def set_images(ad_id: str, images: list[dict], confirmation: str = "") -> dict:
        """Replace all images of a listing. Each {"url": "https://..."} or {"base64": "..."}, JPG up to 2 MB."""
        args = {"ad_id": ad_id, "images": images}
        return await write("set_images", args, lambda: service.plan_set_images(ad_id, images), confirmation)

    @server.tool(annotations=WRITE)
    async def send_direct_offer(ad_id: str, text: str, days: int, confirmation: str = "") -> dict:
        """Send a direct offer to everyone who parked the listing. 3 to 1000 characters, no phone numbers or
        e-mail addresses, valid 1 to 14 days."""
        args = {"ad_id": ad_id, "text": text, "days": days}
        return await write(
            "send_direct_offer", args, lambda: service.plan_send_direct_offer(ad_id, text, days), confirmation
        )

    @server.tool(annotations=WRITE)
    async def reply_rating(rating_id: str, comment: str, confirmation: str = "") -> dict:
        """Publish the dealer's reply to a rating (once per rating, 1 to 1000 characters)."""
        args = {"rating_id": rating_id, "comment": comment}
        return await write("reply_rating", args, lambda: service.plan_reply_rating(rating_id, comment), confirmation)

    @server.tool(annotations=WRITE)
    async def invite_rating(ad_id: str, buyer_email: str, confirmation: str = "") -> dict:
        """Invite a buyer of this vehicle to rate the dealer. Only with the buyer's consent."""
        args = {"ad_id": ad_id, "buyer_email": buyer_email}
        return await write("invite_rating", args, lambda: service.plan_invite_rating(ad_id, buyer_email), confirmation)

    @server.tool(annotations=WRITE)
    async def set_lead_status(lead_id: str, status: str, confirmation: str = "") -> dict:
        """Report the state of an inquiry back to mobile.de: IN_PROGRESS, SOLD, NOT_INTERESTED or SPAM."""
        args = {"lead_id": lead_id, "status": status}
        return await write("set_lead_status", args, lambda: service.plan_set_lead_status(lead_id, status), confirmation)

    return server
