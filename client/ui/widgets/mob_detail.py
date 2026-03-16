"""Mob entity detail page — maturities, damage, spawns, loots, codex, globals."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
)

from ..icons import svg_icon, MAPS as MAPS_ICON, COPY as COPY_ICON, CHECK as CHECK_ICON
from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    MobDamageGridWidget, make_section_table,
    _TABLE_ROW_HEIGHT, _TABLE_MAX_HEIGHT,
)
from .fancy_table import ColumnDef
from .multi_line_chart import MultiLineChart, ChartSeries
from ...data.wiki_columns import _DAMAGE_TYPES, deep_get, get_item_name, fmt_int, fmt_bool
from ..theme import (
    PRIMARY, SECONDARY, BORDER, HOVER, TEXT, TEXT_MUTED, ACCENT, SUCCESS,
)


# ---------------------------------------------------------------------------
# Frequency badge colors (matching web MobLoots.svelte)
# ---------------------------------------------------------------------------
_FREQUENCY_COLORS = {
    "Always":         ("#22c55e", "rgba(22, 163, 74, 0.25)"),
    "Very often":     ("#4ade80", "rgba(34, 197, 94, 0.25)"),
    "Often":          ("#84cc16", "rgba(101, 163, 13, 0.25)"),
    "Common":         ("#eab308", "rgba(202, 138, 4, 0.25)"),
    "Uncommon":       ("#f97316", "rgba(234, 88, 12, 0.25)"),
    "Rare":           ("#ef4444", "rgba(220, 38, 38, 0.25)"),
    "Very Rare":      ("#f43f5e", "rgba(190, 18, 60, 0.25)"),
    "Very rare":      ("#f43f5e", "rgba(190, 18, 60, 0.25)"),
    "Extremely rare": ("#a855f7", "rgba(147, 51, 234, 0.25)"),
    "Discontinued":   ("#6b7280", "rgba(107, 114, 128, 0.25)"),
}

# Density labels/colors (matching web MobLocations.svelte)
_DENSITY_LABELS = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}
_DENSITY_COLORS = {
    1: ("#94a3b8", "rgba(148, 163, 184, 0.25)"),
    2: ("#eab308", "rgba(202, 138, 4, 0.25)"),
    3: ("#22c55e", "rgba(22, 163, 74, 0.25)"),
    4: ("#ef4444", "rgba(220, 38, 38, 0.25)"),
    5: ("#a855f7", "rgba(168, 85, 247, 0.25)"),
}

# Difficulty bands (matching mapUtil.js / maps_page.py)
_DIFFICULTY_LABELS = ["Very Low", "Low", "Medium", "High", "Very High", "Boss"]
_DIFFICULTY_COLORS = [
    ("#64e632", "rgba(100, 230, 50, 0.25)"),   # Very Low
    ("#c8e600", "rgba(200, 230, 0, 0.25)"),     # Low
    ("#ffc800", "rgba(255, 200, 0, 0.25)"),     # Medium
    ("#ff7800", "rgba(255, 120, 0, 0.25)"),     # High
    ("#ff321e", "rgba(255, 50, 30, 0.25)"),     # Very High
    ("#b450dc", "rgba(180, 80, 220, 0.25)"),    # Boss
]

_BADGE_STYLE = (
    "font-size: 11px; font-weight: 500; border-radius: 4px; "
    "padding: 2px 8px; border: none;"
)

_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {SECONDARY};
        alternate-background-color: {PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        font-size: 13px;
        color: {TEXT};
    }}
    QTableWidget::item {{
        padding: 4px 10px;
        border-bottom: 1px solid {BORDER};
        border-left: 2px solid transparent;
    }}
    QTableWidget::item:hover {{
        background-color: rgba(96, 176, 255, 0.15);
        border-left: 2px solid {ACCENT};
    }}
    QHeaderView::section {{
        background-color: {HOVER};
        color: {TEXT_MUTED};
        border: none;
        border-right: 1px solid {BORDER};
        border-bottom: 1px solid {BORDER};
        padding: 6px 10px;
        font-weight: 600;
        font-size: 11px;
    }}
"""


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


def _format_ped(v) -> str:
    """Format a PED value compactly (e.g. 1.5K)."""
    if v is None:
        return "0"
    if v >= 1000:
        return f"{v / 1000:.1f}K"
    return f"{v:.2f}"


