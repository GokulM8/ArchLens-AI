"""Production entry point: ``python -m app.serve``.

Binds ``0.0.0.0`` on ``$PORT`` (set by Render and most PaaS hosts), falling
back to 8000 for Docker Compose and local runs. Runs a single uvicorn worker:
the upload/LLM rate limits and the analysis concurrency limit live in process
memory and are only correct with one process.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional

DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"


def resolve_port(env: Optional[Mapping[str, str]] = None) -> int:
    """``$PORT`` when it is a valid TCP port, else 8000."""
    env = os.environ if env is None else env
    raw = (env.get("PORT") or "").strip()
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


def resolve_host(env: Optional[Mapping[str, str]] = None) -> str:
    env = os.environ if env is None else env
    return (env.get("HOST") or "").strip() or DEFAULT_HOST


def uvicorn_options(env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    return {
        "host": resolve_host(env),
        "port": resolve_port(env),
        "workers": 1,
        # Trust X-Forwarded-Proto from the platform proxy. The client address
        # used for rate limiting is resolved separately (safeguards.client_key)
        # because uvicorn trusts the left-most, client-controlled X-Forwarded-For
        # entry when every proxy is trusted.
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        "timeout_keep_alive": 5,
        "log_level": os.getenv("ARCHLENS_LOG_LEVEL", "info").lower(),
    }


def main() -> None:  # pragma: no cover - exercised by the container
    import uvicorn

    uvicorn.run("app.api:app", **uvicorn_options())


if __name__ == "__main__":  # pragma: no cover
    main()
