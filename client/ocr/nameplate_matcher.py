"""Mob nameplate matcher for target lock OCR.

Matches noisy OCR text against the known mob/maturity database. Designed
to handle the typical OCR errors when reading text rendered without a
darker backdrop:

- Spurious internal whitespace ("Gokibu sagi" instead of "Gokibusagi")
- Leading and trailing junk ("IPAR AL Ari L15Go kibusagi Guardian RRA8")
- Single-character errors ("Gokibi sagi" -> Gokibusagi)
- Missing or wrong level prefix
- Word reorder is implicitly handled by compact normalization

Uses **compact matching**: both OCR text and database entries are
normalized to lowercase alphanumerics with all whitespace removed, then
compared by substring containment first and bounded Levenshtein second.

Database entries can be filtered by planet for faster, more accurate
matching - in the common case the player is on a single planet and only
sees mobs that spawn there. The full index is still used as a fallback
for events / cross-planet spawns.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

from ..core.logger import get_logger

log = get_logger("NameplateMatcher")

# Refresh the index from the API every 30 minutes
_REFRESH_INTERVAL = 1800.0

# Default minimum match score (0..1)
DEFAULT_MIN_SCORE = 0.65

# Permissive level prefix: requires an actual L-like letter (l/L/I/i),
# optionally preceded by '1' (OCR misread).  We do NOT accept a bare leading
# digit as a level - '15 Foo' should NOT be parsed as level 5.
_LEVEL_RE = re.compile(
    r"^[^a-zA-Z0-9]*(?:1[\s]?)?[lLiI][\s]?(\d{1,4})",
    re.UNICODE,
)
_COMPACT_RE = re.compile(r"[^a-z0-9]+")
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def _compact(text: str) -> str:
    """Normalize for matching: lowercase alphanumeric, no whitespace."""
    return _COMPACT_RE.sub("", text.lower())


def _strip_paren(name: str) -> str:
    """Strip parenthetical disambiguators like 'Atrox (Calypso)' -> 'Atrox'."""
    return _PAREN_RE.sub(" ", name).strip()


def parse_level(text: str) -> tuple[int | None, str]:
    """Strip a leading level token (L42, l 42, I15, 1L15, ...) and return rest."""
    m = _LEVEL_RE.match(text)
    if m:
        try:
            return int(m.group(1)), text[m.end():].strip()
        except ValueError:
            pass
    return None, text


def _bounded_levenshtein(a: str, b: str, max_dist: int) -> int:
    """Levenshtein distance with early termination at max_dist + 1."""
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        row_min = i
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_dist:
            return max_dist + 1
        prev = curr
    return prev[lb]


@dataclass
class NameplateEntry:
    """A single known mob nameplate string."""
    full: str            # display nameplate (mob name + maturity, etc.)
    mob_name: str
    maturity_name: str
    level: int | None    # database-stored level (often outdated)
    planet: str          # canonical planet name (lowercased) or "" if unknown
    compact: str         # lowercase alphanumeric, no spaces (for matching)


@dataclass
class NameMatch:
    """Result of a successful nameplate match."""
    nameplate: str
    mob_name: str
    maturity_name: str
    level: int | None
    score: float
    raw_ocr: str


def _build_entries(mobs: list[dict]) -> list[NameplateEntry]:
    """Build NameplateEntry objects from the raw mob list returned by the API."""
    entries: list[NameplateEntry] = []
    seen: set[str] = set()
    for mob in mobs:
        raw_mob_name = (mob.get("Name") or "").strip()
        mob_name = _strip_paren(raw_mob_name)
        if not mob_name:
            continue
        planet = ((mob.get("Planet") or {}).get("Name") or "").strip().lower()
        maturities = mob.get("Maturities") or []
        for mat in maturities:
            mat_name = _strip_paren((mat.get("Name") or "").strip())
            mode = mat.get("NameMode") or "Empty"
            level = (mat.get("Properties") or {}).get("Level")
            if mode == "Suffix":
                full = f"{mob_name} {mat_name}".strip()
            elif mode == "Verbatim":
                full = mat_name
            else:  # Empty / None
                full = mob_name
            if not full:
                continue
            key = _compact(full)
            if not key or key in seen:
                continue
            seen.add(key)
            entries.append(NameplateEntry(
                full=full,
                mob_name=mob_name,
                maturity_name=mat_name if mode == "Suffix" else "",
                level=int(level) if isinstance(level, (int, float)) else None,
                planet=planet,
                compact=key,
            ))
        if not maturities:
            key = _compact(mob_name)
            if key and key not in seen:
                seen.add(key)
                entries.append(NameplateEntry(
                    full=mob_name, mob_name=mob_name, maturity_name="",
                    level=None, planet=planet, compact=key,
                ))
    return entries


def _score_against(ocr_compact: str,
                   entries: list[NameplateEntry]) -> tuple[NameplateEntry, float] | None:
    """Score the OCR compact form against a list of entries; return best."""
    best: tuple[NameplateEntry, float] | None = None
    for entry in entries:
        ek = entry.compact
        elen = len(ek)
        if elen < 3:
            continue

        # Fast path 1: entry compact appears as substring of OCR
        if ek in ocr_compact:
            score = 0.9 + 0.1 * (elen / max(elen, len(ocr_compact)))
            if best is None or score > best[1]:
                best = (entry, score)
            continue
        # Fast path 2: OCR is substring of entry (truncated read)
        if ocr_compact in ek and len(ocr_compact) >= elen * 0.6:
            score = 0.85 * (len(ocr_compact) / elen)
            if best is None or score > best[1]:
                best = (entry, score)
            continue

        # Fuzzy fallback: bounded Levenshtein (~17% allowed edit distance)
        max_dist = max(2, elen // 6)
        window = ocr_compact
        if len(window) > elen + max_dist:
            window = ocr_compact[:elen + max_dist]
        dist = _bounded_levenshtein(window, ek, max_dist)
        if dist <= max_dist:
            score = 1.0 - (dist / elen)
            if best is None or score > best[1]:
                best = (entry, score)
    return best


class NameplateMatcher:
    """Matches OCR-read nameplates against the mob database.

    Thread-safe.  Refreshes from the API periodically.  Supports an
    optional planet filter that restricts matches to mobs known to spawn
    on the player's current planet first, with full-database fallback
    for off-planet spawns (events, raids, etc.).
    """

    def __init__(self, data_client, min_score: float = DEFAULT_MIN_SCORE):
        self._data_client = data_client
        self._min_score = min_score
        self._lock = threading.Lock()
        self._all_entries: list[NameplateEntry] = []
        self._planet_entries: list[NameplateEntry] = []
        self._planet: str = ""
        self._last_refresh: float = 0.0
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_planet(self, planet: str | None) -> None:
        """Restrict primary matching to mobs known to spawn on *planet*.

        Pass None or "" to use the full database with no planet filter.
        Matching always falls back to the full database if no planet
        match is found, so off-planet spawns (events) still work.
        """
        normalized = (planet or "").strip().lower()
        with self._lock:
            if normalized == self._planet:
                return
            self._planet = normalized
            self._rebuild_planet_filter_locked()
        log.info("Planet filter set to %r (%d entries)",
                 planet, len(self._planet_entries))

    def match(self, raw_text: str) -> NameMatch | None:
        """Match raw OCR text against the nameplate database.

        Returns the best match (planet-filtered first, full-db fallback)
        or None if no entry scores above the minimum threshold.
        """
        if not raw_text:
            return None

        self._refresh_if_needed()

        level, rest = parse_level(raw_text)
        ocr_compact = _compact(rest)
        if len(ocr_compact) < 3:
            return None

        with self._lock:
            planet_entries = self._planet_entries
            all_entries = self._all_entries

        # Try planet-filtered list first
        best = None
        if planet_entries:
            best = _score_against(ocr_compact, planet_entries)
            if best and best[1] >= self._min_score:
                return self._make_match(best, level, raw_text)

        # Fall back to the full database
        full_best = _score_against(ocr_compact, all_entries)
        if full_best and full_best[1] >= self._min_score:
            return self._make_match(full_best, level, raw_text)

        # Surface even sub-threshold planet match if it beat the fallback
        if best is not None and (full_best is None or best[1] >= full_best[1]):
            if best[1] >= self._min_score * 0.8:
                return self._make_match(best, level, raw_text)
        return None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_entries(self) -> int:
        return len(self._all_entries)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_match(self, scored: tuple[NameplateEntry, float],
                    level: int | None, raw_text: str) -> NameMatch:
        entry, score = scored
        return NameMatch(
            nameplate=entry.full,
            mob_name=entry.mob_name,
            maturity_name=entry.maturity_name,
            # Prefer OCR-extracted level (DB has many wrong levels)
            level=level if level is not None else entry.level,
            score=score,
            raw_ocr=raw_text,
        )

    def _refresh_if_needed(self) -> None:
        now = time.monotonic()
        if self._loaded and (now - self._last_refresh) < _REFRESH_INTERVAL:
            return
        with self._lock:
            if self._loaded and (now - self._last_refresh) < _REFRESH_INTERVAL:
                return
            try:
                mobs = self._data_client.get_mobs()
                if not mobs:
                    if not self._loaded:
                        # Don't repeatedly hammer the API on first failure
                        self._last_refresh = now
                    return
                self._all_entries = _build_entries(mobs)
                self._rebuild_planet_filter_locked()
                self._last_refresh = now
                self._loaded = True
                log.info("Loaded %d nameplate entries from %d mobs",
                         len(self._all_entries), len(mobs))
            except Exception as e:
                log.warning("Failed to refresh nameplate index: %s", e)
                if not self._loaded:
                    self._last_refresh = now

    def _rebuild_planet_filter_locked(self) -> None:
        if not self._planet:
            self._planet_entries = []
            return
        self._planet_entries = [
            e for e in self._all_entries if e.planet == self._planet
        ]