def _time_ago(date_str: str) -> str:
    """Convert an ISO timestamp to a relative time string."""
    if not date_str:
        return ""
    try:
        then = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - then
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        return f"{days}d"
    except (ValueError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Maturity aggregation helpers
# ---------------------------------------------------------------------------

def _maturity_stats(item: dict):
    """Extract level range, HP range, and lowest HP/Level from maturities."""
    maturities = item.get("Maturities") or []
    if not maturities:
        return None, None, None

    levels = []
    hps = []
    hp_per_levels = []
    for m in maturities:
        level = deep_get(m, "Properties", "Level")
        hp = deep_get(m, "Properties", "Health")
        if level is not None:
            levels.append(level)
        if hp is not None:
            hps.append(hp)
        if level and hp and level > 0:
            hp_per_levels.append(hp / level)

    level_range = (min(levels), max(levels)) if levels else None
    hp_range = (min(hps), max(hps)) if hps else None
    lowest_hpl = min(hp_per_levels) if hp_per_levels else None

    return level_range, hp_range, lowest_hpl


def _get_damage_groups(maturities: list[dict], attack_name: str):
    """Group consecutive maturities with identical damage composition.

    Mirrors the website's getDamageGroups() logic — returns a list of
    ``{spread: dict, maturities: [str]}`` dicts, or None if no data.
    """
    # Sort: non-bosses first, then by HP*Level ascending
    sorted_mats = sorted(maturities, key=lambda m: (
        deep_get(m, "Properties", "Boss") is True,
        (deep_get(m, "Properties", "Health") or 0)
        * (deep_get(m, "Properties", "Level") or 0),
    ))

    entries: list[tuple[str, dict, str]] = []  # (name, spread, key)
    for m in sorted_mats:
        for attack in (m.get("Attacks") or []):
            if attack.get("Name") != attack_name:
                continue
            dmg = attack.get("Damage")
            if not dmg:
                continue
            spread = {k: (dmg.get(k) or 0) for k in _DAMAGE_TYPES}
            key = ",".join(str(round(spread[k])) for k in _DAMAGE_TYPES)
            entries.append((m.get("Name") or "Unknown", spread, key))

    if not entries:
        return None

    # Group consecutive maturities with identical composition
    groups: list[dict] = []
    for name, spread, key in entries:
        if groups and groups[-1]["key"] == key:
            groups[-1]["maturities"].append(name)
        else:
            groups.append({"spread": spread, "maturities": [name], "key": key})

    return [{"spread": g["spread"], "maturities": g["maturities"]} for g in groups]


def _format_maturity_label(maturities: list[str], total_count: int) -> str:
    """Build a concise maturity range label (or empty if all share the same composition)."""
    if len(maturities) == total_count:
        return ""
    if len(maturities) <= 2:
        return ", ".join(maturities)
    return f"{maturities[0]} \u2013 {maturities[-1]}"


def _parse_mob_area_name(name: str) -> list[str]:
    """Parse 'Mob1 - Mat1/Mat2, Mob2 - Mat3' → ['Mob1', 'Mob2']."""
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


def _format_maturity_range(sorted_mats: list[dict]) -> str:
    """Format sorted maturities into ranges (3+ consecutive → 'First-Last')."""
    if not sorted_mats:
        return ""
    if len(sorted_mats) == 1:
        return sorted_mats[0]["name"]

    ranges: list[str] = []
    start = 0
    for i in range(1, len(sorted_mats) + 1):
        boss_break = (i < len(sorted_mats)
                      and sorted_mats[i]["boss"] != sorted_mats[i - 1]["boss"])
        if i == len(sorted_mats) or boss_break:
            count = i - start
            if count >= 3:
                ranges.append(
                    f"{sorted_mats[start]['name']}-{sorted_mats[i - 1]['name']}"
                )
            else:
                for j in range(start, i):
                    ranges.append(sorted_mats[j]["name"])
            start = i
    return ", ".join(ranges)


def _spawn_maturities_for_mob(spawn: dict, mob_name: str) -> str:
    """Format the maturities in a spawn that belong to the given mob."""
    maturities = spawn.get("Maturities") or []
    mats = []
    for entry in maturities:
        mat = entry.get("Maturity") or {}
        mob = (mat.get("Mob") or {}).get("Name", "")
        if mob != mob_name:
            continue
        props = mat.get("Properties") or {}
        mats.append({
            "name": mat.get("Name", ""),
            "level": props.get("Level"),
            "health": props.get("Health", 0),
            "boss": props.get("Boss", False),
        })
    if not mats:
        return "All"
    mats.sort(key=lambda m: (
        m["level"] if m["level"] is not None else float("inf"),
        m["health"],
    ))
    return _format_maturity_range(mats) or "All"


def _spawn_difficulty(spawn: dict) -> tuple[int, str] | None:
    """Compute difficulty band from spawn maturities. Returns (band, label) or None."""
    maturities = spawn.get("Maturities")
    if not maturities:
        return None

    levels: list[int] = []
    boss_count = 0
    total = 0

    for entry in maturities:
        mat = entry.get("Maturity") or {}
        props = mat.get("Properties") or {}
        total += 1
        if props.get("Boss", False):
            boss_count += 1
        level = props.get("Level")
        if level is not None:
            levels.append(level)

    if total == 0:
        return None
    if boss_count == total:
        return (5, "Boss")
    if not levels:
        return None

    avg = sum(levels) / len(levels)
    thresholds = [5, 15, 35, 70]
    for i, threshold in enumerate(thresholds):
        if avg <= threshold:
            return (i, _DIFFICULTY_LABELS[i])
    return (4, _DIFFICULTY_LABELS[4])


def _make_badge(text: str, fg: str, bg: str) -> QLabel:
    """Create a small colored badge label."""
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"{_BADGE_STYLE} color: {fg}; background-color: {bg};"
    )
    return label


def _build_waypoint(spawn: dict, mob_name: str) -> str:
    """Build a /wp waypoint string from spawn data."""
    coords = deep_get(spawn, "Properties", "Coordinates") or {}
    if not coords:
        coords = deep_get(spawn, "Properties", "Data") or {}
    x = coords.get("Longitude") or coords.get("x") or 0
    y = coords.get("Latitude") or coords.get("y") or 0
    z = coords.get("Altitude") or 0
    planet = (
        deep_get(spawn, "Planet", "Properties", "TechnicalName")
        or deep_get(spawn, "Planet", "Name")
        or ""
    )
    return f"/wp [{planet}, {x}, {y}, {z}, {mob_name}]"


_ICON_SIZE = 14
_BTN_SIZE = 20

_SMALL_BTN_STYLE = (
    f"QPushButton {{ color: {TEXT_MUTED};"
    f" background: transparent; border: 1px solid {BORDER};"
    f" border-radius: 3px; padding: 0; margin: 0; }}"
    f"QPushButton:hover {{ background: {HOVER}; }}"
)


def _make_copy_button(waypoint: str) -> QPushButton:
    """Create a small copy-waypoint button for a table cell."""
    btn = QPushButton()
    btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
    btn.setIcon(svg_icon(COPY_ICON, TEXT_MUTED, _ICON_SIZE))
    btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(waypoint)
    btn.setStyleSheet(_SMALL_BTN_STYLE)

    def _copy():
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(waypoint)
        btn.setIcon(svg_icon(CHECK_ICON, SUCCESS, _ICON_SIZE))
        QTimer.singleShot(
            1500, lambda: btn.setIcon(svg_icon(COPY_ICON, TEXT_MUTED, _ICON_SIZE))
        )

    btn.clicked.connect(_copy)
    return btn


def _make_map_button(spawn_id: int, planet_name: str) -> QPushButton:
    """Create a small 'open on map' button for a table cell."""
    btn = QPushButton()
    btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
    btn.setIcon(svg_icon(MAPS_ICON, TEXT_MUTED, _ICON_SIZE))
    btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Open on map")
    btn.setStyleSheet(_SMALL_BTN_STYLE)

    def _open():
        app = QApplication.instance()
        if not app:
            return
        for w in app.topLevelWidgets():
            if hasattr(w, "_ensure_page"):
                from ..main_window import PAGE_MAPS
                w._sidebar.set_active(PAGE_MAPS)
                maps_page = w._ensure_page(PAGE_MAPS)
                if hasattr(maps_page, "navigate_to_location"):
                    maps_page.navigate_to_location(planet_name, spawn_id)
                break

    btn.clicked.connect(_open)
    return btn


