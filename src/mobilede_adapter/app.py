"""One process, two fronts. `serve` speaks HTTP (MCP under /mcp, Vilikon's paths under /ki/), `stdio` speaks MCP
over standard input and output for a local client.

Who may reach what:
- /mcp needs `Authorization: Bearer <ADAPTER_TOKEN>` when a token is set. Without a token the server only listens on
  the loopback address. Inside Vilikon /mcp is off unless a token is set: colleagues use /ki/.
- /ki/ is on inside Vilikon (BASE_PATH below /werkzeug/) or with MOBILE_DE_KI=on. Its writes need the cockpit's
  approval header (vilikon.py).
"""

from __future__ import annotations

import hmac
import ipaddress

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from . import mcp_server, vilikon
from .config import Settings
from .service import Service


class TokenGate:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self.token = app, token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith("/mcp"):
            given = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if not hmac.compare_digest(given, f"Bearer {self.token}"):
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def http_app(settings: Settings, service: Service | None = None) -> ASGIApp:
    service = service or Service(settings)
    mcp_on = bool(settings.token) or (not settings.in_vilikon and loopback(settings.host))
    if not mcp_on and not settings.ki:
        raise SystemExit("Refusing to serve /mcp on a public address without ADAPTER_TOKEN.")
    ki = vilikon.routes(service) if settings.ki else []
    if mcp_on:
        app = mcp_server.build(service).streamable_http_app(host=settings.host)
        app.router.routes[0:0] = ki
    else:
        app = Starlette(routes=ki)
    return TokenGate(app, settings.token) if settings.token else app
