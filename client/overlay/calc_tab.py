"""Calculator tab content — simplified loadout builder for the detail overlay."""

from __future__ import annotations

import re
import threading
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QSpinBox, QDoubleSpinBox, QPushButton, QComboBox, QSizePolicy,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from .calc_search_input import CalcSearchInput, _item_name
from .detail_overlay import (
    TEXT_COLOR, TEXT_DIM, ACCENT, CONTENT_BG, FOOTER_BG,
)
from ..core.logger import get_logger
from ..loadout.models import LoadoutStats, create_empty_loadout
from ..loadout.calculator import LoadoutCalculator

log = get_logger("CalcTab")

if TYPE_CHECKING:
    from ..api.data_client import DataClient

# Skill level assumed for the simplified calculator
_SKILL_LEVEL = 200  # profession level doesn't matter — we use maxed Hit/Dmg

_DEBOUNCE_MS = 300

# Amp overcap: allow amps with total damage up to this % over the weapon's cap (damage/2)
_AMP_OVERCAP_TOLERANCE = 10  # percent
_OVERCAP_COLOR = "#fbbf24"  # yellow/amber for overcapped amps

_SECTION_STYLE = (
    f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
    f" padding: 2px 0px 0px 0px; background: transparent;"
)
_LABEL_STYLE = (
    f"color: {TEXT_DIM}; font-size: 11px;"
    f" padding: 0px; background: transparent;"
)

_RING_SLOT_RE = re.compile(r"ring|finger", re.IGNORECASE)


def _has_effects(item: dict) -> bool:
    """Check if a clothing/consumable has any effects."""
    if item.get("EffectsOnEquip"):
        return True
    if item.get("EffectsOnConsume"):
        return True
    s = item.get("Set")
    if s and s.get("EffectsOnSetEquip"):
        return True
    return False


def _is_ring(item: dict) -> bool:
    slot = item.get("Properties", {}).get("Slot") or ""
    return bool(_RING_SLOT_RE.search(slot))


def _item_total_damage(item: dict) -> float:
    """Sum all damage types on an item. Returns 0 if no damage data."""
    dmg = item.get("Properties", {}).get("Damage")
    if not dmg:
        return 0
    return (
        (dmg.get("Impact") or 0) + (dmg.get("Cut") or 0)
        + (dmg.get("Stab") or 0) + (dmg.get("Penetration") or 0)
        + (dmg.get("Shrapnel") or 0) + (dmg.get("Burn") or 0)
        + (dmg.get("Cold") or 0) + (dmg.get("Acid") or 0)
        + (dmg.get("Electric") or 0)
    )


def _is_overcapped(amp: dict, weapon: dict) -> bool:
    """Check if an amplifier exceeds the weapon's amp cap (damage/2)."""
    amp_dmg = _item_total_damage(amp)
    weapon_dmg = _item_total_damage(weapon)
    if weapon_dmg <= 0 or amp_dmg <= 0:
        return False
    return 2 * amp_dmg > weapon_dmg


def _filter_amplifiers(
    all_amps: list[dict], weapon: dict, *, filter_overcap: bool = True,
) -> list[dict]:
    """Filter amplifiers to those compatible with the weapon's class/type.

    When filter_overcap is True, also removes amps whose damage exceeds
    the weapon's cap by more than _AMP_OVERCAP_TOLERANCE percent.
    """
    props = weapon.get("Properties", {})
    wclass = props.get("Class", "")
    wtype = props.get("Type", "")
    weapon_dmg = _item_total_damage(weapon) if filter_overcap else 0

    filtered = []
    for amp in all_amps:
        amp_type = amp.get("Properties", {}).get("Type", "")
        if amp_type == "Matrix":
            continue  # matrices handled separately

        # Class/type compatibility
        compatible = False
        if wclass == "Ranged":
            if wtype == "BLP" and amp_type == "BLP":
                compatible = True
            elif wtype != "BLP" and amp_type == "Energy":
                compatible = True
        elif wclass == "Melee" and amp_type == "Melee":
            compatible = True
        elif wclass == "Mindforce" and amp_type == "Mindforce":
            compatible = True

        if not compatible:
            continue

        # Overcap filtering
        if filter_overcap and weapon_dmg > 0:
            amp_dmg = _item_total_damage(amp)
            cap = (1 + _AMP_OVERCAP_TOLERANCE / 100) * weapon_dmg
            if 2 * amp_dmg > cap:
                continue

        filtered.append(amp)
    return filtered


