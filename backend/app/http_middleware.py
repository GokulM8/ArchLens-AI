"""ASGI middleware for running the API directly on the public internet.

Without nginx in front (e.g. on Render) the app itself must:

- cap request bodies while they stream in, including chunked uploads with no
  Content-Length, before Starlette spools them to disk
  (``BodySizeLimitMiddleware``);
- turn unexpected exceptions into a generic JSON 500 that leaks no internals
  and still passes through the CORS middleware, so browsers can read it
  (``SafeErrorMiddleware``);
- resolve the CORS allow-list from configuration (``cors_origins``).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Callable, List, Mapping, Optional
from urllib.parse import urlsplit

logger = logging.getLogger("archlens.http")


def _json_response(status: int, body: dict) -> tuple[dict, dict]:
    payload = json.dumps(body).encode("utf-8")
    start = {
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode()),
        ],
    }
    return start, {"type": "http.response.body", "body": payload}


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """413 once a request body exceeds ``max_bytes()`` (read per request)."""

    def __init__(self, app, max_bytes: Callable[[], int]):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.max_bytes()
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length", b"").decode("latin1")
        if declared.isdigit() and int(declared) > limit:
            return await self._reject(send, limit)

        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send, limit: int):
        start, body = _json_response(
            413,
            {
                "detail": f"Request body exceeds the {max(1, limit // (1024 * 1024))} MB limit.",
                "code": "upload_too_large",
            },
        )
        await send(start)
        await send(body)


class SafeErrorMiddleware:
    """Generic JSON 500 for unhandled exceptions; details go to the log only."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            start, body = _json_response(
                500, {"detail": "Internal server error.", "code": "internal_error"}
            )
            await send(start)
            await send(body)


def _normalize_origin(value: str) -> Optional[str]:
    """``scheme://host[:port]`` for an http(s) origin, else None."""
    value = value.strip().rstrip("/")
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path or parts.query:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def cors_origins(env: Optional[Mapping[str, str]] = None) -> List[str]:
    """Allowed browser origins from ``FRONTEND_ORIGIN`` and ``ARCHLENS_CORS_ORIGINS``.

    Both accept comma-separated origins. ``*`` and anything that is not an
    http(s) origin are ignored with a warning: the API is never opened to every
    origin.
    """
    env = os.environ if env is None else env
    raw = ",".join([env.get("FRONTEND_ORIGIN", ""), env.get("ARCHLENS_CORS_ORIGINS", "")])
    origins: List[str] = []
    for item in raw.split(","):
        if not item.strip():
            continue
        origin = _normalize_origin(item)
        if origin is None:
            logger.warning("Ignoring invalid CORS origin %r (use e.g. https://app.example.com)", item.strip())
        elif origin not in origins:
            origins.append(origin)
    return origins
