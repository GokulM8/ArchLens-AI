"""Manual smoke test for the configured LLM provider (docs/LLM.md).

    python -m app.llm.smoke                    # one minimal text request
    python -m app.llm.smoke --list-models nemotron   # model ids visible to the key

Reads the same ARCHLENS_LLM_* settings as the server (and backend/.env). It
makes a real network call, so it is never run by the test suite or at startup.
The API key is never printed; provider errors are redacted.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import List, Optional

import httpx
from dotenv import load_dotenv

from app.llm.factory import LLMProviderFactory
from app.llm.provider import LLMRequest
from app.llm.redaction import redact

PROMPT = "Reply with exactly one word: pong"


def _key() -> str:
    return os.getenv("ARCHLENS_LLM_API_KEY", "")


def _describe_key(key: str) -> str:
    if not key:
        return "not set"
    shape = "nvapi-…" if key.startswith("nvapi-") else "set"
    return f"{shape} ({len(key)} characters)"


async def _ping() -> int:
    error = LLMProviderFactory.get_configuration_error()
    print(f"provider: {os.getenv('ARCHLENS_LLM_PROVIDER', '') or '(unset)'}")
    print(f"model:    {os.getenv('ARCHLENS_LLM_MODEL', '') or '(unset)'}")
    print(f"api key:  {_describe_key(_key())}")
    if error:
        print(f"configuration error: {redact(error, [_key()])}")
        return 2
    try:
        provider = LLMProviderFactory.create_provider()
    except ValueError as e:
        print(f"configuration error: {redact(str(e), [_key()])}")
        return 2
    print(f"base url: {getattr(provider, 'base_url', '(n/a)')}")

    response = await provider.generate(
        LLMRequest(system_prompt="You are a connectivity check.", user_prompt=PROMPT, context={}, temperature=0, max_tokens=256)
    )
    print(f"latency:  {response.latency_ms:.0f} ms")
    if not response.success:
        print(f"FAILED:   {response.error_type}: {redact(response.error, [_key()])}")
        return 1
    print(f"usage:    {response.usage}")
    print(f"answer:   {response.content.strip()[:200]!r}")
    print("OK")
    return 0


async def _list_models(contains: Optional[str]) -> int:
    base = (os.getenv("ARCHLENS_LLM_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
    if not _key():
        print("ARCHLENS_LLM_API_KEY is not set")
        return 2
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {_key()}"})
    except httpx.HTTPError as e:
        print(f"FAILED: could not reach {base}/models ({type(e).__name__})")
        return 1
    if r.status_code != 200:
        print(f"FAILED: HTTP {r.status_code}: {redact(r.text[:300], [_key()])}")
        return 1
    ids: List[str] = sorted(m.get("id", "") for m in r.json().get("data", []) if isinstance(m, dict))
    if contains:
        ids = [i for i in ids if contains.lower() in i.lower()]
    print("\n".join(ids) or "(no matching models)")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m app.llm.smoke", description=__doc__.split("\n\n")[0])
    parser.add_argument("--list-models", nargs="?", const="", metavar="FILTER", help="list model ids instead")
    args = parser.parse_args(argv)
    if args.list_models is not None:
        return asyncio.run(_list_models(args.list_models or None))
    return asyncio.run(_ping())


if __name__ == "__main__":
    sys.exit(main())
