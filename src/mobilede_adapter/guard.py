"""Nothing changes at mobile.de without a second look.

The adapter runs on its own as well, behind any MCP client. So a write never happens on the first call unless the
operator chose `MOBILE_DE_WRITES=on`: with `confirm` (the default) the first call returns a preview and a short-lived
code, and only a second call with the same values and that code carries it out. In Vilikon the owner's approval card
is that second look, and the write route checks for it (see vilikon.py).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .texts import Texts

TTL_S = 600


@dataclass
class Plan:
    """A write, prepared: what it will do in one sentence, and the call that does it (returns a sentence)."""

    preview: str
    run: Callable[[], Awaitable[str]]


def fingerprint(name: str, args: dict) -> str:
    return hashlib.sha256(
        json.dumps([name, args], sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


class WriteGuard:
    def __init__(self, mode: str, texts: Texts, clock: Callable[[], float] = time.monotonic) -> None:
        self.mode = mode
        self.t = texts
        self._clock = clock
        self._pending: dict[str, tuple[str, float]] = {}

    async def apply(self, name: str, args: dict, plan: Callable[[], Awaitable[Plan]], confirmation: str = "") -> dict:
        if self.mode == "off":
            return {"done": False, "text": self.t("writes_off")}
        p = await plan()  # checks the values and reads the current state, even when it then waits for a code
        if self.mode == "on":
            return {"done": True, "text": await p.run()}
        self._forget_expired()
        key = fingerprint(name, args)
        if confirmation:
            entry = self._pending.get(confirmation.strip())
            if entry is None or entry[0] != key:
                return {"done": False, "text": self.t("confirm_wrong")}
            del self._pending[confirmation.strip()]
            return {"done": True, "text": await p.run()}
        code = secrets.token_hex(3)
        self._pending[code] = (key, self._clock() + TTL_S)
        return {
            "done": False,
            "preview": p.preview,
            "confirmation": code,
            "text": self.t("confirm_needed", code=code, minutes=TTL_S // 60),
        }

    def _forget_expired(self) -> None:
        now = self._clock()
        for code in [c for c, (_, until) in self._pending.items() if until < now]:
            del self._pending[code]
