"""Mob entity detail page — maturities, damage, spawns, loots, codex."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QApplication,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from ..icons import svg_icon, MAPS as MAPS_ICON, COPY as COPY_ICON, CHECK as CHECK_ICON
from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    MobDamageGridWidget, make_compact_table,
    _TABLE_ROW_HEIGHT, _TABLE_MAX_HEIGHT,
)
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
_DENSITY_LABELS = {1: "Low", 2: "Medium", 3: "High"}
_DENSITY_COLORS = {
    1: ("#eab308", "rgba(202, 138, 4, 0.25)"),
    2: ("#22c55e", "rgba(22, 163, 74, 0.25)"),
    3: ("#ef4444", "rgba(220, 38, 38, 0.25)"),
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


# ---------------------------------------------------------------------------
# Maturity aggregation helpers
# ---------------------------------------------------------------------------

def _maturity_stats(item: dict):
    """Extract level range, HP range, and lowest HP/Level from maturities."""
    maturities = item.get("Maturities") or []
    if not maturities:
        return None, None, None, None, None

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

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
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
                    skill_section.add_row(StatRow("Defense", def_prof))
                if scan_prof:
                    skill_section.add_row(StatRow("Scanning", scan_prof))
                if loot_prof:
                    skill_section.add_row(StatRow("Looting", loot_prof))
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
            sorted_mats = sorted(maturities, key=lambda m: (
                deep_get(m, "Properties", "Level") or 0,
                deep_get(m, "Properties", "Health") or 0,
            ))
            mat_section = DataSection("Maturities", expanded=True)
            mat_section.set_subtitle(f"{len(sorted_mats)} maturities")
            headers = ["Name", "Level", "HP", "HP/Lvl", "Damage", "Defense"]
            rows = []
            for m in sorted_mats:
                m_name = m.get("Name") or "Single Maturity"
                level = deep_get(m, "Properties", "Level")
                hp = deep_get(m, "Properties", "Health")
                hpl = f"{hp / level:.2f}" if hp and level and level > 0 else "-"
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
                rows.append([
                    m_name,
                    fmt_int(level),
                    fmt_int(hp),
                    hpl,
                    _fv(primary, 1) if primary else "-",
                    _fv(total_def, 1) if total_def > 0 else "-",
                ])
            mat_section.set_content(make_compact_table(headers, rows))
            self._add_article_section(mat_section)

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
                table.setItem(r, 0, QTableWidgetItem(str(l_name)))

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
            loot_section.set_content(table)
            self._add_article_section(loot_section)
