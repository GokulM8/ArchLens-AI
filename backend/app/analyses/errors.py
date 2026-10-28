"""Consistent error responses for the /v1 API: ``{"detail": ..., "code": ...}``."""

from __future__ import annotations

from typing import Any, Dict, Optional


class APIError(Exception):
    """An error with an HTTP status and a stable machine-readable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers
        self.extra = extra or {}

    def body(self) -> Dict[str, Any]:
        return {"detail": self.detail, "code": self.code, **self.extra}