def _filter_matrices(all_amps: list[dict]) -> list[dict]:
    return [a for a in all_amps if a.get("Properties", {}).get("Type") == "Matrix"]


# ---------------------------------------------------------------------------
# Multi-slot list widget (for clothing / consumables)
# ---------------------------------------------------------------------------

class _MultiSlotWidget(QWidget):
    """Widget with add/remove capability for multiple CalcSearchInputs."""

    changed = pyqtSignal()

    def __init__(self, placeholder: str, max_slots: int = 5, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []
        self._placeholder = placeholder
        self._max_slots = max_slots
        self._inputs: list[CalcSearchInput] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._slot_layout = layout

        # Add button
        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(20, 18)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; font-size: 14px; font-weight: bold;"
            f" background: transparent; border: 1px solid #444444; border-radius: 3px;"
            f" padding: 0px; }}"
            f"QPushButton:hover {{ background-color: rgba(60, 60, 90, 180); }}"
        )
        self._add_btn.clicked.connect(self._add_slot)

        # Start with one slot + the add button
        self._add_slot()

    def set_items(self, items: list[dict]):
        self._items = items
        for inp in self._inputs:
            inp.set_items(items)

    def get_selected_names(self) -> list[str]:
        names = []
        for inp in self._inputs:
            name = inp.selected_name()
            if name:
                names.append(name)
        return names

    def _add_slot(self):
        if len(self._inputs) >= self._max_slots:
            return

        row = QWidget()
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(2)

        inp = CalcSearchInput(self._items, self._placeholder)
        inp.item_selected.connect(lambda _item: self.changed.emit())
        row_l.addWidget(inp, 1)

        remove_btn = QPushButton("\u2212")
        remove_btn.setFixedSize(18, 22)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_DIM}; font-size: 14px;"
            f" background: transparent; border: none; padding: 0px; }}"
            f"QPushButton:hover {{ color: #f87171; }}"
        )
        remove_btn.clicked.connect(lambda _, r=row, i=inp: self._remove_slot(r, i))
        row_l.addWidget(remove_btn, 0)

        # Insert before the add button (last widget)
        idx = self._slot_layout.count() - 1
        if idx < 0:
            idx = 0
        self._slot_layout.insertWidget(idx, row)
        self._inputs.append(inp)

        if len(self._inputs) >= self._max_slots:
            self._add_btn.hide()
        # Ensure add button is at the end
        self._slot_layout.removeWidget(self._add_btn)
        self._slot_layout.addWidget(self._add_btn)

    def _remove_slot(self, row: QWidget, inp: CalcSearchInput):
        if len(self._inputs) <= 1:
            inp.clear_selection()
            self.changed.emit()
            return
        self._inputs.remove(inp)
        self._slot_layout.removeWidget(row)
        row.deleteLater()
        if len(self._inputs) < self._max_slots:
            self._add_btn.show()
        self.changed.emit()


# ---------------------------------------------------------------------------
# CalcTab
# ---------------------------------------------------------------------------

