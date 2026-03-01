"""Maps page — full-canvas interactive planet maps with floating controls."""

from __future__ import annotations

import math
import os
import re
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit,
    QPushButton, QLabel, QApplication, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QPixmap

import requests

from ..widgets.map_canvas import MapCanvas
from ..theme import PRIMARY, SECONDARY, BORDER, HOVER, ACCENT, TEXT, TEXT_MUTED, MAIN_DARK
from ...core.logger import get_logger

log = get_logger("MapsPage")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OVERLAY_BG = "rgba(17, 17, 23, 0.88)"
_OVERLAY_BORDER = BORDER
_OVERLAY_RADIUS = 6

# Planet groups (mirrors MapList.svelte)
PLANET_GROUPS: list[tuple[str, list[dict]]] = [
    ("Calypso", [
        {"Name": "Calypso", "slug": "calypso"},
        {"Name": "Setesh", "slug": "setesh"},
        {"Name": "ARIS", "slug": "aris"},
        {"Name": "Crystal Palace", "slug": "crystalpalace"},
        {"Name": "Asteroid F.O.M.A", "slug": "asteroidfoma"},
    ]),
    ("Arkadia", [
        {"Name": "Arkadia", "slug": "arkadia"},
        {"Name": "Arkadia Underground", "slug": "arkadiaunderground"},
        {"Name": "Arkadia Moon", "slug": "arkadiamoon"},
    ]),
    ("Cyrene", [
        {"Name": "Cyrene", "slug": "cyrene"},
    ]),
    ("Rocktropia", [
        {"Name": "ROCKtropia", "slug": "rocktropia"},
        {"Name": "HELL", "slug": "hell"},
        {"Name": "Hunt the THING", "slug": "huntthething"},
        {"Name": "Secret Island", "slug": "secretisland"},
    ]),
    ("Next Island", [
        {"Name": "Next Island", "slug": "nextisland"},
        {"Name": "Ancient Greece", "slug": "ancientgreece"},
    ]),
    ("Toulan", [
        {"Name": "Toulan", "slug": "toulan"},
    ]),
    ("Monria", [
        {"Name": "Monria", "slug": "monria"},
        {"Name": "DSEC9", "slug": "dsec9"},
    ]),
    ("Space", [
        {"Name": "Space", "slug": "space"},
    ]),
]

# Layer toggle definitions: (label, color, types_controlled, default_on)
_LAYER_DEFS: list[tuple[str, str, set[str], bool]] = [
    ("TP",  "#00FFFF", {"Teleporter"}, True),
    ("LA",  "#4ade80", {"LandArea"}, True),
    ("MA",  "#facc15", {"MobArea", "Creature"}, False),
    ("PVP", "#ef4444", {"PvpArea", "PvpLootArea"}, False),
    ("OTH", "#a78bfa", {"ZoneArea", "EventArea", "WaveEventArea", "OtherArea", "OtherLocation"}, False),
]

_IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache", "maps")


def _planet_slug(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]", "", name).lower()


# ---------------------------------------------------------------------------
# Mob-area name parsing and difficulty coloring
# ---------------------------------------------------------------------------

# Difficulty bands: 0-5 index → label, base hue
# Very Low → Low → Medium → High → Very High → Boss-only
_DIFFICULTY_LABELS = ["Very Low", "Low", "Medium", "High", "Very High", "Boss"]

_BOSS_COLOR = (180, 80, 220)  # purple RGB


def _parse_mob_area_name(name: str) -> list[str]:
    """Parse 'Mob1 - Mat1/Mat2, Mob2 - Mat3' → ['Mob1', 'Mob2'].

    Returns empty list if name doesn't follow the pattern.
    """
    if not name:
        return []
    groups = [g.strip() for g in name.split(",") if g.strip()]
    mobs: list[str] = []
    for g in groups:
        dash = g.find(" - ")
        if dash != -1:
            mobs.append(g[:dash].strip())
        else:
            mobs.append(g.strip())
    return mobs


def _mob_area_display_name(loc: dict) -> str:
    """Return display name for a mob area: just mob names, no maturities."""
    mobs = _parse_mob_area_name(loc.get("Name", ""))
    return ", ".join(mobs) if mobs else loc.get("Name", "Unknown")


def _format_mob_area_maturities(loc: dict) -> list[dict]:
    """Format mob maturity listings for info panel display.

    Returns list of dicts: { mob: str, display: str }
    e.g., [{"mob": "Atrox", "display": "Young-Old Alpha, Stalker"}]
    """
    maturities = loc.get("Maturities")
    if not maturities:
        return []

    # Group by mob name
    by_mob: dict[str, list[dict]] = {}
    for entry in maturities:
        mat = entry.get("Maturity") or {}
        mob_name = (mat.get("Mob") or {}).get("Name", "Unknown")
        props = mat.get("Properties") or {}
        if mob_name not in by_mob:
            by_mob[mob_name] = []
        by_mob[mob_name].append({
            "name": mat.get("Name", ""),
            "level": props.get("Level"),
            "health": props.get("Health", 0),
            "boss": props.get("Boss", False),
        })

    result = []
    for mob_name, mats in by_mob.items():
        # Sort by level, then health
        mats.sort(key=lambda m: (m["level"] if m["level"] is not None else float("inf"), m["health"]))
        display = _format_maturity_range(mats)
        result.append({"mob": mob_name, "display": display})
    return result