def _build_styled_table(headers: list[str], row_count: int) -> QTableWidget:
    """Create a styled QTableWidget shell (no data filled yet)."""
    table = QTableWidget(row_count, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setStyleSheet(_TABLE_STYLE)
    return table


_BADGE_COL_WIDTH = 120  # fixed width for badge columns (Frequency/Density/Difficulty)


def _finish_table(table: QTableWidget, row_count: int,
                  stretch_col: int = 0,
                  fixed_cols: dict[int, int] | None = None) -> None:
    """Apply sizing to a finished table.

    *fixed_cols*: mapping of column index → pixel width for badge columns.
    """
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    cols = table.columnCount()
    for i in range(cols):
        if fixed_cols and i in fixed_cols:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(i, fixed_cols[i])
        elif i == stretch_col:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    for r in range(row_count):
        table.setRowHeight(r, _TABLE_ROW_HEIGHT)
    content_height = _TABLE_ROW_HEIGHT + row_count * _TABLE_ROW_HEIGHT + 4
    table.setFixedHeight(min(content_height, _TABLE_MAX_HEIGHT))


class MobDetailView(WikiDetailView):
    """Detail view for a single mob entity."""

    _globals_loaded = pyqtSignal(object)    # globals data dict from background thread
    _globals_refreshed = pyqtSignal(object)  # refresh update (partial)
    _loadouts_loaded = pyqtSignal(object)   # list of loadout dicts
    _loadout_evaluated = pyqtSignal(object) # LoadoutStats or None

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, nexus_client=None,
                 config=None, config_path=None, parent=None):
        self._nexus_client = nexus_client
        self._mob_config = config
        self._mob_config_path = config_path
        self._loadouts: list[dict] = []
        self._loadout_stats = None
        self._mat_section = None
        self._mat_flat_data: list[dict] = []
        self._loadout_combo = None
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        mob_type = item.get("Type") or "-"

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/mob/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = [self._make_badge(mob_type)]
        planet = deep_get(item, "Planet", "Name")
        if planet:
            subtitle_widgets.append(self._make_subtitle_text(planet))
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: HP/Level, Level Range, HP Range ---
        level_range, hp_range, lowest_hpl = _maturity_stats(item)

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow(
            "Avg HP/Lvl", _fv(lowest_hpl, 2) if lowest_hpl else "N/A"
        ))
        if level_range:
            if level_range[0] == level_range[1]:
                tier1.add_row(Tier1StatRow("Level", fmt_int(level_range[0])))
            else:
                tier1.add_row(Tier1StatRow(
                    "Level Range", f"{fmt_int(level_range[0])} - {fmt_int(level_range[1])}"
                ))
        if hp_range:
            if hp_range[0] == hp_range[1]:
                tier1.add_row(Tier1StatRow("HP", fmt_int(hp_range[0])))
            else:
                tier1.add_row(Tier1StatRow(
                    "HP Range", f"{fmt_int(hp_range[0])} - {fmt_int(hp_range[1])}"
                ))
        self._add_section(tier1)

        # --- General ---
        is_asteroid = mob_type == "Asteroid"

        general = InfoboxSection("General")
        species = deep_get(item, "Species", "Name")
        if species:
            general.add_row(StatRow("Species", species))
        if planet:
            general.add_row(StatRow("Planet", planet))
        general.add_row(StatRow("Type", mob_type))
        if not is_asteroid:
            apm = deep_get(item, "Properties", "AttacksPerMinute")
            atk_range = deep_get(item, "Properties", "AttackRange")
            aggro_range = deep_get(item, "Properties", "AggressionRange")
            aggro_timer = deep_get(item, "Properties", "AggressionTimer")
            if apm is not None:
                general.add_row(StatRow("Attacks/Min", _fv(apm, 1)))
            if atk_range is not None:
                general.add_row(StatRow("Attack Range", f"{_fv(atk_range, 1)}m"))
            if aggro_range is not None:
                general.add_row(StatRow("Aggro Range", f"{_fv(aggro_range, 1)}m"))
            if aggro_timer:
                general.add_row(StatRow("Aggro Timer", str(aggro_timer)))
        sweatable = deep_get(item, "Properties", "IsSweatable")
        general.add_row(StatRow(
            "Sweatable", fmt_bool(sweatable),
            highlight=(sweatable is True or sweatable == 1),
        ))
        self._add_section(general)

        # --- Skills ---
        if not is_asteroid:
            def_prof = deep_get(item, "DefensiveProfession", "Name")
            scan_prof = deep_get(item, "Species", "Properties", "ScanningProfession")
            loot_prof = deep_get(item, "Species", "Properties", "LootingProfession")
            if def_prof or scan_prof or loot_prof:
                skill_section = InfoboxSection("Skills")
                if def_prof:
                    skill_section.add_row(self._linked_stat_row(
                        "Defense", def_prof, "Profession"))
                if scan_prof:
                    skill_section.add_row(self._linked_stat_row(
                        "Scanning", scan_prof, "Profession"))
                if loot_prof:
                    skill_section.add_row(self._linked_stat_row(
                        "Looting", loot_prof, "Profession"))
                self._add_section(skill_section)

        # --- Damage Breakdown (per-maturity groups, matching web) ---
        maturities = item.get("Maturities") or []
        total_mat_count = len(maturities)
        if not is_asteroid and maturities:
            primary_groups = _get_damage_groups(maturities, "Primary")
            secondary_groups = _get_damage_groups(maturities, "Secondary")
            tertiary_groups = _get_damage_groups(maturities, "Tertiary")

            if primary_groups or secondary_groups or tertiary_groups:
                dmg_section = InfoboxSection("Damage Breakdown")
                for atk_name, groups in (
                    ("Primary", primary_groups),
                    ("Secondary", secondary_groups),
                    ("Tertiary", tertiary_groups),
                ):
                    if not groups:
                        continue
                    for group in groups:
                        mat_label = _format_maturity_label(
                            group["maturities"], total_mat_count
                        )
                        if len(groups) == 1 and not mat_label:
                            label = atk_name
                        else:
                            label = (f"{atk_name} ({mat_label})"
                                     if mat_label else atk_name)
                        dmg_section.add_widget(
                            MobDamageGridWidget(group["spread"], label=label)
                        )
                self._add_section(dmg_section)

        # --- Codex ---
        codex_type = deep_get(item, "Species", "Properties", "CodexType")
        if codex_type:
            codex_section = InfoboxSection("Codex")
            codex_section.add_row(StatRow("Type", codex_type))
            self._add_section(codex_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Maturities table (pre-sorted by level then health) ---
        if maturities:
            mat_section = DataSection("Maturities", expanded=True)
            mat_section.set_subtitle(f"{len(maturities)} maturities")
            self._mat_section = mat_section

            # Loadout dropdown
            combo = QComboBox()
            combo.setFixedWidth(170)
            combo.setStyleSheet(
                f"QComboBox {{ background-color: {PRIMARY}; color: {TEXT};"
                f" border: 1px solid {BORDER}; border-radius: 4px;"
                f" padding: 2px 6px; font-size: 12px; }}"
                f"QComboBox:focus {{ border-color: {ACCENT}; }}"
                f"QComboBox QAbstractItemView {{ background-color: {PRIMARY};"
                f" color: {TEXT}; selection-background-color: {HOVER}; }}"
            )
            combo.addItem("No loadout", None)
            combo.currentIndexChanged.connect(self._on_maturity_loadout_changed)
            mat_section.add_header_widget(combo)
            self._loadout_combo = combo

            # Build flat maturity data
            flat = []
            for m in maturities:
                m_name = m.get("Name") or "Single Maturity"
                level = deep_get(m, "Properties", "Level")
                hp = deep_get(m, "Properties", "Health")
                hpl = hp / level if hp and level and level > 0 else None
                primary = None
                for a in (m.get("Attacks") or []):
                    if a.get("Name") == "Primary" or primary is None:
                        td = a.get("TotalDamage")
                        if td is not None:
                            primary = td
                defense = deep_get(m, "Properties", "Defense")
                total_def = 0
                if defense:
                    total_def = sum(
                        v for v in defense.values()
                        if isinstance(v, (int, float))
                    )
                flat.append({
                    "name": m_name,
                    "level": level,
                    "hp": hp,
                    "hpl": hpl,
                    "damage": primary,
                    "defense": total_def if total_def > 0 else None,
                })
            self._mat_flat_data = flat
            mat_section.set_content(make_section_table(
                [
                    ColumnDef("name", "Name", main=True),
                    ColumnDef("level", "Level", format=lambda v: fmt_int(v)),
                    ColumnDef("hp", "HP", format=lambda v: fmt_int(v)),
                    ColumnDef("hpl", "HP/Lvl", format=lambda v: f"{v:.2f}" if v else "-"),
                    ColumnDef("damage", "Damage", format=lambda v: _fv(v, 1) if v else "-"),
                    ColumnDef("defense", "Defense", format=lambda v: _fv(v, 1) if v else "-"),
                ],
                flat,
                default_sort=("level", "ASC"),
            ))
            self._add_article_section(mat_section)

            # Async: fetch loadouts
            self._loadouts_loaded.connect(self._on_loadouts_loaded)
            self._loadout_evaluated.connect(self._on_loadout_evaluated)
            if self._nexus_client:
                threading.Thread(
                    target=lambda: self._loadouts_loaded.emit(
                        self._nexus_client.get_loadouts() or []
                    ),
                    daemon=True, name="mob-loadouts",
                ).start()

        # --- Locations / Spawns table ---
        spawns = item.get("Spawns") or []
        if spawns:
            loc_section = DataSection("Locations", expanded=True)
            loc_section.set_subtitle(f"{len(spawns)} locations")
            loc_headers = ["Location", "Maturities", "Density", "Difficulty", "", ""]
            table = _build_styled_table(loc_headers, len(spawns))

            for r, s in enumerate(spawns):
                # Location name (shortened to mob names only)
                raw_name = (
                    deep_get(s, "Location", "Name")
                    or s.get("Name") or "-"
                )
                mobs = _parse_mob_area_name(raw_name)
                short_name = ", ".join(mobs) if mobs else raw_name
                table.setItem(r, 0, QTableWidgetItem(short_name))

                # Maturities (only for current mob)
                mat_text = _spawn_maturities_for_mob(s, name)
                table.setItem(r, 1, QTableWidgetItem(mat_text))

                # Density badge
                density = (
                    deep_get(s, "Properties", "Density")
                    or s.get("Density")
                )
                if density and density in _DENSITY_LABELS:
                    d_label = _DENSITY_LABELS[density]
                    fg, bg = _DENSITY_COLORS[density]
                    table.setCellWidget(r, 2, _make_badge(d_label, fg, bg))
                else:
                    table.setItem(r, 2, QTableWidgetItem("N/A"))

                # Difficulty badge
                diff = _spawn_difficulty(s)
                if diff:
                    band, d_label = diff
                    fg, bg = _DIFFICULTY_COLORS[band]
                    table.setCellWidget(r, 3, _make_badge(d_label, fg, bg))
                else:
                    table.setItem(r, 3, QTableWidgetItem("N/A"))

                # Copy waypoint button
                waypoint = _build_waypoint(s, name)
                table.setCellWidget(r, 4, _make_copy_button(waypoint))

                # Open on map button
                spawn_id = s.get("Id")
                spawn_planet = deep_get(s, "Planet", "Name") or ""
                table.setCellWidget(r, 5, _make_map_button(spawn_id, spawn_planet))

            _ACTION_COL_WIDTH = 42
            _finish_table(table, len(spawns), stretch_col=0,
                         fixed_cols={2: _BADGE_COL_WIDTH,
                                     3: _BADGE_COL_WIDTH,
                                     4: _ACTION_COL_WIDTH,
                                     5: _ACTION_COL_WIDTH})
            loc_section.set_content(table)
            self._add_article_section(loc_section)

        # --- Loots table ---
        loots = item.get("Loots") or []
        if loots:
            # Sort by frequency (most common first)
            freq_order = {
                "Always": 0, "Very often": 1, "Often": 2, "Common": 3,
                "Uncommon": 4, "Rare": 5, "Very Rare": 6, "Very rare": 6,
                "Extremely rare": 7, "Discontinued": 8,
            }
            sorted_loots = sorted(
                loots, key=lambda l: freq_order.get(l.get("Frequency", ""), 99)
            )

            loot_section = DataSection("Loots", expanded=True)
            loot_section.set_subtitle(f"{len(sorted_loots)} items")
            loot_headers = ["Item", "Frequency"]
            table = _build_styled_table(loot_headers, len(sorted_loots))

            for r, l in enumerate(sorted_loots):
                l_name = (
                    deep_get(l, "Item", "Name") or l.get("Name") or "-"
                )
                l_type = deep_get(l, "Item", "Type") or "Material"
                item_widget = QTableWidgetItem(str(l_name))
                item_widget.setForeground(QColor(ACCENT))
                item_widget.setData(Qt.ItemDataRole.UserRole, l_type)
                table.setItem(r, 0, item_widget)

                frequency = l.get("Frequency") or ""
                if frequency and frequency in _FREQUENCY_COLORS:
                    fg, bg = _FREQUENCY_COLORS[frequency]
                    table.setCellWidget(
                        r, 1, _make_badge(frequency, fg, bg)
                    )
                else:
                    table.setItem(
                        r, 1, QTableWidgetItem(frequency or "-")
                    )

            _finish_table(table, len(sorted_loots), stretch_col=0,
                         fixed_cols={1: _BADGE_COL_WIDTH})
            table.cellDoubleClicked.connect(
                lambda row, col, t=table: self.entity_navigate.emit(
                    {"Name": t.item(row, 0).text(),
                     "Type": t.item(row, 0).data(Qt.ItemDataRole.UserRole) or "Material"}
                ) if t.item(row, 0) else None
            )
            loot_section.set_content(table)
            self._add_article_section(loot_section)

        # --- Globals section (async) ---
        if self._data_client and name:
            self._globals_section = DataSection("Globals", expanded=False)
            self._globals_section.set_subtitle("Global loot events")
            self._globals_section.set_loading()
            self._add_article_section(self._globals_section)
            self._globals_period = "30d"
            self._globals_mob_name = name
            self._globals_loaded.connect(self._on_globals_loaded)
            self._fetch_globals()

    # --- Globals helpers ---

    def _fetch_globals(self):
        dc = self._data_client
        mob_name = self._globals_mob_name
        period = self._globals_period

        def fetch():
            data = dc.get_mob_globals(mob_name, period=period)
            self._globals_loaded.emit(data)

        threading.Thread(
            target=fetch, daemon=True, name="wiki-mob-globals",
        ).start()

    def _on_globals_loaded(self, data: dict):
        section = getattr(self, "_globals_section", None)
        if not section:
            return
        content = self._build_globals_content(data)
        section.set_content(content)
        summary = data.get("summary") or {}
        count = summary.get("total_count", 0)
        if count:
            section.set_subtitle(f"{count:,} globals")
            self._start_globals_refresh()
        else:
            section.set_subtitle("No globals")

    def _build_globals_content(self, data: dict) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        summary = data.get("summary") or {}
        if not summary or summary.get("total_count", 0) == 0:
            # Distinguish "no data ever" from "request failed"
            msg = ("Failed to load globals \u2014 try a shorter period"
                   if not data else "No globals recorded for this mob")
            lbl = QLabel(msg)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return container

        # Period selector
        period_row = QWidget()
        period_row.setStyleSheet("background: transparent;")
        pl = QHBoxLayout(period_row)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(4)
        period_label = QLabel("PERIOD")
        period_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.3px; background: transparent;"
        )
        pl.addWidget(period_label)
        for p in ("24h", "7d", "30d", "90d", "1y", "all"):
            btn = QPushButton(p)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            active = p == self._globals_period
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {ACCENT if active else 'transparent'};"
                f"  color: {'#fff' if active else TEXT_MUTED};"
                f"  border: 1px solid {ACCENT if active else BORDER};"
                f"  border-radius: 3px; font-size: 11px;"
                f"  padding: 2px 10px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  color: {'#fff' if active else TEXT};"
                f"  border-color: {ACCENT};"
                f"}}"
            )
            btn.clicked.connect(
                lambda checked=False, period=p: self._on_globals_period_changed(period)
            )
            pl.addWidget(btn)
        pl.addStretch(1)
        layout.addWidget(period_row)

        # Summary stats row
        stats_row = QWidget()
        stats_row.setStyleSheet(
            f"background: {SECONDARY}; border-radius: 6px;"
        )
        sl = QHBoxLayout(stats_row)
        sl.setContentsMargins(8, 6, 8, 6)
        sl.setSpacing(8)
        stats = [
            ("Globals", f"{summary.get('total_count') or 0:,}"),
            ("Total", f"{_format_ped(summary.get('total_value') or 0)} PED"),
            ("Avg", f"{_format_ped(summary.get('avg_value') or 0)} PED"),
            ("Highest", f"{_format_ped(summary.get('max_value') or 0)} PED"),
            ("HoF", f"{summary.get('hof_count') or 0:,}"),
            ("ATH", f"{summary.get('ath_count') or 0:,}"),
        ]
        self._globals_stat_labels: dict[str, QLabel] = {}
        for label, value in stats:
            card = QWidget()
            card.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.setSpacing(2)
            val_lbl = QLabel(value)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 15px; font-weight: 700;"
                " background: transparent;"
            )
            cl.addWidget(val_lbl)
            self._globals_stat_labels[label] = val_lbl
            label_lbl = QLabel(label.upper())
            label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600;"
                " letter-spacing: 0.3px; background: transparent;"
            )
            cl.addWidget(label_lbl)
            sl.addWidget(card)
        layout.addWidget(stats_row)

        # Activity chart
        activity = data.get("activity") or []
        if activity:
            chart_label = QLabel("Activity")
            chart_label.setStyleSheet(
                f"color: {TEXT}; font-size: 14px; font-weight: 600;"
                " background: transparent;"
            )
            layout.addWidget(chart_label)

            chart = MultiLineChart()
            chart.setFixedHeight(160)
            count_points = []
            value_points = []
            for a in activity:
                if not a.get("bucket") or a.get("count") is None:
                    continue
                ts = int(datetime.fromisoformat(
                    a["bucket"].replace("Z", "+00:00")
                ).timestamp())
                count_points.append((ts, float(a["count"])))
                value_points.append((ts, float(a.get("value", 0))))
            series = []
            if count_points:
                series.append(ChartSeries("Count", ACCENT, count_points))
            if value_points and any(v > 0 for _, v in value_points):
                series.append(ChartSeries(
                    "Value (PED)", SUCCESS, value_points,
                    y_axis='right', dash_pattern=[6, 3],
                ))
            if series:
                chart.set_data(series)
                chart.set_smooth(True)
            layout.addWidget(chart)

        # Top players + recent side by side
        top_players = data.get("top_players") or []
        recent = data.get("recent") or []

        if top_players or recent:
            grid = QWidget()
            grid.setStyleSheet("background: transparent;")
            gl = QHBoxLayout(grid)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setSpacing(12)
            gl.setAlignment(Qt.AlignmentFlag.AlignTop)

            if top_players:
                self._globals_top_players = top_players
                self._globals_top_page = 1
                self._globals_top_page_size = 10
                self._globals_top_sort = "value"

                top_widget = QWidget()
                top_widget.setStyleSheet("background: transparent;")
                tw_layout = QVBoxLayout(top_widget)
                tw_layout.setContentsMargins(0, 0, 0, 0)
                tw_layout.setSpacing(4)

                # Header row: label + sort toggle
                top_header = QWidget()
                top_header.setStyleSheet("background: transparent;")
                th_layout = QHBoxLayout(top_header)
                th_layout.setContentsMargins(0, 0, 0, 0)
                th_layout.setSpacing(8)
                top_label = QLabel("Top Players")
                top_label.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px; font-weight: 600;"
                    " background: transparent;"
                )
                th_layout.addWidget(top_label)
                th_layout.addStretch(1)

                # Sort toggle group
                self._globals_sort_btns: list[QPushButton] = []
                for sort_key, sort_label in [("value", "Total"), ("count", "Count"), ("best_value", "Best")]:
                    sbtn = QPushButton(sort_label)
                    sbtn.setCursor(Qt.CursorShape.PointingHandCursor)
                    active = sort_key == self._globals_top_sort
                    sbtn.setStyleSheet(self._sort_btn_style(active))
                    sbtn.clicked.connect(
                        lambda checked=False, k=sort_key: self._on_top_players_sort(k)
                    )
                    th_layout.addWidget(sbtn)
                    self._globals_sort_btns.append((sbtn, sort_key))
                tw_layout.addWidget(top_header)

                sorted_players = sorted(top_players, key=lambda p: p.get("value", 0), reverse=True)
                page = sorted_players[:self._globals_top_page_size]
                self._globals_top_table = make_section_table(
                    self._top_players_columns(),
                    self._top_players_rows(page),
                    max_visible_rows=10,
                    searchable=False,
                    default_sort=None,
                )
                tw_layout.addWidget(self._globals_top_table)

                # Pagination row
                tw_layout.addWidget(self._build_pagination(
                    "top", len(sorted_players), self._globals_top_page_size,
                ))

                gl.addWidget(top_widget, 1, Qt.AlignmentFlag.AlignTop)

            if recent:
                self._globals_recent_data = recent
                self._globals_recent_page = 1
                self._globals_recent_page_size = 10

                rec_widget = QWidget()
                rec_widget.setStyleSheet("background: transparent;")
                rw_layout = QVBoxLayout(rec_widget)
                rw_layout.setContentsMargins(0, 0, 0, 0)
                rw_layout.setSpacing(4)
                rec_header = QWidget()
                rec_header.setStyleSheet("background: transparent;")
                rh_layout = QHBoxLayout(rec_header)
                rh_layout.setContentsMargins(0, 0, 0, 0)
                rh_layout.setSpacing(8)
                rec_label = QLabel("Recent Globals")
                rec_label.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px; font-weight: 600;"
                    " background: transparent;"
                )
                rh_layout.addWidget(rec_label)
                rh_layout.addStretch(1)
                # Match Top Players header height (which includes sort buttons)
                if top_players:
                    rec_header.setFixedHeight(top_header.sizeHint().height())
                rw_layout.addWidget(rec_header)
                page_data = recent[:self._globals_recent_page_size]
                self._globals_recent_table = make_section_table(
                    self._recent_columns(),
                    self._recent_rows(page_data),
                    max_visible_rows=10,
                    searchable=False,
                    default_sort=None,
                )
                rw_layout.addWidget(self._globals_recent_table)

                # Pagination row
                rw_layout.addWidget(self._build_pagination(
                    "recent", len(recent), self._globals_recent_page_size,
                ))

                gl.addWidget(rec_widget, 1, Qt.AlignmentFlag.AlignTop)

            layout.addWidget(grid)

        return container

    # --- Globals table helpers ---

    @staticmethod
    def _top_players_columns() -> list[ColumnDef]:
        return [
            ColumnDef("player", "Player", main=True),
            ColumnDef("count", "#",
                      format=lambda v: f"{v:,}" if v else "-"),
            ColumnDef("value", "Total",
                      format=lambda v: f"{_format_ped(v)} PED" if v else "-"),
            ColumnDef("best_value", "Best",
                      format=lambda v: f"{_format_ped(v)} PED" if v else "-"),
        ]

    @staticmethod
    def _top_players_rows(players: list[dict]) -> list[dict]:
        return [
            {
                "player": ("[T] " if p.get("is_team") else "") + (p.get("player") or "?"),
                "count": p.get("count", 0),
                "value": p.get("value", 0),
                "best_value": p.get("best_value", 0),
            }
            for p in players
        ]

    @staticmethod
    def _recent_columns() -> list[ColumnDef]:
        return [
            ColumnDef("player", "Player", main=True),
            ColumnDef("value", "Value",
                      format=lambda v: f"{_format_ped(v)} PED" if v else "-"),
            ColumnDef("badge", ""),
            ColumnDef("time", "Time"),
        ]

    @staticmethod
    def _recent_rows(recent: list[dict]) -> list[dict]:
        return [
            {
                "player": ("[T] " if g.get("type") == "team_kill" else "")
                          + (g.get("player") or "?"),
                "value": g.get("value", 0),
                "badge": ("ATH" if g.get("ath")
                          else "HoF" if g.get("hof") else ""),
                "time": _time_ago(g.get("timestamp", "")),
            }
            for g in recent
        ]

    @staticmethod
    def _page_btn_style() -> str:
        return (
            f"QPushButton {{"
            f"  background: transparent; color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER}; border-radius: 3px;"
            f"  font-size: 14px; font-weight: 700;"
            f"  padding: 2px 8px;"
            f"}}"
            f"QPushButton:hover {{ color: {TEXT}; border-color: {ACCENT}; }}"
            f"QPushButton:disabled {{ color: {BORDER}; border-color: {BORDER}; }}"
        )

    @staticmethod
    def _sort_btn_style(active: bool) -> str:
        return (
            f"QPushButton {{"
            f"  background: {ACCENT if active else 'transparent'};"
            f"  color: {'#fff' if active else TEXT_MUTED};"
            f"  border: 1px solid {ACCENT if active else BORDER};"
            f"  border-radius: 3px; font-size: 11px;"
            f"  padding: 1px 8px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  color: {'#fff' if active else TEXT};"
            f"  border-color: {ACCENT};"
            f"}}"
        )

    def _build_pagination(self, prefix: str, total_items: int, page_size: int) -> QWidget:
        """Build a Prev / page / Next pagination row."""
        total_pages = max(1, -(-total_items // page_size))
        page_row = QWidget()
        page_row.setStyleSheet("background: transparent;")
        pr_layout = QHBoxLayout(page_row)
        pr_layout.setContentsMargins(0, 2, 0, 0)
        pr_layout.setSpacing(6)
        pr_layout.addStretch(1)

        if total_pages > 1:
            prev_btn = QPushButton("\u2039")
            prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            prev_btn.setEnabled(False)
            prev_btn.setStyleSheet(self._page_btn_style())
            prev_btn.clicked.connect(lambda: self._on_page_change(prefix, -1))
            pr_layout.addWidget(prev_btn)

            page_lbl = QLabel(f"1 / {total_pages}")
            page_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
            )
            pr_layout.addWidget(page_lbl)

            next_btn = QPushButton("\u203a")
            next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            next_btn.setEnabled(total_pages > 1)
            next_btn.setStyleSheet(self._page_btn_style())
            next_btn.clicked.connect(lambda: self._on_page_change(prefix, 1))
            pr_layout.addWidget(next_btn)

            setattr(self, f"_globals_{prefix}_prev_btn", prev_btn)
            setattr(self, f"_globals_{prefix}_next_btn", next_btn)
            setattr(self, f"_globals_{prefix}_page_lbl", page_lbl)

        pr_layout.addStretch(1)
        return page_row

    def _on_page_change(self, prefix: str, delta: int):
        """Generic page change handler for 'top' or 'recent' tables."""
        if prefix == "top":
            sort_key = getattr(self, "_globals_top_sort", "value")
            all_data = sorted(
                getattr(self, "_globals_top_players", []),
                key=lambda p: p.get(sort_key, 0), reverse=True,
            )
            ps = self._globals_top_page_size
            page_attr = "_globals_top_page"
            table_attr = "_globals_top_table"
            row_fn = self._top_players_rows
        else:
            all_data = getattr(self, "_globals_recent_data", [])
            ps = self._globals_recent_page_size
            page_attr = "_globals_recent_page"
            table_attr = "_globals_recent_table"
            row_fn = self._recent_rows

        total_pages = max(1, -(-len(all_data) // ps))
        cur = getattr(self, page_attr, 1)
        new_page = max(1, min(total_pages, cur + delta))
        setattr(self, page_attr, new_page)
        start = (new_page - 1) * ps

        table = getattr(self, table_attr, None)
        if table:
            # Disable updates on the table and its scroll ancestor so the
            # rebuild does not cause visible flicker or scroll jumps.
            from PyQt6.QtWidgets import QApplication
            prev_focus = QApplication.focusWidget()
            table.setUpdatesEnabled(False)
            table.set_data(row_fn(all_data[start:start + ps]))
            table.setUpdatesEnabled(True)
            if prev_focus and prev_focus is not QApplication.focusWidget():
                prev_focus.setFocus()

        lbl = getattr(self, f"_globals_{prefix}_page_lbl", None)
        if lbl:
            lbl.setText(f"{new_page} / {total_pages}")
        prev_btn = getattr(self, f"_globals_{prefix}_prev_btn", None)
        if prev_btn:
            prev_btn.setEnabled(new_page > 1)
        next_btn = getattr(self, f"_globals_{prefix}_next_btn", None)
        if next_btn:
            next_btn.setEnabled(new_page < total_pages)

    def _on_top_players_sort(self, sort_key: str):
        """Change top players sort field and reset to page 1."""
        if getattr(self, "_globals_top_sort", "value") == sort_key:
            return
        self._globals_top_sort = sort_key
        self._globals_top_page = 1

        # Update button styles
        for sbtn, key in getattr(self, "_globals_sort_btns", []):
            sbtn.setStyleSheet(self._sort_btn_style(key == sort_key))

        # Re-sort and show page 1
        players = getattr(self, "_globals_top_players", [])
        sorted_players = sorted(players, key=lambda p: p.get(sort_key, 0), reverse=True)
        ps = self._globals_top_page_size
        table = getattr(self, "_globals_top_table", None)
        if table:
            table.setUpdatesEnabled(False)
            table.set_data(self._top_players_rows(sorted_players[:ps]))
            table.setUpdatesEnabled(True)

        # Update pagination
        total_pages = max(1, -(-len(sorted_players) // ps))
        lbl = getattr(self, "_globals_top_page_lbl", None)
        if lbl:
            lbl.setText(f"1 / {total_pages}")
        prev_btn = getattr(self, "_globals_top_prev_btn", None)
        if prev_btn:
            prev_btn.setEnabled(False)
        next_btn = getattr(self, "_globals_top_next_btn", None)
        if next_btn:
            next_btn.setEnabled(total_pages > 1)

    def _on_globals_period_changed(self, period: str):
        self._globals_period = period
        self._stop_globals_refresh()
        section = getattr(self, "_globals_section", None)
        if section:
            section.set_loading()
        self._fetch_globals()

    # --- Auto-refresh ---

    _GLOBALS_REFRESH_MS = 60_000

    def _start_globals_refresh(self):
        self._stop_globals_refresh()
        if not getattr(self, "_globals_refresh_connected", False):
            self._globals_refreshed.connect(self._on_globals_refreshed)
            self._globals_refresh_connected = True
        timer = QTimer(self)
        timer.timeout.connect(self._refresh_globals)
        timer.start(self._GLOBALS_REFRESH_MS)
        self._globals_refresh_timer = timer

    def _stop_globals_refresh(self):
        timer = getattr(self, "_globals_refresh_timer", None)
        if timer:
            timer.stop()
            self._globals_refresh_timer = None

    def _refresh_globals(self):
        dc = self._data_client
        mob_name = self._globals_mob_name
        period = self._globals_period
        if not dc or not mob_name:
            return

        def fetch():
            data = dc.get_mob_globals(mob_name, period=period, force_refresh=True)
            self._globals_refreshed.emit(data)

        threading.Thread(
            target=fetch, daemon=True, name="wiki-mob-globals-refresh",
        ).start()

    def _on_globals_refreshed(self, data: dict):
        if not data:
            return
        # Update summary stat labels
        summary = data.get("summary") or {}
        if not summary:
            return
        stat_map = {
            "Globals": f"{summary.get('total_count', 0):,}",
            "Total": f"{_format_ped(summary.get('total_value', 0))} PED",
            "Avg": f"{_format_ped(summary.get('avg_value', 0))} PED",
            "Highest": f"{_format_ped(summary.get('max_value', 0))} PED",
            "HoF": f"{summary.get('hof_count', 0):,}",
            "ATH": f"{summary.get('ath_count', 0):,}",
        }
        labels = getattr(self, "_globals_stat_labels", {})
        for key, value in stat_map.items():
            lbl = labels.get(key)
            if lbl:
                lbl.setText(value)

        # Update section subtitle
        section = getattr(self, "_globals_section", None)
        count = summary.get("total_count", 0)
        if section and count:
            section.set_subtitle(f"{count:,} globals")

        # Update recent table
        recent = data.get("recent") or []
        if recent:
            self._globals_recent_data = recent
            ps = getattr(self, "_globals_recent_page_size", 10)
            page = getattr(self, "_globals_recent_page", 1)
            total_pages = max(1, -(-len(recent) // ps))
            if page > total_pages:
                self._globals_recent_page = total_pages
                page = total_pages
            start = (page - 1) * ps
            rec_table = getattr(self, "_globals_recent_table", None)
            if rec_table:
                rec_table.set_data(self._recent_rows(recent[start:start + ps]))
            lbl = getattr(self, "_globals_recent_page_lbl", None)
            if lbl:
                lbl.setText(f"{page} / {total_pages}")

        # Update top players
        top_players = data.get("top_players") or []
        if top_players:
            self._globals_top_players = top_players
            sort_key = getattr(self, "_globals_top_sort", "value")
            sorted_players = sorted(top_players, key=lambda p: p.get(sort_key, 0), reverse=True)
            ps = getattr(self, "_globals_top_page_size", 10)
            total_pages = max(1, -(-len(sorted_players) // ps))
            page = getattr(self, "_globals_top_page", 1)
            if page > total_pages:
                self._globals_top_page = total_pages
                page = total_pages
            start = (page - 1) * ps
            table = getattr(self, "_globals_top_table", None)
            if table:
                table.set_data(self._top_players_rows(sorted_players[start:start + ps]))
            lbl = getattr(self, "_globals_top_page_lbl", None)
            if lbl:
                lbl.setText(f"{page} / {total_pages}")

    # --- Loadout-based kill stats ---

    def _on_loadouts_loaded(self, loadouts: list):
        """Populate the loadout combo box with fetched loadouts."""
        if not loadouts or not self._loadout_combo:
            return
        self._loadouts = loadouts
        combo = self._loadout_combo
        combo.blockSignals(True)
        for lo in loadouts:
            data = lo.get("data") or lo
            raw_name = lo.get("name") or data.get("Name") or ""
            # Auto-generate name from weapon/armor when using default name
            if not raw_name or raw_name == "New Loadout":
                weapon = (data.get("Gear") or {}).get("Weapon", {}).get("Name")
                armor = (data.get("Gear") or {}).get("Armor", {}).get("SetName")
                if weapon and armor:
                    raw_name = f"{weapon} ({armor})"
                elif weapon:
                    raw_name = weapon
                else:
                    raw_name = raw_name or "New Loadout"
            lo_id = lo.get("id") or lo.get("Id") or ""
            combo.addItem(raw_name, str(lo_id))

        # Restore saved selection
        saved_id = (
            self._mob_config.mob_maturity_loadout_id
            if self._mob_config else None
        )
        if saved_id:
            for i in range(combo.count()):
                if combo.itemData(i) == saved_id:
                    combo.setCurrentIndex(i)
                    break
        combo.blockSignals(False)

        # Evaluate if there's a saved selection
        if saved_id and combo.currentData() == saved_id:
            self._evaluate_loadout(saved_id)

    def _on_maturity_loadout_changed(self, index: int):
        """Handle loadout combo selection change."""
        if not self._loadout_combo:
            return
        lo_id = self._loadout_combo.itemData(index)

        # Persist preference
        if self._mob_config and self._mob_config_path:
            from ...core.config import save_config
            self._mob_config.mob_maturity_loadout_id = lo_id
            save_config(self._mob_config, self._mob_config_path)

        if not lo_id:
            self._loadout_stats = None
            self._rebuild_maturity_table()
            return

        self._evaluate_loadout(lo_id)

    def _evaluate_loadout(self, lo_id: str):
        """Evaluate loadout stats in a background thread."""
        lo_data = None
        for lo in self._loadouts:
            lid = str(lo.get("id") or lo.get("Id") or "")
            if lid == lo_id:
                lo_data = lo.get("data") or lo
                break
        if not lo_data:
            self._loadout_stats = None
            self._rebuild_maturity_table()
            return

        dc = self._data_client

        def work():
            try:
                from ...loadout.calculator import LoadoutCalculator
                calc = LoadoutCalculator()
                entities = {
                    "weapons": dc.get_weapons() if dc else [],
                    "amplifiers": dc.get_amplifiers() if dc else [],
                    "scopes_sights": dc.get_scopes_and_sights() if dc else [],
                    "absorbers": dc.get_absorbers() if dc else [],
                    "implants": dc.get_implants() if dc else [],
                    "armor_sets": dc.get_armor_sets() if dc else [],
                    "armors": dc.get_armors() if dc else [],
                    "armor_platings": dc.get_armor_platings() if dc else [],
                    "medical_tools": dc.get_medical_tools() if dc else [],
                    "medical_chips": dc.get_medical_chips() if dc else [],
                    "clothing": dc.get_clothing() if dc else [],
                    "pets": dc.get_pets() if dc else [],
                    "stimulants": dc.get_stimulants() if dc else [],
                    "effects": dc.get_effects() if dc else [],
                }
                stats = calc.evaluate(lo_data, entities)
                self._loadout_evaluated.emit(stats)
            except Exception:
                import traceback
                traceback.print_exc()
                self._loadout_evaluated.emit(None)

        threading.Thread(target=work, daemon=True, name="mob-loadout-eval").start()

    def _on_loadout_evaluated(self, stats):
        """Handle loadout evaluation result — rebuild maturity table."""
        self._loadout_stats = stats
        self._rebuild_maturity_table()

    def _rebuild_maturity_table(self):
        """Rebuild the maturity table with or without kill stat columns."""
        if not self._mat_section or not self._mat_flat_data:
            return

        import math
        stats = self._loadout_stats
        flat = self._mat_flat_data

        columns = [
            ColumnDef("name", "Name", main=True),
            ColumnDef("level", "Level", format=lambda v: fmt_int(v)),
            ColumnDef("hp", "HP", format=lambda v: fmt_int(v)),
            ColumnDef("hpl", "HP/Lvl", format=lambda v: f"{v:.2f}" if v else "-"),
            ColumnDef("damage", "Damage", format=lambda v: _fv(v, 1) if v else "-"),
            ColumnDef("defense", "Defense", format=lambda v: _fv(v, 1) if v else "-"),
        ]

        dpp = (getattr(stats, "dpp", 0) or 0) if stats else 0
        eff_dmg = (getattr(stats, "effective_damage", 0) or 0) if stats else 0
        reload_time = (getattr(stats, "reload", 0) or 0) if stats else 0

        if stats and (dpp > 0 or eff_dmg > 0):
            columns.extend([
                ColumnDef("ctk", "Cost/kill", format=lambda v: f"{v:.2f}" if v else "-"),
                ColumnDef("stk", "Shots/kill", format=lambda v: str(int(v)) if v else "-"),
                ColumnDef("ttk", "Time/kill", format=lambda v: f"{v:.1f}s" if v else "-"),
            ])
            augmented = []
            for row in flat:
                new_row = dict(row)
                hp = row.get("hp")
                if hp and eff_dmg > 0:
                    stk = math.ceil(hp / eff_dmg)
                    new_row["stk"] = stk
                    new_row["ttk"] = (stk - 1) * reload_time if reload_time > 0 else None
                else:
                    new_row["stk"] = None
                    new_row["ttk"] = None
                new_row["ctk"] = (hp / dpp) / 100 if hp and dpp > 0 else None
                augmented.append(new_row)
            flat = augmented

        self._mat_section.set_content(make_section_table(
            columns, flat, default_sort=("level", "ASC"),
        ))