class CalcTab(QScrollArea):
    """Calculator tab content — gear selection form.

    Signals:
        stats_updated(LoadoutStats): Emitted when loadout stats are recalculated.
        create_loadout(dict): Emitted when user clicks "Create Loadout".
    """

    stats_updated = pyqtSignal(object)
    create_loadout = pyqtSignal(dict)
    _stats_ready = pyqtSignal(object)

    def __init__(self, *, data_client: DataClient, weapon_item: dict, parent=None):
        super().__init__(parent)
        self._data_client = data_client
        self._weapon_item = weapon_item
        self._weapon_entity: dict | None = None  # full weapon with Properties
        self._calculator: LoadoutCalculator | None = None
        self._entities: dict | None = None
        self._loading = True

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            f"  background: transparent; width: 6px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(80, 80, 100, 160); border-radius: 3px;"
            "  min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}"
        )

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(6, 4, 6, 6)
        self._layout.setSpacing(2)

        # Loading label (shown until data fetched)
        self._loading_lbl = QLabel("Loading data...")
        self._loading_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 13px; background: transparent;"
        )
        self._loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._loading_lbl)

        self.setWidget(self._content)

        # Debounce timer for recalculation
        self._recalc_timer = QTimer()
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.setInterval(_DEBOUNCE_MS)
        self._recalc_timer.timeout.connect(self._recalculate)

        # Cross-thread signal for stats
        self._stats_ready.connect(self._on_stats_ready)

        # Fetch data in background
        threading.Thread(target=self._fetch_data, daemon=True).start()

    # --- Data fetching ---

    def _fetch_data(self):
        dc = self._data_client
        try:
            weapons = dc.get_weapons()
            weapon_name = self._weapon_item.get("Name") or self._weapon_item.get("DisplayName")
            self._weapon_entity = next(
                (w for w in weapons if _item_name(w) == weapon_name), None
            )

            all_amps = dc.get_amplifiers()
            vision_attachments = dc.get_scopes_and_sights()
            scopes = [v for v in vision_attachments
                      if v.get("Properties", {}).get("Type") == "Scope"]
            sights = [v for v in vision_attachments
                      if v.get("Properties", {}).get("Type") == "Sight"]

            # Filter amplifiers by weapon compatibility
            if self._weapon_entity:
                filtered_amps = _filter_amplifiers(
                    all_amps, self._weapon_entity, filter_overcap=True,
                )
                # All compatible amps (no overcap filter) for when checkbox is unchecked
                all_compatible_amps = _filter_amplifiers(
                    all_amps, self._weapon_entity, filter_overcap=False,
                )
            else:
                filtered_amps = [a for a in all_amps
                                 if a.get("Properties", {}).get("Type") != "Matrix"]
                all_compatible_amps = filtered_amps

            matrices = _filter_matrices(all_amps)

            all_clothing = dc.get_clothing()
            clothing_with_effects = [c for c in all_clothing if _has_effects(c)]
            rings = [c for c in all_clothing if _is_ring(c)]
            regular_clothing = [c for c in clothing_with_effects if not _is_ring(c)]

            self._entities = {
                "weapons": weapons,
                "amplifiers": all_amps,  # unfiltered for the evaluator
                "filtered_amplifiers": filtered_amps,
                "all_compatible_amplifiers": all_compatible_amps,
                "matrices": matrices,
                "scopes": scopes,
                "sights": sights,
                "scopes_sights": vision_attachments,
                "absorbers": dc.get_absorbers(),
                "implants": dc.get_implants(),
                "armors": dc.get_armors(),
                "armor_platings": dc.get_armor_platings(),
                "armor_sets": dc.get_armor_sets(),
                "clothing": all_clothing,  # full list for the evaluator
                "clothing_with_effects": regular_clothing,  # filtered for UI selector
                "rings": rings,
                "pets": dc.get_pets(),
                "stimulants": dc.get_stimulants(),
                "medical_tools": dc.get_medical_tools(),
                "effects": dc.get_effects(),
            }
            self._calculator = LoadoutCalculator()
        except Exception:
            log.error("Failed to load calculator data", exc_info=True)
            self._entities = None

        QTimer.singleShot(0, self._on_data_loaded)

    def _on_data_loaded(self):
        self._loading_lbl.hide()
        self._loading = False

        if not self._entities:
            self._loading_lbl.setText("Failed to load data")
            self._loading_lbl.show()
            return

        self._build_form()
        self._schedule_recalc()

    # --- Form building ---

    def _build_form(self):
        ent = self._entities
        weapon = self._weapon_entity
        wclass = weapon.get("Properties", {}).get("Class", "") if weapon else ""

        # Weapon name (read-only)
        weapon_name = self._weapon_item.get("DisplayName") or self._weapon_item.get("Name", "?")
        w_lbl = QLabel(weapon_name)
        w_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            f" background: transparent; padding: 2px 0px;"
        )
        self._layout.addWidget(w_lbl)

        # --- Attachments ---
        self._add_section("ATTACHMENTS")

        # Amp overcap color function — highlights overcapped amps yellow
        amp_color_fn = None
        if weapon:
            amp_color_fn = lambda amp, w=weapon: (
                _OVERCAP_COLOR if _is_overcapped(amp, w) else None
            )

        self._amp_input = self._add_search(
            "Amplifier", ent["filtered_amplifiers"], color_fn=amp_color_fn,
        )

        # Checkbox to toggle overcap filtering
        self._overcap_cb = QCheckBox("Hide overcapped amps")
        self._overcap_cb.setChecked(True)
        self._overcap_cb.setStyleSheet(
            f"QCheckBox {{ color: {TEXT_DIM}; font-size: 11px;"
            f" background: transparent; spacing: 4px; }}"
        )
        self._overcap_cb.stateChanged.connect(self._on_overcap_toggle)
        self._layout.addWidget(self._overcap_cb)

        # Ranged-only: Scope, Sight
        self._scope_input = None
        self._sight_input = None
        if wclass == "Ranged":
            self._scope_input = self._add_search("Scope", ent["scopes"])
            self._sight_input = self._add_search("Sight", ent["sights"])

        self._absorber_input = self._add_search("Absorber", ent["absorbers"])

        # Melee-only: Matrix
        self._matrix_input = None
        if wclass == "Melee":
            self._matrix_input = self._add_search("Matrix", ent["matrices"])

        # Implant — effects apply to all weapons; absorption is Mindforce-only
        self._implant_input = self._add_search("Implant", ent["implants"])

        # --- Enhancers ---
        self._add_section("ENHANCERS")
        self._dmg_enh = self._add_spin("Damage", 0, 10)

        # --- Armor ---
        self._add_section("ARMOR SET")
        self._armor_set_input = self._add_search("Armor Set", ent["armor_sets"])

        # --- Rings ---
        self._add_section("RINGS")
        self._ring_left_input = self._add_search("Left Ring", ent["rings"])
        self._ring_right_input = self._add_search("Right Ring", ent["rings"])

        # --- Clothing ---
        self._add_section("CLOTHING")
        self._clothing_multi = _MultiSlotWidget("Clothing", max_slots=5)
        self._clothing_multi.set_items(ent["clothing_with_effects"])
        self._clothing_multi.changed.connect(self._schedule_recalc)
        self._layout.addWidget(self._clothing_multi)

        # --- Pet ---
        self._add_section("PET")
        self._pet_input = self._add_search("Pet", ent["pets"])
        self._pet_effect_combo = QComboBox()
        self._pet_effect_combo.setFixedHeight(22)
        self._pet_effect_combo.setStyleSheet(
            f"QComboBox {{"
            f"  color: {TEXT_COLOR}; font-size: 13px;"
            f"  background-color: rgba(20, 20, 35, 200);"
            f"  border: 1px solid #444444; border-radius: 3px;"
            f"  padding: 2px 4px;"
            f"}}"
            f"QComboBox::drop-down {{ border: none; width: 16px; }}"
            f"QComboBox QAbstractItemView {{"
            f"  color: {TEXT_COLOR}; background-color: rgba(20, 20, 30, 240);"
            f"  border: 1px solid #555555; selection-background-color: rgba(60, 60, 90, 180);"
            f"}}"
        )
        self._pet_effect_combo.currentIndexChanged.connect(
            lambda _: self._schedule_recalc()
        )
        self._pet_effect_combo.hide()
        self._layout.addWidget(self._pet_effect_combo)

        # --- Consumables ---
        self._add_section("CONSUMABLES")
        self._consumables_multi = _MultiSlotWidget("Consumable", max_slots=5)
        self._consumables_multi.set_items(ent["stimulants"])
        self._consumables_multi.changed.connect(self._schedule_recalc)
        self._layout.addWidget(self._consumables_multi)

        # --- Bonuses ---
        self._add_section("BONUSES")
        self._bonus_dmg = self._add_double_spin("% Damage", 0, 100, suffix="%")
        self._bonus_crit = self._add_double_spin("% Crit Chance", 0, 100, suffix="%")
        self._bonus_crit_dmg = self._add_double_spin("% Crit Damage", 0, 100, suffix="%")
        self._bonus_reload = self._add_double_spin("% Reload", 0, 100, suffix="%")

        # --- Create Loadout button ---
        self._layout.addSpacing(4)
        create_btn = QPushButton("Create Loadout")
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setFixedHeight(24)
        create_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            f"  background-color: rgba(40, 40, 60, 200);"
            f"  border: 1px solid {ACCENT}; border-radius: 4px;"
            f"  padding: 2px 8px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: rgba(60, 60, 90, 200);"
            f"}}"
        )
        create_btn.clicked.connect(self._on_create_loadout)
        self._layout.addWidget(create_btn)

        self._layout.addStretch(1)

    # --- Widget helpers ---

    def _add_section(self, title: str):
        lbl = QLabel(title)
        lbl.setStyleSheet(_SECTION_STYLE)
        self._layout.addWidget(lbl)

    def _add_search(
        self, label: str, items: list[dict], color_fn=None,
    ) -> CalcSearchInput:
        lbl = QLabel(label)
        lbl.setStyleSheet(_LABEL_STYLE)
        self._layout.addWidget(lbl)
        inp = CalcSearchInput(items, f"Search {label.lower()}...", color_fn=color_fn)
        inp.item_selected.connect(lambda _item: self._on_item_changed())
        self._layout.addWidget(inp)
        return inp

    def _add_spin(self, label: str, min_val: int, max_val: int) -> QSpinBox:
        row = QWidget()
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(4)

        lbl = QLabel(label)
        lbl.setStyleSheet(_LABEL_STYLE)
        row_l.addWidget(lbl, 1)

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setFixedSize(48, 22)
        spin.setStyleSheet(
            f"QSpinBox {{"
            f"  color: {TEXT_COLOR}; font-size: 13px;"
            f"  background-color: rgba(20, 20, 35, 200);"
            f"  border: 1px solid #444444; border-radius: 3px;"
            f"  padding: 1px 2px;"
            f"}}"
        )
        spin.valueChanged.connect(lambda _: self._schedule_recalc())
        row_l.addWidget(spin, 0)

        self._layout.addWidget(row)
        return spin

    def _add_double_spin(
        self, label: str, min_val: float, max_val: float,
        suffix: str = "", step: float = 0.5,
    ) -> QDoubleSpinBox:
        row = QWidget()
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(4)

        lbl = QLabel(label)
        lbl.setStyleSheet(_LABEL_STYLE)
        row_l.addWidget(lbl, 1)

        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(1)
        if suffix:
            spin.setSuffix(suffix)
        spin.setFixedSize(64, 22)
        spin.setStyleSheet(
            f"QDoubleSpinBox {{"
            f"  color: {TEXT_COLOR}; font-size: 13px;"
            f"  background-color: rgba(20, 20, 35, 200);"
            f"  border: 1px solid #444444; border-radius: 3px;"
            f"  padding: 1px 2px;"
            f"}}"
        )
        spin.valueChanged.connect(lambda _: self._schedule_recalc())
        row_l.addWidget(spin, 0)

        self._layout.addWidget(row)
        return spin

    # --- Change handlers ---

    def _on_overcap_toggle(self, state: int):
        """Toggle between filtered (hide overcapped) and all compatible amps."""
        if not self._entities:
            return
        hide_overcap = state == Qt.CheckState.Checked.value
        if hide_overcap:
            amps = self._entities["filtered_amplifiers"]
        else:
            amps = self._entities["all_compatible_amplifiers"]
        self._amp_input.set_items(amps)
        # Don't clear selection — if the user already picked an overcapped amp, keep it

    def _on_item_changed(self):
        # Special handling for pet — update effect combo
        pet = self._pet_input.selected_item()
        if pet and pet.get("Effects"):
            effects = pet["Effects"]
            self._pet_effect_combo.blockSignals(True)
            self._pet_effect_combo.clear()
            self._pet_effect_combo.addItem("(no effect)", None)
            for eff in effects:
                name = eff.get("Name", "?")
                strength = (
                    eff.get("Properties", {}).get("Strength")
                    or eff.get("Values", {}).get("Strength")
                    or eff.get("Values", {}).get("Value")
                    or 0
                )
                display = f"{name} ({strength})" if strength else name
                # Store the effect key matching getPetEffectKey in JS
                key = f"{name}::{strength}"
                self._pet_effect_combo.addItem(display, key)
            self._pet_effect_combo.blockSignals(False)
            self._pet_effect_combo.show()
        else:
            self._pet_effect_combo.hide()
            self._pet_effect_combo.clear()

        self._schedule_recalc()

    def _schedule_recalc(self):
        if not self._loading:
            self._recalc_timer.start()

    # --- Loadout building ---

    def _build_loadout(self) -> dict:
        loadout = create_empty_loadout()
        weapon_name = self._weapon_item.get("Name") or self._weapon_item.get("DisplayName")
        loadout["Gear"]["Weapon"]["Name"] = weapon_name

        # Attachments
        amp = self._amp_input.selected_name()
        if amp:
            loadout["Gear"]["Weapon"]["Amplifier"]["Name"] = amp

        if self._scope_input:
            scope = self._scope_input.selected_name()
            if scope:
                loadout["Gear"]["Weapon"]["Scope"]["Name"] = scope
        if self._sight_input:
            sight = self._sight_input.selected_name()
            if sight:
                loadout["Gear"]["Weapon"]["Sight"]["Name"] = sight

        absorber = self._absorber_input.selected_name()
        if absorber:
            loadout["Gear"]["Weapon"]["Absorber"]["Name"] = absorber

        if self._matrix_input:
            matrix = self._matrix_input.selected_name()
            if matrix:
                loadout["Gear"]["Weapon"]["Matrix"]["Name"] = matrix

        if self._implant_input:
            implant = self._implant_input.selected_name()
            if implant:
                loadout["Gear"]["Weapon"]["Implant"]["Name"] = implant

        # Enhancers (damage only)
        loadout["Gear"]["Weapon"]["Enhancers"]["Damage"] = self._dmg_enh.value()

        # Armor set
        armor_set = self._armor_set_input.selected_name()
        if armor_set:
            loadout["Gear"]["Armor"]["SetName"] = armor_set

        # Rings (treated as clothing with Slot/Side)
        clothing_entries = []
        ring_left = self._ring_left_input.selected_name()
        if ring_left:
            clothing_entries.append({"Name": ring_left, "Slot": "Ring", "Side": "Left"})
        ring_right = self._ring_right_input.selected_name()
        if ring_right:
            clothing_entries.append({"Name": ring_right, "Slot": "Ring", "Side": "Right"})

        # Clothing — deduplicate by slot (last selection per slot wins)
        slot_map: dict[str, dict] = {}  # slot -> entry
        unknown_entries: list[dict] = []
        all_clothing = self._entities.get("clothing", [])
        for name in self._clothing_multi.get_selected_names():
            entity = next((c for c in all_clothing if _item_name(c) == name), None)
            slot = entity.get("Properties", {}).get("Slot", "Unknown") if entity else "Unknown"
            entry = {"Name": name, "Slot": slot}
            if slot and slot != "Unknown":
                slot_map[slot] = entry  # replaces any prior item in same slot
            else:
                unknown_entries.append(entry)
        clothing_entries.extend(slot_map.values())
        clothing_entries.extend(unknown_entries)
        loadout["Gear"]["Clothing"] = clothing_entries

        # Pet
        pet = self._pet_input.selected_name()
        if pet:
            loadout["Gear"]["Pet"]["Name"] = pet
            effect_key = self._pet_effect_combo.currentData()
            if effect_key:
                loadout["Gear"]["Pet"]["Effect"] = effect_key

        # Consumables
        loadout["Gear"]["Consumables"] = [
            {"Name": name}
            for name in self._consumables_multi.get_selected_names()
        ]

        # Bonuses
        loadout["Properties"]["BonusDamage"] = self._bonus_dmg.value()
        loadout["Properties"]["BonusCritChance"] = self._bonus_crit.value()
        loadout["Properties"]["BonusCritDamage"] = self._bonus_crit_dmg.value()
        loadout["Properties"]["BonusReload"] = self._bonus_reload.value()

        # Skill — maxed
        loadout["Skill"] = {"Hit": _SKILL_LEVEL, "Dmg": _SKILL_LEVEL, "Heal": _SKILL_LEVEL}

        return loadout

    # --- Recalculation ---

    def _recalculate(self):
        if not self._calculator or not self._entities:
            return
        loadout = self._build_loadout()
        threading.Thread(
            target=self._run_calc, args=(loadout,), daemon=True
        ).start()

    def _run_calc(self, loadout: dict):
        try:
            stats = self._calculator.evaluate(loadout, self._entities)
            self._stats_ready.emit(stats)
        except Exception:
            self._stats_ready.emit(LoadoutStats())

    def _on_stats_ready(self, stats: LoadoutStats):
        self.stats_updated.emit(stats)

    # --- Create loadout ---

    def _on_create_loadout(self):
        loadout = self._build_loadout()
        self.create_loadout.emit(loadout)