def _format_maturity_range(sorted_mats: list[dict]) -> str:
    """Format sorted maturities into ranges.

    Consecutive maturities become 'First-Last'. Boss boundary breaks ranges.
    Only collapses into a range for 3+ consecutive.
    """
    if not sorted_mats:
        return ""
    if len(sorted_mats) == 1:
        return sorted_mats[0]["name"]

    ranges: list[str] = []
    start = 0

    for i in range(1, len(sorted_mats) + 1):
        boss_break = i < len(sorted_mats) and sorted_mats[i]["boss"] != sorted_mats[i - 1]["boss"]
        if i == len(sorted_mats) or boss_break:
            count = i - start
            if count >= 3:
                ranges.append(f"{sorted_mats[start]['name']}-{sorted_mats[i - 1]['name']}")
            else:
                for j in range(start, i):
                    ranges.append(sorted_mats[j]["name"])
            start = i

    return ", ".join(ranges)


def _mob_area_difficulty(loc: dict) -> tuple[int, str] | None:
    """Compute difficulty band (0-5) from Maturities data.

    Returns (band_index, label) or None if no maturity data.
    Band 5 = boss-only.
    """
    maturities = loc.get("Maturities")
    if not maturities:
        return None

    levels: list[int] = []
    boss_count = 0
    total_count = 0

    for entry in maturities:
        mat = entry.get("Maturity") or {}
        props = mat.get("Properties") or {}
        is_boss = props.get("Boss", False)
        level = props.get("Level")

        total_count += 1
        if is_boss:
            boss_count += 1
        if level is not None:
            levels.append(level)

    if total_count == 0:
        return None

    # Boss-only area
    if boss_count == total_count:
        return (5, "Boss")

    if not levels:
        return None

    avg_level = sum(levels) / len(levels)

    # Map average level to difficulty band (0-4)
    # Based on Entropia Universe mob level ranges:
    # Very Low: 1-5, Low: 6-15, Medium: 16-35, High: 36-70, Very High: 71+
    if avg_level <= 5:
        band = 0
    elif avg_level <= 15:
        band = 1
    elif avg_level <= 35:
        band = 2
    elif avg_level <= 70:
        band = 3
    else:
        band = 4

    return (band, _DIFFICULTY_LABELS[band])


def _difficulty_color(band: int) -> tuple[int, int, int]:
    """Return RGB tuple for a difficulty band (0-5).

    Colors blend with the MobArea base yellow so they stay in the warm
    spectrum and won't be confused with other area type colors (blue, green, etc.).
    """
    if band == 5:  # Boss
        return _BOSS_COLOR

    # Gradient from green-yellow → yellow → orange → red-orange → red
    # Pre-computed to look good both solo and when rendered at 0.3 opacity
    _BAND_COLORS = [
        (100, 230, 50),   # Very Low — green-yellow
        (200, 230, 0),    # Low — yellow-green
        (255, 200, 0),    # Medium — warm yellow
        (255, 120, 0),    # High — orange
        (255, 50, 30),    # Very High — red
    ]
    return _BAND_COLORS[band]


def _precompute_mob_area_data(locations: list[dict]):
    """Pre-compute display names and difficulty colors for all MobArea locations.

    Stores results directly on the location dicts as:
      _mob_display_name: str
      _mob_difficulty: (band, label) | None
      _mob_color: (r, g, b) | None
    """
    for loc in locations:
        loc_type = loc.get("Properties", {}).get("Type", "")
        if loc_type != "MobArea":
            continue

        loc["_mob_display_name"] = _mob_area_display_name(loc)

        diff = _mob_area_difficulty(loc)
        loc["_mob_difficulty"] = diff
        if diff:
            loc["_mob_color"] = _difficulty_color(diff[0])
        else:
            loc["_mob_color"] = None


def _fuzzy_score(name: str, query: str) -> int:
    """Fuzzy scoring — ported from mapUtil.js."""
    if not name or not query:
        return 0
    name_l = name.lower()
    query_l = query.lower()

    if name_l == query_l:
        return 1000
    if name_l.startswith(query_l):
        return 900

    words = name_l.split()
    for i, w in enumerate(words):
        if w.startswith(query_l):
            return 800 - i * 5

    idx = name_l.find(query_l)
    if idx != -1:
        return 700 - min(idx, 50)

    if len(query_l) < 4:
        return 0

    query_idx = 0
    score = 0
    consecutive_bonus = 0
    match_positions: list[int] = []

    for i, ch in enumerate(name_l):
        if query_idx < len(query_l) and ch == query_l[query_idx]:
            match_positions.append(i)
            query_idx += 1
            consecutive_bonus += 10
            score += consecutive_bonus
            if i == 0 or name_l[i - 1] in (" ", "-", "_"):
                score += 30
        else:
            consecutive_bonus = 0

    if query_idx == len(query_l):
        spread = (match_positions[-1] - match_positions[0]) if len(match_positions) > 1 else 0
        if spread > len(query_l) * 2:
            return 0
        compact_bonus = max(0, 50 - spread)
        return 300 + score + compact_bonus

    match_ratio = query_idx / len(query_l)
    if match_ratio >= 0.95 and len(query_l) >= 5:
        spread = (match_positions[-1] - match_positions[0]) if len(match_positions) > 1 else 0
        if spread <= len(query_l) * 2:
            return 100 + int(score * match_ratio)

    return 0


_MAX_SEARCH_RESULTS = 20


# ---------------------------------------------------------------------------
# _SearchResultsList
# ---------------------------------------------------------------------------

class _SearchResultRow(QWidget):
    """Single row in the search results dropdown."""

    clicked = pyqtSignal(int)
    hovered = pyqtSignal(int)

    def __init__(self, index: int, name: str, loc_type: str, name_color: str | None = None, parent=None):
        super().__init__(parent)
        self._index = index
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setStyleSheet(self._bg_style(False))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        idx_lbl = QLabel(str(index + 1))
        idx_lbl.setFixedWidth(20)
        idx_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        idx_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        layout.addWidget(idx_lbl)

        color = name_color or TEXT
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        name_lbl.setMinimumWidth(0)
        sp = name_lbl.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        name_lbl.setSizePolicy(sp)
        layout.addWidget(name_lbl, 1)

        type_lbl = QLabel(loc_type)
        type_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        type_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;")
        type_lbl.setFixedWidth(80)
        layout.addWidget(type_lbl)

        self.setToolTip(name)

    def set_active(self, active: bool):
        self.setStyleSheet(self._bg_style(active))

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hovered.emit(self._index)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)

    @staticmethod
    def _bg_style(active: bool) -> str:
        bg = HOVER if active else "transparent"
        return f"background: {bg}; border: none; border-radius: 3px;"


