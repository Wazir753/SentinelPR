"""Broken math helpers for Phase 2 patch-generation tests."""

from __future__ import annotations


def broken_add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a - b  # bug: should add
