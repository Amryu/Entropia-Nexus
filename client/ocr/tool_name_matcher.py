"""Matches OCR-read tool names against equippable items.

Subclasses ItemNameMatcher to load only equippable item types
(weapons, medical tools, chips, etc.) instead of the full item database.
This reduces the Levenshtein search space and avoids false matches
against non-equippable items like materials or furniture.

Also supports prefix matching for tool names truncated by the HUD
(ROI is 315px, long names like "Exceptional Kriegerum Mayhem G.2
Gauss Rifle, Perfected (L)" overflow).
"""

from __future__ import annotations

import time

from .item_name_matcher import (
    ItemNameMatcher,
    MatchResult,
    _levenshtein,
    _max_edit_distance,
    _normalize_for_matching,
)
from ..core.logger import get_logger

log = get_logger("ToolMatcher")

# Equippable item category getters on DataClient
_EQUIPPABLE_GETTERS = [
    "get_weapons",
    "get_medical_tools",
    "get_medical_chips",
    "get_misc_tools",
    "get_finders",
    "get_excavators",
    "get_refiners",
    "get_scanners",
    "get_teleportation_chips",
    "get_effect_chips",
    "get_implants",
    "get_amplifiers",
    "get_scopes_and_sights",
    "get_absorbers",
    "get_finder_amplifiers",
]

# Minimum prefix length for truncated name matching
MIN_PREFIX_LEN = 10


class ToolNameMatcher(ItemNameMatcher):
    """Matches OCR tool names against equippable items only.

    Overrides data loading to fetch only equippable categories.
    Adds prefix matching for names truncated by the HUD viewport.
    """

    def _refresh_if_needed(self):
        """Rebuild lookup tables from equippable items only."""
        now = time.monotonic()
        if self._loaded and (now - self._last_refresh) < 1800:
            return

        with self._lock:
            if self._loaded and (now - self._last_refresh) < 1800:
                return
            try:
                items = self._fetch_equippable_items()
                if items:
                    self._build_index(items)
                    self._last_refresh = time.monotonic()
                    self._loaded = True
            except Exception as e:
                log.warning("Failed to load equippable items: %s", e)
                if not self._loaded:
                    self._last_refresh = 0.0

    def _fetch_equippable_items(self) -> list[dict]:
        """Fetch all equippable items by calling each category getter."""
        items: list[dict] = []
        seen_names: set[str] = set()

        for getter_name in _EQUIPPABLE_GETTERS:
            getter = getattr(self._data_client, getter_name, None)
            if getter is None:
                continue
            try:
                category_items = getter()
                for item in (category_items or []):
                    name = item.get("Name", "")
                    if name and name not in seen_names:
                        seen_names.add(name)
                        items.append(item)
            except Exception as e:
                log.debug("Skipping %s: %s", getter_name, e)

        log.info("Loaded %d equippable items", len(items))
        return items

    def match_prefix(
        self,
        ocr_name: str,
        per_char_scores: list[float] | None = None,
        base_confidence: float = 1.0,
    ) -> MatchResult:
        """Match a potentially truncated OCR name using prefix matching.

        First tries exact/fuzzy matching via the parent class. If that
        fails and the OCR name is long enough, tries prefix matching
        against all known items.
        """
        # Try normal matching first
        result = self.match(ocr_name, per_char_scores, base_confidence)
        if result.edit_distance <= _max_edit_distance(
            _normalize_for_matching(ocr_name)
        ):
            return result

        # Prefix matching for truncated names
        self._refresh_if_needed()
        norm_ocr = _normalize_for_matching(ocr_name)

        if len(norm_ocr) < MIN_PREFIX_LEN:
            return result

        max_dist = _max_edit_distance(norm_ocr)
        candidates: list[str] = []

        for norm_item, original in self._name_by_normalized.items():
            # Item must be at least as long as the OCR text
            if len(norm_item) < len(norm_ocr):
                continue
            # Compare OCR text against the same-length prefix of the item
            prefix = norm_item[:len(norm_ocr)]
            dist = _levenshtein(norm_ocr, prefix, max_dist)
            if dist <= max_dist:
                candidates.append(original)

        if not candidates:
            return result

        if len(candidates) == 1:
            return MatchResult(
                matched_name=candidates[0],
                ocr_name=ocr_name,
                confidence=base_confidence * 0.85,
                edit_distance=0,
                ambiguous=False,
                candidates=candidates,
            )

        return MatchResult(
            matched_name=candidates[0],
            ocr_name=ocr_name,
            confidence=base_confidence * 0.70,
            edit_distance=0,
            ambiguous=True,
            candidates=candidates,
        )
