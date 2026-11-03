"""Limits for endpoints that call the external LLM provider.

Every LLM call costs money and sends repository context off the server, so
each one passes through ``llm_guard``:

- per-client rate limit: ``ARCHLENS_LLM_RATE_PER_MINUTE`` (default 6)
- server-wide daily quota (UTC day): ``ARCHLENS_LLM_DAILY_QUOTA`` (default 200)
- concurrent calls: ``ARCHLENS_LLM_MAX_CONCURRENT`` (default 2)

Uploads are limited by ``UploadGuard`` (per client and server-wide, per hour).

State is in process memory: it resets on restart and is per replica, which
matches the single-replica deployment. Clients are keyed by IP address
(see ``client_key`` for how it is resolved behind proxies).
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import AsyncIterator, Callable, Deque, Iterator

from fastapi import Request

from app.analyses.errors import APIError

_WINDOW_S = 60.0
# Bound memory when many distinct clients appear; the oldest are forgotten.
_MAX_TRACKED_CLIENTS = 10_000


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


class LLMGuard:
    def __init__(
        self,
        rate_per_minute: int = 6,
        daily_quota: int = 200,
        max_concurrent: int = 2,
        clock: Callable[[], float] = time.time,
    ):
        self.rate_per_minute = max(1, rate_per_minute)
        self.daily_quota = max(1, daily_quota)
        self.max_concurrent = max(1, max_concurrent)
        self._clock = clock
        self._lock = threading.Lock()
        self._calls: "OrderedDict[str, Deque[float]]" = OrderedDict()
        self._day = ""
        self._day_count = 0
        self._active = 0

    @classmethod
    def from_env(cls) -> "LLMGuard":
        return cls(
            rate_per_minute=_env_int("ARCHLENS_LLM_RATE_PER_MINUTE", 6),
            daily_quota=_env_int("ARCHLENS_LLM_DAILY_QUOTA", 200),
            max_concurrent=_env_int("ARCHLENS_LLM_MAX_CONCURRENT", 2),
        )

    def acquire(self, client: str) -> None:
        """Admit one call for ``client`` or raise 429; pair with ``release``."""
        now = self._clock()
        with self._lock:
            day = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")
            if day != self._day:
                self._day, self._day_count = day, 0
            if self._day_count >= self.daily_quota:
                raise APIError(
                    429,
                    "llm_quota_exceeded",
                    "The Copilot's daily usage limit for this server has been reached. Try again tomorrow.",
                    headers={"Retry-After": "3600"},
                )

            calls = self._calls.get(client)
            if calls is None:
                calls = self._calls[client] = deque()
                while len(self._calls) > _MAX_TRACKED_CLIENTS:
                    self._calls.popitem(last=False)
            else:
                self._calls.move_to_end(client)
            while calls and now - calls[0] >= _WINDOW_S:
                calls.popleft()
            if len(calls) >= self.rate_per_minute:
                wait = max(1, int(_WINDOW_S - (now - calls[0])) + 1)
                raise APIError(
                    429,
                    "llm_rate_limited",
                    f"Too many Copilot requests. Wait {wait} seconds and try again.",
                    headers={"Retry-After": str(wait)},
                )

            if self._active >= self.max_concurrent:
                raise APIError(
                    429,
                    "llm_busy",
                    "The Copilot is busy with other requests. Try again shortly.",
                    headers={"Retry-After": "5"},
                )

            calls.append(now)
            self._day_count += 1
            self._active += 1

    def release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)


@lru_cache(maxsize=1)
def get_llm_guard() -> LLMGuard:
    return LLMGuard.from_env()


class UploadGuard:
    """Sliding one-hour limits on analysis uploads.

    - per client: ``ARCHLENS_UPLOAD_RATE_PER_HOUR`` (default 20)
    - whole server: ``ARCHLENS_UPLOAD_GLOBAL_PER_HOUR`` (default 120); this
      cap holds even if client addresses are spoofed or shared.

    Attempts are counted when admitted, whether or not the analysis succeeds,
    because rejected archives still cost upload bandwidth and disk. ``0``
    disables a limit.
    """

    _WINDOW = 3600.0

    def __init__(self, per_client: int = 20, global_limit: int = 120, clock: Callable[[], float] = time.time):
        self.per_client = max(0, per_client)
        self.global_limit = max(0, global_limit)
        self._clock = clock
        self._lock = threading.Lock()
        self._calls: "OrderedDict[str, Deque[float]]" = OrderedDict()
        self._all: Deque[float] = deque()

    @classmethod
    def from_env(cls) -> "UploadGuard":
        return cls(
            per_client=_env_int("ARCHLENS_UPLOAD_RATE_PER_HOUR", 20),
            global_limit=_env_int("ARCHLENS_UPLOAD_GLOBAL_PER_HOUR", 120),
        )

    def _retry_after(self, oldest: float, now: float) -> str:
        return str(max(1, int(self._WINDOW - (now - oldest)) + 1))

    def admit(self, client: str) -> None:
        now = self._clock()
        with self._lock:
            while self._all and now - self._all[0] >= self._WINDOW:
                self._all.popleft()
            calls = self._calls.get(client)
            if calls is None:
                calls = self._calls[client] = deque()
                while len(self._calls) > _MAX_TRACKED_CLIENTS:
                    self._calls.popitem(last=False)
            else:
                self._calls.move_to_end(client)
            while calls and now - calls[0] >= self._WINDOW:
                calls.popleft()

            if self.per_client and len(calls) >= self.per_client:
                raise APIError(
                    429,
                    "upload_rate_limited",
                    "Too many uploads from your address. Try again later.",
                    headers={"Retry-After": self._retry_after(calls[0], now)},
                )
            if self.global_limit and len(self._all) >= self.global_limit:
                raise APIError(
                    429,
                    "server_upload_limit",
                    "This server has reached its upload limit for now. Try again later.",
                    headers={"Retry-After": self._retry_after(self._all[0], now)},
                )
            calls.append(now)
            self._all.append(now)


@lru_cache(maxsize=1)
def get_upload_guard() -> UploadGuard:
    return UploadGuard.from_env()


def client_key(request: Request) -> str:
    """The address rate limits are keyed on.

    By default this is the connecting peer as uvicorn reports it, which is
    right behind the bundled nginx (it overwrites X-Forwarded-For). When the
    app sits directly behind a platform proxy that *appends* to
    X-Forwarded-For (Render), set ``ARCHLENS_TRUSTED_PROXY_HOPS`` to the number
    of such proxies: the entry that many places from the right is the one the
    outermost trusted proxy saw, and entries further left are client-supplied
    and ignored.
    """
    hops = _env_int("ARCHLENS_TRUSTED_PROXY_HOPS", 0)
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


@contextmanager
def llm_slot(client: str) -> Iterator[None]:
    """Hold one admitted LLM call for ``client`` (429 when over a limit)."""
    guard = get_llm_guard()
    guard.acquire(client)
    try:
        yield
    finally:
        guard.release()


async def llm_guard(request: Request) -> AsyncIterator[None]:
    """FastAPI dependency: admit the request under the LLM limits for its duration."""
    with llm_slot(client_key(request)):
        yield
