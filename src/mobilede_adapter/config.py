"""Settings, read from the environment only. Nothing here is ever written to a file or a log."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PRODUCTION = "https://services.mobile.de"
SANDBOX = "https://services.sandbox.mobile.de"
WRITE_MODES = ("off", "confirm", "on")


def _on(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "on", "yes", "true", "ja")


@dataclass(frozen=True)
class Settings:
    user: str = ""
    password: str = field(default="", repr=False)
    seller_id: str = ""
    sandbox: bool = False
    writes: str = "confirm"
    lang: str = "de"
    data_dir: Path = Path(".")
    token: str = field(default="", repr=False)
    host: str = "127.0.0.1"
    port: int = 8080
    base_path: str = ""
    ki: bool = False

    @property
    def base_url(self) -> str:
        return SANDBOX if self.sandbox else PRODUCTION

    @property
    def in_vilikon(self) -> bool:
        """Vilikon's tool runtime gives every tool a BASE_PATH below /werkzeug/."""
        return self.base_path.startswith("/werkzeug/")

    @property
    def configured(self) -> bool:
        return bool(self.user and self.password)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        writes = (e.get("MOBILE_DE_WRITES") or "confirm").strip().lower()
        base_path = (e.get("BASE_PATH") or "").strip()
        return cls(
            user=(e.get("MOBILE_DE_USER") or "").strip(),
            password=e.get("MOBILE_DE_PASSWORD") or "",
            seller_id=(e.get("MOBILE_DE_SELLER_ID") or "").strip(),
            sandbox=_on(e.get("MOBILE_DE_SANDBOX")),
            writes=writes if writes in WRITE_MODES else "confirm",
            lang="en" if (e.get("MOBILE_DE_LANG") or "").strip().lower().startswith("en") else "de",
            data_dir=Path(e.get("DATA_DIR") or "."),
            token=(e.get("ADAPTER_TOKEN") or "").strip(),
            host=(e.get("HOST") or "127.0.0.1").strip(),
            port=int(e.get("PORT") or 8080),
            base_path=base_path,
            ki=_on(e.get("MOBILE_DE_KI")) or base_path.startswith("/werkzeug/"),
        )
