"""Helpers for validating identifiers used by the Sherlock API."""

from __future__ import annotations

import re

__all__ = ["is_valid_uuid32"]

_UUID32_RE = re.compile(r"[a-fA-F0-9]{32}")


def is_valid_uuid32(s: str) -> bool:
    """Check whether ``s`` is a 32-character UUID (hex only, no hyphens).

    Sherlock identifiers (case, batch, image and process ids) use this form.
    The client never enforces it; call this yourself if you want to validate
    ids before sending them.

    >>> is_valid_uuid32("8957CBFC162F6A1F713F269CE8BD6F8A")
    True
    >>> is_valid_uuid32("not-a-uuid")
    False
    """
    return bool(_UUID32_RE.fullmatch(s))
