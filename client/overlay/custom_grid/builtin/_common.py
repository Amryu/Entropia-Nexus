"""Shared font-scaling helpers for built-in GridWidget implementations.

All ``font_*(h)`` functions map the pixel *height* of a widget cell to an
appropriate font size so that content scales smoothly across the S/M/L
tile-size settings.
"""

from __future__ import annotations


def font_label(h: int) -> int:
    """Small supporting / key text."""
    if h < 50:  return 8
    if h < 80:  return 9
    if h < 120: return 10
    return 11


def font_value(h: int) -> int:
    """Data / value text (medium emphasis)."""
    if h < 50:  return 10
    if h < 80:  return 11
    if h < 120: return 13
    return 15


def font_big(h: int) -> int:
    """Large primary display (clock time, timer, stat value)."""
    if h < 50:  return 14
    if h < 80:  return 18
    if h < 120: return 24
    return 32


def font_title(h: int) -> int:
    """Section title / widget name."""
    if h < 50:  return 9
    if h < 80:  return 10
    if h < 120: return 11
    return 12


# Common colour tokens
C_ACCENT  = "#00ccff"
C_TEXT    = "#e0e0e0"
C_DIM     = "#888888"
C_IDLE    = "#666666"
C_GREEN   = "#aaddaa"
C_BLUE    = "#80b8ff"