class _SearchResultsList(QWidget):
    """Floating dropdown of search results below the search input."""

    result_hovered = pyqtSignal(object)   # dict | None
    result_clicked = pyqtSignal(object)   # dict

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"_SearchResultsList {{ background: {_OVERLAY_BG};"
            f" border: 1px solid {_OVERLAY_BORDER};"
            f" border-radius: {_OVERLAY_RADIUS}px; }}"
        )
        self.hide()

        self._results: list[dict] = []
        self._selected_index = -1
        self._rows: list[_SearchResultRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        layout.addWidget(self._scroll)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)
        self._scroll.setWidget(self._container)

    def set_results(self, results: list[dict]):
        """Populate with new results."""
        self._results = results
        self._selected_index = 0 if results else -1

        # Clear old rows
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        for i, loc in enumerate(results):
            name = loc.get("_mob_display_name") or loc.get("Name") or ""
            loc_type = loc.get("Properties", {}).get("Type", "Location")
            mob_rgb = loc.get("_mob_color")
            name_color = f"rgb({mob_rgb[0]}, {mob_rgb[1]}, {mob_rgb[2]})" if mob_rgb else None
            row = _SearchResultRow(i, name, loc_type, name_color=name_color)
            row.set_active(i == self._selected_index)
            row.clicked.connect(self._on_click)
            row.hovered.connect(self._on_hover)
            self._container_layout.addWidget(row)
            self._rows.append(row)

        if results:
            max_h = min(len(results) * 28 + 8, 400)
            self.setFixedHeight(max_h)
            self.show()
            self.raise_()
        else:
            self.hide()

    def select_index(self, index: int, *, scroll: bool = False):
        """Move the active highlight to *index* and emit hover signal."""
        if not self._results:
            return
        old = self._selected_index
        self._selected_index = max(0, min(index, len(self._results) - 1))
        if old != self._selected_index:
            if 0 <= old < len(self._rows):
                self._rows[old].set_active(False)
            self._rows[self._selected_index].set_active(True)
            if scroll:
                self._scroll.ensureWidgetVisible(self._rows[self._selected_index])
            self.result_hovered.emit(self._results[self._selected_index])

    def highlight_by_id(self, loc_id: int | None):
        """Visually highlight row matching *loc_id* without emitting signals."""
        old = self._selected_index
        new_idx = -1
        if loc_id is not None:
            for i, r in enumerate(self._results):
                if r.get("Id") == loc_id:
                    new_idx = i
                    break
        if new_idx == old:
            return
        if 0 <= old < len(self._rows):
            self._rows[old].set_active(False)
        if 0 <= new_idx < len(self._rows):
            self._rows[new_idx].set_active(True)
        self._selected_index = new_idx

    def clear_highlight(self):
        """Remove highlight from all rows without emitting signals."""
        if 0 <= self._selected_index < len(self._rows):
            self._rows[self._selected_index].set_active(False)
        self._selected_index = -1

    def current_result(self) -> dict | None:
        if 0 <= self._selected_index < len(self._results):
            return self._results[self._selected_index]
        return None

    def _on_click(self, index: int):
        if 0 <= index < len(self._results):
            self.result_clicked.emit(self._results[index])

    def _on_hover(self, index: int):
        self.select_index(index)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.result_hovered.emit(None)


# ---------------------------------------------------------------------------
# Distance helpers
# ---------------------------------------------------------------------------

def _distance_meters(a_coords: dict, b_coords: dict) -> float:
    """Euclidean 2D distance between two Entropia coordinates (already in meters)."""
    dx = a_coords.get("Longitude", 0) - b_coords.get("Longitude", 0)
    dy = a_coords.get("Latitude", 0) - b_coords.get("Latitude", 0)
    return math.sqrt(dx * dx + dy * dy)


def _closest_teleporters(loc: dict, all_locations: list[dict], count: int = 3) -> list[tuple[dict, float]]:
    """Return up to *count* closest teleporters with distances."""
    coords = loc.get("Properties", {}).get("Coordinates")
    if not coords:
        return []
    tps = []
    for l in all_locations:
        p = l.get("Properties", {})
        if p.get("Type") == "Teleporter" and p.get("Coordinates"):
            d = _distance_meters(coords, p["Coordinates"])
            tps.append((l, d))
    tps.sort(key=lambda t: t[1])
    return tps[:count]


_INFO_PANEL_WIDTH = 420  # Fallback; overridden at runtime to match search panel


# ---------------------------------------------------------------------------
# _LocationInfoPanel
# ---------------------------------------------------------------------------

