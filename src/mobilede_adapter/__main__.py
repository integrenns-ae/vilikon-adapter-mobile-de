"""`python -m mobilede_adapter stdio` for a local MCP client, `python -m mobilede_adapter serve` for HTTP."""

from __future__ import annotations

import asyncio
import sys

from .config import Settings


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    mode = args[0] if args else "serve"
    settings = Settings.from_env()
    if mode == "stdio":
        from . import mcp_server
        from .service import Service

        asyncio.run(mcp_server.build(Service(settings)).run_stdio_async())
    elif mode == "serve":
        import uvicorn

        from .app import http_app

        uvicorn.run(
            http_app(settings), host=settings.host, port=settings.port, log_level="warning", access_log=False
        )  # no access log
    else:
        sys.exit("usage: python -m mobilede_adapter [serve|stdio]")


if __name__ == "__main__":
    main()
