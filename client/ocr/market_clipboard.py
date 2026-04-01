"""
Clipboard monitor for market price data copied from the game's market value window.

The game provides Copy and Copy CSV buttons that place tab-separated market data
on the clipboard. This module detects such data and feeds it into the existing
market price ingestion pipeline via EVENT_MARKET_PRICE_SCAN.

Format (tab-separated, one header + N data rows):
  Item  Tier  Day Markup  Day Sales  Week Markup  Week Sales  ...  Decade Sales

Markup values: "125.5%" (percent mode), "3469.540" (absolute mode), "N/A", ">999999%"
Sales values:  "3.000 PEC", "1.890 PED", "25.260 PED", "0.000", "1.600K", "N/A"
"""

import logging
import re
from datetime import datetime, timezone

from PyQt6.QtWidgets import QApplication

from ..core.constants import EVENT_MARKET_PRICE_SCAN

log = logging.getLogger("Nexus.MarketClipboard")

HEADER_PREFIX = "Item\tTier\t"
EXPECTED_FIELDS = 12
PERIODS = ["1d", "7d", "30d", "365d", "3650d"]

# --- unit / suffix multipliers (value → PED) ---

UNIT_MULTIPLIERS = {
    "MPED": 1_000_000.0,
    "kPED": 1_000.0,
    "PED":  1.0,
    "PEC":  0.01,
    "mPEC": 0.00001,
    "uPEC": 0.00000001,
}
# Ordered longest-first so "kPED" is tried before "PED"
_UNIT_KEYS = sorted(UNIT_MULTIPLIERS, key=len, reverse=True)

BARE_SUFFIX_MULTIPLIERS = {
    "K": 1_000.0,
    "M": 1_000_000.0,
    "B": 1_000_000_000.0,
}

# --- field validation patterns ---

_RE_OVERFLOW = re.compile(r"^>999999%?$")
_RE_NA = re.compile(r"^N/A$", re.IGNORECASE)
_RE_TIER = re.compile(r"^\d{1,2}$")


# ---------------------------------------------------------------------------
# Value parsers
# ---------------------------------------------------------------------------

MARKUP_OVERFLOW = -1  # sentinel for ">999999%" overflow

def _parse_markup(raw, mode):
    """Parse a markup cell. Returns float, MARKUP_OVERFLOW (-1), or None."""
    raw = raw.strip()
    if not raw or _RE_NA.match(raw):
        return None
    if _RE_OVERFLOW.match(raw):
        return MARKUP_OVERFLOW
    s = raw.rstrip("%").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_sales(raw):
    """Parse a sales cell into PED. Returns float or None."""
    raw = raw.strip()
    if not raw or _RE_NA.match(raw):
        return None

    # Unit-based: "3.000 PEC", "1.890 PED", "25.260 kPED"
    for unit in _UNIT_KEYS:
        if raw.endswith(unit):
            num = raw[: -len(unit)].strip().replace(",", "")
            try:
                return float(num) * UNIT_MULTIPLIERS[unit]
            except ValueError:
                return None

    # Bare suffix: "1.600K"
    for suffix, mult in BARE_SUFFIX_MULTIPLIERS.items():
        if raw.endswith(suffix):
            num = raw[: -len(suffix)].replace(",", "")
            try:
                return float(num) * mult
            except ValueError:
                return None

    # Plain number (absolute-mode sales)
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _detect_markup_mode(fields):
    """Determine 'percent' or 'absolute' from the markup columns (indices 2,4,6,8,10)."""
    for i in range(5):
        val = fields[2 + i * 2].strip()
        if not val or _RE_NA.match(val) or _RE_OVERFLOW.match(val):
            continue
        if "%" in val:
            return "percent"
        return "absolute"
    return "percent"


def _is_tier(s):
    return bool(_RE_TIER.match(s.strip()))




# ---------------------------------------------------------------------------
# Item-level parser
# ---------------------------------------------------------------------------

def _parse_item_fields(fields):
    """Parse exactly 12 tab-separated fields into a market-price dict.

    Returns dict compatible with EVENT_MARKET_PRICE_SCAN, or None.
    """
    if len(fields) != EXPECTED_FIELDS:
        return None

    name = fields[0].strip()
    if not name:
        return None

    tier_str = fields[1].strip()
    if not _is_tier(tier_str):
        return None
    tier = int(tier_str)

    mode = _detect_markup_mode(fields)

    result = {
        "item_name": name,
        "tier": tier if tier > 0 else None,
        "markup_mode": mode,
        "ocr_confidence": 1.0,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "_source": "clipboard",
    }

    for i, period in enumerate(PERIODS):
        markup_raw = fields[2 + i * 2].strip()
        sales_raw = fields[3 + i * 2].strip()

        markup_val = _parse_markup(markup_raw, mode)
        sales_val = _parse_sales(sales_raw)

        result[f"markup_{period}"] = markup_val
        result[f"sales_{period}"] = sales_val

    return result


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------

def parse_market_clipboard(text):
    """Parse clipboard text as market price data.

    Returns list of dicts compatible with EVENT_MARKET_PRICE_SCAN,
    or empty list if the text is not market data.
    """
    if not text or HEADER_PREFIX not in text:
        return []

    lines = text.strip().splitlines()
    if not lines or not lines[0].strip().startswith(HEADER_PREFIX):
        return []

    items = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != EXPECTED_FIELDS:
            continue
        item = _parse_item_fields(fields)
        if item:
            items.append(item)

    return items


# ---------------------------------------------------------------------------
# Qt clipboard monitor
# ---------------------------------------------------------------------------

class MarketClipboardMonitor:
    """Monitors the system clipboard for market price data from the game.

    Connects to QClipboard.dataChanged to detect when the user copies
    market data via the game's Copy / Copy CSV buttons.
    """

    def __init__(self, event_bus):
        self._event_bus = event_bus
        self._running = False
        self._clipboard = None
        self._last_text = ""

    def start(self):
        if self._running:
            return
        self._running = True
        self._clipboard = QApplication.clipboard()
        if self._clipboard:
            self._clipboard.dataChanged.connect(self._on_clipboard_changed)
            log.info("Market clipboard monitor started")

    def stop(self):
        self._running = False
        if self._clipboard:
            try:
                self._clipboard.dataChanged.disconnect(self._on_clipboard_changed)
            except (TypeError, RuntimeError):
                pass
        self._clipboard = None
        log.info("Market clipboard monitor stopped")

    def _on_clipboard_changed(self):
        if not self._running or not self._clipboard:
            return

        text = self._clipboard.text()
        if not text or text == self._last_text:
            return
        self._last_text = text

        if HEADER_PREFIX not in text:
            return

        items = parse_market_clipboard(text)
        if not items:
            return

        from .market_heuristics import heuristic_confidence_penalty

        log.info("Parsed %d market price item(s) from clipboard", len(items))
        for item in items:
            # Clipboard data is exact (ocr_confidence=1.0) but apply
            # heuristic checks (sales monotonicity, markup stability)
            penalty = heuristic_confidence_penalty(item)
            item["ocr_confidence"] = 1.0 * penalty
            if penalty < 1.0:
                item["heuristic_penalty"] = penalty
            log.debug("  %s (tier %s, mode=%s, conf=%.2f)",
                       item["item_name"], item.get("tier"),
                       item.get("markup_mode"), item["ocr_confidence"])
            self._event_bus.publish(EVENT_MARKET_PRICE_SCAN, item)
