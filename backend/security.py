from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass


def create_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def token_matches(candidate: str, expected: str) -> bool:
    return bool(candidate and expected and hmac.compare_digest(candidate, expected))


@dataclass
class RateWindow:
    started_at: float
    count: int


class RateLimiter:
    def __init__(self, limit: int = 120, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._entries: dict[str, RateWindow] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_cleanup >= self.window_seconds:
                self._entries = {
                    entry_key: entry for entry_key, entry in self._entries.items()
                    if now - entry.started_at < self.window_seconds
                }
                self._last_cleanup = now
            current = self._entries.get(key)
            if current is None or now - current.started_at >= self.window_seconds:
                self._entries[key] = RateWindow(now, 1)
                return True
            current.count += 1
            return current.count <= self.limit
