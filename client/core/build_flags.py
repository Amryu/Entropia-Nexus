"""Helpers for runtime build-channel checks."""

from __future__ import annotations

import sys


def is_dev_build() -> bool:
    """Return True when running from source/non-frozen runtime."""
    return not getattr(sys, "frozen", False)