class _LocationInfoPanel(QWidget):
    """Compact floating info panel shown when a location is selected."""

    close_clicked = pyqtSignal()
    teleporter_clicked = pyqtSignal(object)  # dict
    teleporter_hovered = pyqtSignal(object)  # dict | None
    mob_clicked = pyqtSignal(str)  # mob name

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(_INFO_PANEL_WIDTH)
        self.setStyleSheet(
            f"_LocationInfoPanel {{ background: {_OVERLAY_BG};"
            f" border: 1px solid {_OVERLAY_BORDER};"
            f" border-radius: {_OVERLAY_RADIUS}px; }}"
        )
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        outer.addWidget(self._scroll)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(14, 12, 14, 14)
        self._layout.setSpacing(0)
        self._scroll.setWidget(self._content)

        self._planet_name: str = ""

    def set_location(self, loc: dict, planet: dict, all_locations: list[dict]):
        """Populate the panel with location info."""
        self._planet_name = planet.get("Name", "")

        # Clear previous fixed-height constraint so layout can size freely.
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX

        # Replace content widget entirely — QScrollArea.setWidget() takes
        # ownership and deletes the previous widget.
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(14, 12, 14, 14)
        self._layout.setSpacing(0)
        self._scroll.setWidget(self._content)

        props = loc.get("Properties", {})
        name = loc.get("_mob_display_name") or loc.get("Name", "Unknown")
        loc_type = props.get("Type", "")

        # --- Header row: name + close button ---
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # Color the name by difficulty for MobAreas
        diff = loc.get("_mob_difficulty")
        mob_color = loc.get("_mob_color")
        if mob_color and diff:
            r, g, b = mob_color
            name_color = f"rgb({r}, {g}, {b})"
        else:
            name_color = TEXT

        name_lbl = QLabel(name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"color: {name_color}; font-size: 15px; font-weight: 600; background: transparent;"
        )
        h_layout.addWidget(name_lbl, 1)

        close_btn = QPushButton("X")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_MUTED}; font-size: 12px; font-weight: 700;"
            f" background: transparent; border: 1px solid {BORDER}; border-radius: 4px; padding: 0px; }}"
            f"QPushButton:hover {{ background: {HOVER}; color: {TEXT}; }}"
        )
        close_btn.clicked.connect(self.close_clicked.emit)
        h_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        self._layout.addWidget(header)

        # --- Type label ---
        if loc_type:
            type_lbl = QLabel(loc_type)
            type_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
                f" margin-top: 2px;"
            )
            self._layout.addWidget(type_lbl)

        self._add_separator()

        # --- Coordinates ---
        coords = props.get("Coordinates")
        if coords:
            lon = coords.get("Longitude")
            lat = coords.get("Latitude")
            if lon is not None and lat is not None:
                coord_lbl = QLabel(f"Long: {lon:.0f}   Lat: {lat:.0f}")
                coord_lbl.setStyleSheet(
                    f"color: {TEXT}; font-size: 12px; background: transparent;"
                )
                self._layout.addWidget(coord_lbl)

                # Waypoint copy button
                wp_btn = QPushButton("Copy Waypoint")
                wp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                wp_btn.setStyleSheet(
                    f"QPushButton {{ color: {ACCENT}; font-size: 11px;"
                    f" background: transparent; border: 1px solid {BORDER};"
                    f" border-radius: 4px; padding: 4px 8px; margin-top: 6px; }}"
                    f"QPushButton:hover {{ background: {HOVER}; }}"
                )
                alt = coords.get("Altitude") or 100
                wp_text = f"/wp [{self._planet_name}, {lon:.0f}, {lat:.0f}, {alt:.0f}, {name}]"
                wp_btn.clicked.connect(lambda _, t=wp_text: self._copy_to_clipboard(t, wp_btn))
                self._layout.addWidget(wp_btn)

                self._add_separator()

        # --- Closest Teleporters ---
        if loc_type != "Teleporter":
            closest = _closest_teleporters(loc, all_locations, count=3)
            if closest:
                tp_header = QLabel("CLOSEST TELEPORTERS")
                tp_header.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600;"
                    f" background: transparent; margin-bottom: 4px;"
                )
                self._layout.addWidget(tp_header)

                _TP_ROW_NORMAL = (
                    f"QWidget {{ background: {MAIN_DARK}; border: 1px solid {BORDER};"
                    f" border-radius: 4px; margin-bottom: 3px; }}"
                )
                _TP_ROW_HOVER = (
                    f"QWidget {{ background: {HOVER}; border: 1px solid {ACCENT};"
                    f" border-radius: 4px; margin-bottom: 3px; }}"
                )

                for tp, dist in closest:
                    tp_name = tp.get("Name", "TP")
                    dist_str = f"{dist / 1000:.1f} km" if dist >= 1000 else f"{dist:.0f} m"

                    row = QWidget()
                    row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    row.setCursor(Qt.CursorShape.PointingHandCursor)
                    row.setFixedHeight(30)
                    row.setStyleSheet(_TP_ROW_NORMAL)
                    row_l = QHBoxLayout(row)
                    row_l.setContentsMargins(8, 0, 8, 0)
                    row_l.setSpacing(4)

                    name_part = QLabel(tp_name)
                    name_part.setStyleSheet(
                        f"color: {TEXT}; font-size: 12px; background: transparent; border: none;"
                    )
                    dist_part = QLabel(dist_str)
                    dist_part.setStyleSheet(
                        f"color: {TEXT_MUTED}; font-size: 11px; background: transparent; border: none;"
                    )
                    dist_part.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                    row_l.addWidget(name_part, 1)
                    row_l.addWidget(dist_part, 0)

                    def _make_tp_handlers(r, t):
                        def on_press(e):
                            self.teleporter_clicked.emit(t)
                        def on_enter(e):
                            r.setStyleSheet(_TP_ROW_HOVER)
                            self.teleporter_hovered.emit(t)
                        def on_leave(e):
                            r.setStyleSheet(_TP_ROW_NORMAL)
                            self.teleporter_hovered.emit(None)
                        return on_press, on_enter, on_leave

                    _press, _enter, _leave = _make_tp_handlers(row, tp)
                    row.mousePressEvent = _press
                    row.enterEvent = _enter
                    row.leaveEvent = _leave
                    self._layout.addWidget(row)

                self._add_separator()

        # --- MobArea details ---
        if loc_type == "MobArea":
            density = props.get("Density")
            shared = props.get("IsShared")
            is_event = props.get("IsEvent")
            notes = props.get("Notes")

            mob_header = QLabel("MOB AREA")
            mob_header.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600;"
                f" background: transparent; margin-bottom: 4px;"
            )
            self._layout.addWidget(mob_header)

            if diff:
                dr, dg, db = _difficulty_color(diff[0])
                self._add_stat_row_colored("Difficulty", diff[1], f"rgb({dr}, {dg}, {db})")
            if density is not None:
                density_map = {1: "Low", 2: "Medium", 3: "High"}
                self._add_stat_row("Density", density_map.get(density, str(density)))
            if shared is not None:
                self._add_stat_row("Shared", "Yes" if shared else "No")
            if is_event is not None:
                self._add_stat_row("Event", "Yes" if is_event else "No")

            # Mob type listings with maturity ranges
            mob_entries = _format_mob_area_maturities(loc)
            if mob_entries:
                for entry in mob_entries:
                    mob_row = QWidget()
                    mob_row.setStyleSheet("background: transparent;")
                    mob_row_l = QHBoxLayout(mob_row)
                    mob_row_l.setContentsMargins(0, 2, 0, 2)
                    mob_row_l.setSpacing(4)

                    mob_link = QPushButton(entry["mob"])
                    mob_link.setCursor(Qt.CursorShape.PointingHandCursor)
                    mob_link.setStyleSheet(
                        f"QPushButton {{ color: {ACCENT}; font-size: 12px;"
                        f" background: transparent; border: none; padding: 0;"
                        f" text-align: left; }}"
                        f"QPushButton:hover {{ text-decoration: underline; }}"
                    )
                    mob_link.clicked.connect(
                        lambda _, m=entry["mob"]: self._navigate_to_mob(m)
                    )
                    mob_row_l.addWidget(mob_link)

                    if entry["display"]:
                        mat_lbl = QLabel(f"- {entry['display']}")
                        mat_lbl.setStyleSheet(
                            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
                        )
                        mob_row_l.addWidget(mat_lbl)

                    mob_row_l.addStretch()
                    self._layout.addWidget(mob_row)

            if notes:
                notes_lbl = QLabel(notes)
                notes_lbl.setWordWrap(True)
                notes_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
                    f" margin-top: 4px;"
                )
                self._layout.addWidget(notes_lbl)

            self._add_separator()

        # --- Description ---
        desc = props.get("Description")
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
            )
            self._layout.addWidget(desc_lbl)

        # Show the panel, then defer height calculation so Qt processes
        # the freshly-built layout before we measure sizeHint().
        self.show()
        self.raise_()
        QTimer.singleShot(0, self._fit_height)

    def _fit_height(self):
        """Recalculate panel height after Qt has processed the layout."""
        if not self.isVisible():
            return
        # Clear previous fixed-height constraint before re-measuring.
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        self._layout.activate()
        self._content.adjustSize()
        ideal_h = self._content.sizeHint().height() + 2  # +2 for border
        parent = self.parentWidget()
        max_h = (parent.height() - 20) if parent else 800
        self.setFixedHeight(min(ideal_h, max_h))

    def _add_separator(self):
        wrapper = QWidget()
        wrapper.setFixedHeight(13)
        wrapper.setStyleSheet("background: transparent;")
        w_layout = QVBoxLayout(wrapper)
        w_layout.setContentsMargins(0, 6, 0, 6)
        w_layout.setSpacing(0)
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {BORDER};")
        w_layout.addWidget(line)
        self._layout.addWidget(wrapper)

    def _add_stat_row(self, label: str, value: str):
        self._add_stat_row_colored(label, value, TEXT)

    def _add_stat_row_colored(self, label: str, value: str, value_color: str):
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 2)
        row_l.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        val = QLabel(value)
        val.setStyleSheet(f"color: {value_color}; font-size: 12px; font-weight: 600; background: transparent;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row_l.addWidget(lbl, 1)
        row_l.addWidget(val, 0)
        self._layout.addWidget(row)

    @staticmethod
    def _copy_to_clipboard(text: str, btn: QPushButton):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
        old = btn.text()
        btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: btn.setText(old))

    def _navigate_to_mob(self, mob_name: str):
        """Emit signal to navigate to a mob's wiki page."""
        self.mob_clicked.emit(mob_name)


