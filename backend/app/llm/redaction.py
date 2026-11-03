"""Remove credentials from text before it reaches logs, responses or reports."""

from __future__ import annotations

import re
from typing import Iterable, Optional

REDACTED = "[REDACTED]"

# Key shapes we can recognise even when the configured key is unknown
# (e.g. echoed back by a provider for a different key).
_KEY_PATTERNS = (
    re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
)


def redact(text: Optional[str], secrets: Iterable[Optional[str]] = ()) -> str:
    """Return ``text`` with every given secret and every key-like token masked."""
    if not text:
        return ""
    out = str(text)
    # Longest first, so a secret that contains another is masked whole.
    for secret in sorted({s for s in secrets if s and len(s) >= 4}, key=len, reverse=True):
        out = out.replace(secret, REDACTED)
    for pattern in _KEY_PATTERNS:
        if pattern.groups:
            out = pattern.sub(lambda m: m.group(1) + REDACTED, out)
        else:
            out = pattern.sub(REDACTED, out)
    return out