# ---------------------------------------------------------------------------
# MapsPage
# ---------------------------------------------------------------------------

class MapsPage(QWidget):
    """Full-canvas map page with floating planet selector, search, and layer toggles."""

    _planet_data_ready = pyqtSignal(str, dict, QPixmap, list)  # slug, planet, image, locations

    def __init__(self, *, data_client, config, **kwargs):
        super().__init__(**kwargs)
        self._data_client = data_client
        self._config = config
        self._planets: list[dict] = []
        self._current_slug: str | None = None
        self._loading = False
        self._pending_location_id: int | None = None

        os.makedirs(_IMAGE_CACHE_DIR, exist_ok=True)

        # --- Layout: map canvas fills everything ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._canvas = MapCanvas(self)
        layout.addWidget(self._canvas)

        # --- Floating overlays (children of self, positioned in resizeEvent) ---

        # Top-left: planet selector + search
        self._top_overlay = QWidget(self)
        self._top_overlay.setStyleSheet(
            f"background: {_OVERLAY_BG}; border: 1px solid {_OVERLAY_BORDER};"
            f" border-radius: {_OVERLAY_RADIUS}px;"
        )
        top_layout = QVBoxLayout(self._top_overlay)
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(6)

        self._planet_combo = QComboBox()
        self._planet_combo.setMinimumWidth(290)
        self._planet_combo.setStyleSheet(
            f"QComboBox {{ background: {MAIN_DARK}; color: {TEXT};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" padding: 4px 8px; font-size: 12px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background: {MAIN_DARK}; color: {TEXT};"
            f" border: 1px solid {BORDER}; selection-background-color: {HOVER}; }}"
        )
        top_layout.addWidget(self._planet_combo)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(0)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search locations...")
        self._search_input.setStyleSheet(
            f"background: {MAIN_DARK}; color: {TEXT}; border: 1px solid {BORDER};"
            f" border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        search_row.addWidget(self._search_input, 1)

        self._search_clear_btn = QPushButton("\u2715")
        self._search_clear_btn.setFixedWidth(28)
        self._search_clear_btn.setFixedHeight(self._search_input.sizeHint().height())
        self._search_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_clear_btn.setStyleSheet(
            f"QPushButton {{ background: {MAIN_DARK}; color: {TEXT_MUTED};"
            f" border: 1px solid {BORDER}; border-left: none;"
            f" border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            f" border-top-left-radius: 0; border-bottom-left-radius: 0;"
            f" font-size: 12px; padding: 0; }}"
            f"QPushButton:hover {{ color: {TEXT}; background: {HOVER}; }}"
        )
        self._search_clear_btn.clicked.connect(self._clear_search)
        self._search_clear_btn.hide()
        search_row.addWidget(self._search_clear_btn)

        top_layout.addLayout(search_row)

        self._top_overlay.adjustSize()

        # Search results dropdown (floating child of self, positioned below top overlay)
        self._search_dropdown = _SearchResultsList(self)
        self._search_dropdown.result_clicked.connect(self._on_search_result_clicked)
        self._search_dropdown.result_hovered.connect(self._on_search_result_hovered)
        self._search_input.installEventFilter(self)

        # Bottom-left: layer toggles
        self._layer_overlay = QWidget(self)
        self._layer_overlay.setStyleSheet("background: transparent;")
        layer_layout = QVBoxLayout(self._layer_overlay)
        layer_layout.setContentsMargins(0, 0, 0, 0)
        layer_layout.setSpacing(6)

        self._layer_buttons: list[tuple[QPushButton, set[str]]] = []
        for label, color, types, default_on in _LAYER_DEFS:
            btn = QPushButton(label)
            btn.setFixedSize(44, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(default_on)
            btn.setStyleSheet(self._layer_btn_style(color, default_on))
            btn.toggled.connect(
                lambda checked, b=btn, c=color: self._on_layer_toggled(b, c, checked)
            )
            layer_layout.addWidget(btn)
            self._layer_buttons.append((btn, types))

        self._layer_overlay.adjustSize()

        # Loading label (centered)
        self._loading_label = QLabel("Loading map...", self)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 16px; background: transparent;"
        )
        self._loading_label.hide()

        # Info panel (floating on right side)
        self._info_panel = _LocationInfoPanel(self)
        self._info_panel.close_clicked.connect(self._hide_info_panel)
        self._info_panel.teleporter_clicked.connect(self._on_teleporter_clicked)
        self._info_panel.teleporter_hovered.connect(self._on_teleporter_hovered)
        self._info_panel.mob_clicked.connect(self._on_mob_clicked)
        self._selected_location: dict | None = None

        # --- Signals ---
        self._planet_combo.currentIndexChanged.connect(self._on_planet_selected)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._planet_data_ready.connect(self._on_planet_data_ready)
        self._canvas.location_clicked.connect(self._on_canvas_location_clicked)
        self._canvas.location_hovered.connect(self._on_canvas_location_hovered)

        # Debounce search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_search)

        # Load planets in background
        threading.Thread(target=self._fetch_planets, daemon=True, name="maps-planets").start()

    # --- Overlay positioning ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_overlays()
        if self._info_panel.isVisible():
            self._info_panel._fit_height()

    def _position_overlays(self):
        margin = 16
        self._top_overlay.move(margin, margin)
        self._layer_overlay.move(margin, self.height() - self._layer_overlay.height() - margin)
        # Position search dropdown below top overlay
        drop_x = margin
        drop_y = margin + self._top_overlay.height() + 4
        self._search_dropdown.move(drop_x, drop_y)
        self._search_dropdown.setFixedWidth(self._top_overlay.width())
        # Info panel on right side — match search panel width
        panel_w = self._top_overlay.width()
        self._info_panel.setFixedWidth(panel_w)
        self._info_panel.move(self.width() - panel_w - margin, margin)
        # Center loading label
        self._loading_label.setGeometry(0, 0, self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        self._position_overlays()
        self._top_overlay.raise_()
        self._layer_overlay.raise_()
        self._search_dropdown.raise_()
        self._info_panel.raise_()

    # --- Layer toggle style ---

    @staticmethod
    def _layer_btn_style(color: str, active: bool) -> str:
        opacity = "1.0" if active else "0.5"
        border_color = ACCENT if active else BORDER
        return (
            f"QPushButton {{ color: {color}; font-size: 11px; font-weight: 700;"
            f" background: rgba(0,0,0,0.75); border: 1px solid {border_color};"
            f" border-radius: 4px; padding: 0px; }}"
            f"QPushButton:hover {{ background: rgba(0,0,0,0.9); }}"
        )

    # --- Data loading ---

    def _fetch_planets(self):
        try:
            self._planets = self._data_client.get_planets()
        except Exception as e:
            log.error("Failed to fetch planets: %s", e)
            self._planets = []
        # Populate combo on main thread
        QTimer.singleShot(0, self._populate_planet_combo)

    def _populate_planet_combo(self):
        self._planet_combo.blockSignals(True)
        self._planet_combo.clear()

        planet_by_slug: dict[str, dict] = {}
        for p in self._planets:
            planet_by_slug[_planet_slug(p["Name"])] = p

        for group_name, entries in PLANET_GROUPS:
            # Group separator
            self._planet_combo.addItem(f"── {group_name} ──")
            idx = self._planet_combo.count() - 1
            # Make separator non-selectable
            self._planet_combo.model().item(idx).setEnabled(False)

            for entry in entries:
                slug = entry["slug"]
                display = entry["Name"]
                self._planet_combo.addItem(display, slug)

        self._planet_combo.blockSignals(False)

        # Select Calypso by default
        for i in range(self._planet_combo.count()):
            if self._planet_combo.itemData(i) == "calypso":
                self._planet_combo.setCurrentIndex(i)
                break

    def _on_planet_selected(self, index: int):
        slug = self._planet_combo.itemData(index)
        if not slug or slug == self._current_slug:
            return
        self._current_slug = slug
        self._loading = True
        self._loading_label.show()
        self._loading_label.raise_()

        threading.Thread(
            target=self._fetch_planet_data, args=(slug,),
            daemon=True, name=f"maps-{slug}",
        ).start()

    def _fetch_planet_data(self, slug: str):
        """Background: fetch locations + areas + mobspawns + image for a planet."""
        # Find planet dict
        planet = None
        for p in self._planets:
            if _planet_slug(p["Name"]) == slug:
                planet = p
                break
        if not planet:
            log.error("Planet not found for slug: %s", slug)
            return

        planet_name = planet["Name"]

        # Fetch data in sequence (threads are cheap, avoid overcomplicating)
        try:
            locations = self._data_client.get_locations_for_planet(planet_name)
        except Exception:
            locations = []
        try:
            areas = self._data_client.get_areas_for_planet(planet_name)
        except Exception:
            areas = []
        try:
            mobspawns = self._data_client.get_mobspawns_for_planet(planet_name)
        except Exception:
            mobspawns = []

        # Merge (same logic as +page.js)
        by_id: dict[int, dict] = {}
        for loc in locations:
            by_id[loc["Id"]] = loc
        for area in areas:
            by_id[area["Id"]] = area
            offset_id = area["Id"] + 200000
            if offset_id in by_id and not by_id[offset_id].get("Properties", {}).get("Shape"):
                del by_id[offset_id]
        for mob in mobspawns:
            by_id[mob["Id"]] = mob
        merged = list(by_id.values())

        # Pre-compute mob area display names and difficulty colors
        _precompute_mob_area_data(merged)

        # Load image
        pixmap = self._load_planet_image(slug)

        if pixmap and not pixmap.isNull():
            self._planet_data_ready.emit(slug, planet, pixmap, merged)

    def _load_planet_image(self, slug: str) -> QPixmap | None:
        """Load planet image from cache or download it."""
        cache_path = os.path.join(_IMAGE_CACHE_DIR, f"{slug}.jpg")

        if os.path.exists(cache_path):
            pm = QPixmap(cache_path)
            if not pm.isNull():
                return pm

        # Download from the website's static assets
        base_url = getattr(self._config, "nexus_base_url", "https://entropianexus.com")
        url = f"{base_url}/{slug}.jpg"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(resp.content)
            pm = QPixmap(cache_path)
            return pm if not pm.isNull() else None
        except Exception as e:
            log.error("Failed to download map image %s: %s", url, e)
            return None

    def _on_planet_data_ready(self, slug: str, planet: dict, pixmap: QPixmap, locations: list):
        """Main thread: set the map data."""
        if slug != self._current_slug:
            return  # User switched planet while loading
        self._loading = False
        self._loading_label.hide()
        self._hide_info_panel()
        self._canvas.set_planet(planet, pixmap, locations)
        self._on_layers_changed()  # Apply current layer state
        self._apply_search()       # Apply current search
        self._position_overlays()
        self._top_overlay.raise_()
        self._search_dropdown.raise_()
        self._layer_overlay.raise_()
        self._info_panel.raise_()

        # If a location was requested before data loaded, select it now
        if self._pending_location_id is not None:
            loc_id = self._pending_location_id
            self._pending_location_id = None
            loc = self._canvas._find_by_id(loc_id)
            if loc:
                self._canvas.set_selected(loc_id)
                self._canvas.center_on_smart(loc)
                self._show_info_panel(loc)

    def navigate_to_location(self, planet_name: str, location_id: int):
        """Navigate to a specific location on a planet (used by external callers)."""
        slug = _planet_slug(planet_name)
        if slug == self._current_slug and not self._loading:
            # Planet already loaded — select immediately
            loc = self._canvas._find_by_id(location_id)
            if loc:
                self._canvas.set_selected(location_id)
                self._canvas.center_on_smart(loc)
                self._show_info_panel(loc)
        else:
            # Planet needs to load first — defer selection
            self._pending_location_id = location_id
            if slug != self._current_slug:
                for i in range(self._planet_combo.count()):
                    if self._planet_combo.itemData(i) == slug:
                        self._planet_combo.setCurrentIndex(i)
                        break

    # --- Layers ---

    def _on_layer_toggled(self, btn: QPushButton, color: str, checked: bool):
        btn.setStyleSheet(self._layer_btn_style(color, checked))
        self._on_layers_changed()

    def _on_layers_changed(self):
        visible: set[str] = set()
        for btn, types in self._layer_buttons:
            if btn.isChecked():
                visible |= types
        self._canvas.set_layers(visible)

    # --- Search ---

    def eventFilter(self, obj, event):
        """Handle keyboard navigation in the search input."""
        if obj is self._search_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                if self._search_dropdown.isVisible():
                    idx = self._search_dropdown._selected_index
                    self._search_dropdown.select_index(idx + 1, scroll=True)
                    result = self._search_dropdown.current_result()
                    if result:
                        self._canvas.set_hovered(result.get("Id"))
                        self._canvas.pan_to(result)
                return True
            elif key == Qt.Key.Key_Up:
                if self._search_dropdown.isVisible():
                    idx = self._search_dropdown._selected_index
                    self._search_dropdown.select_index(idx - 1, scroll=True)
                    result = self._search_dropdown.current_result()
                    if result:
                        self._canvas.set_hovered(result.get("Id"))
                        self._canvas.pan_to(result)
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._search_dropdown.isVisible():
                    result = self._search_dropdown.current_result()
                    if result:
                        self._on_search_result_clicked(result)
                return True
            elif key == Qt.Key.Key_Escape:
                if self._search_input.text().strip():
                    self._search_input.clear()
                else:
                    self._search_dropdown.hide()
                    self._search_input.clearFocus()
                return True
        return super().eventFilter(obj, event)

    def _on_search_changed(self, text: str):
        has_text = bool(text.strip())
        self._search_clear_btn.setVisible(has_text)
        # Adjust input border: remove right border/radius when clear button is visible
        if has_text:
            self._search_input.setStyleSheet(
                f"background: {MAIN_DARK}; color: {TEXT}; border: 1px solid {BORDER};"
                f" border-right: none;"
                f" border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
                f" border-top-right-radius: 0; border-bottom-right-radius: 0;"
                f" padding: 4px 8px; font-size: 12px;"
            )
        else:
            self._search_input.setStyleSheet(
                f"background: {MAIN_DARK}; color: {TEXT}; border: 1px solid {BORDER};"
                f" border-radius: 4px; padding: 4px 8px; font-size: 12px;"
            )
        self._search_timer.start()

    def _clear_search(self):
        """Clear the search input (triggers _on_search_changed)."""
        self._search_input.clear()
        self._search_input.setFocus()

    def _apply_search(self):
        query = self._search_input.text().strip()
        if not query:
            self._canvas.set_search_results(set())
            self._search_dropdown.set_results([])
            return

        # Fuzzy score all locations (name score, + 40% of type score)
        # For MobAreas, also score the simplified display name
        scored: list[tuple[int, dict]] = []
        for loc in self._canvas._locations:
            name = loc.get("Name") or ""
            loc_type = loc.get("Properties", {}).get("Type", "")
            display_name = loc.get("_mob_display_name") or ""
            s = max(
                _fuzzy_score(name, query),
                _fuzzy_score(display_name, query) if display_name else 0,
                int(_fuzzy_score(loc_type, query) * 0.4),
            )
            if s > 0:
                scored.append((s, loc))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [loc for _, loc in scored[:_MAX_SEARCH_RESULTS]]

        # Update canvas highlighting
        ids = {loc["Id"] for loc in results}
        self._canvas.set_search_results(ids)

        # Update dropdown
        self._search_dropdown.set_results(results)
        self._position_overlays()

    def _on_search_result_clicked(self, loc: dict):
        """User selected a search result — center map on it (dropdown stays open)."""
        self._canvas.set_selected(loc.get("Id"))
        self._canvas.center_on_smart(loc)
        self._show_info_panel(loc)
        # Return focus to search input so keyboard navigation keeps working
        self._search_input.setFocus()

    def _on_search_result_hovered(self, loc: object):
        """Highlight hovered search result on canvas and pan to it."""
        if loc and isinstance(loc, dict):
            self._canvas.set_hovered(loc.get("Id"))
            self._canvas.pan_to(loc)
        else:
            self._canvas.set_hovered(None)

    def _on_canvas_location_hovered(self, loc: object):
        """When hovering a location on the map, highlight the matching search result."""
        if not self._search_dropdown.isVisible():
            return
        if loc and isinstance(loc, dict):
            self._search_dropdown.highlight_by_id(loc.get("Id"))
        else:
            self._search_dropdown.clear_highlight()

    def _on_canvas_location_clicked(self, loc: object):
        """User clicked a location on the canvas — zoom in + show info."""
        if loc and isinstance(loc, dict):
            self._canvas.center_on_smart(loc)
            self._show_info_panel(loc)
        else:
            self._hide_info_panel()

    # --- Info panel ---

    def _show_info_panel(self, loc: dict):
        """Show the location info panel on the right side."""
        self._selected_location = loc
        # Find current planet dict
        planet = None
        for p in self._planets:
            if _planet_slug(p["Name"]) == self._current_slug:
                planet = p
                break
        if not planet:
            return
        self._info_panel.set_location(loc, planet, self._canvas._locations)
        self._position_overlays()
        self._info_panel.raise_()

    def _hide_info_panel(self):
        """Hide the info panel and clear selection."""
        self._selected_location = None
        self._info_panel.hide()
        self._canvas.set_selected(None)

    def _on_mob_clicked(self, mob_name: str):
        """Open the mob's wiki page in a browser."""
        import webbrowser
        from urllib.parse import quote as url_quote
        base_url = getattr(self._config, "nexus_base_url", "https://entropianexus.com")
        slug = re.sub(r"[^0-9a-zA-Z]", "", mob_name).lower()
        webbrowser.open(f"{base_url}/information/mobs/{url_quote(slug)}")

    def _on_teleporter_hovered(self, tp: object):
        """Pan to teleporter on hover, pan back to selected location on un-hover."""
        if tp and isinstance(tp, dict):
            self._canvas.set_hovered(tp.get("Id"))
            self._canvas.pan_to(tp)
        else:
            self._canvas.set_hovered(None)
            if self._selected_location:
                self._canvas.pan_to(self._selected_location)

    def _on_teleporter_clicked(self, tp: object):
        """User clicked a teleporter in the info panel — navigate to it."""
        if tp and isinstance(tp, dict):
            self._canvas.set_selected(tp.get("Id"))
            self._canvas.center_on_smart(tp)
            self._show_info_panel(tp)
