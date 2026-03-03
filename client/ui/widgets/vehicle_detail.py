"""Vehicle entity detail page — speed, passengers, defense, economy."""

from __future__ import annotations

import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

from .wiki_detail import (
    WikiDetailView, InfoboxSection, Tier1StatRow, StatRow, DataSection,
    DefenseBreakdownWidget, build_acquisition_content, build_usage_content,
    exchange_url,
)
from ...data.wiki_columns import (
    deep_get, get_item_name, armor_total_defense, fmt_int,
    _DAMAGE_TYPES,
)


def _fv(value, decimals: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


class VehicleDetailView(WikiDetailView):
    """Detail view for a single vehicle entity."""

    _acquisition_loaded = pyqtSignal(dict)
    _usage_loaded = pyqtSignal(dict)

    def __init__(self, item: dict, *, nexus_base_url: str = "",
                 data_client=None, parent=None):
        super().__init__(
            item, nexus_base_url=nexus_base_url,
            data_client=data_client, parent=parent,
        )
        self._acquisition_loaded.connect(self._on_acquisition_loaded)
        self._usage_loaded.connect(self._on_usage_loaded)
        self._build(item)

    def _build(self, item: dict):
        name = get_item_name(item)
        vehicle_type = deep_get(item, "Properties", "Type") or "-"

        # --- Image ---
        self._add_image_placeholder(name)
        item_id = item.get("Id")
        if item_id and self._nexus_base_url:
            self._load_image_async(
                f"{self._nexus_base_url}/api/img/vehicle/{item_id}"
            )

        # --- Badge + title ---
        subtitle_widgets = [self._make_badge(vehicle_type)]
        self._add_infobox_title(name, subtitle_widgets)

        # --- Tier1: Speed, Passengers, Max SI ---
        max_speed = deep_get(item, "Properties", "MaxSpeed")
        passengers = deep_get(item, "Properties", "PassengerCount")
        max_si = deep_get(item, "Properties", "MaxStructuralIntegrity")

        tier1 = InfoboxSection(tier1=True)
        tier1.add_row(Tier1StatRow(
            "Max Speed",
            f"{fmt_int(max_speed)} km/h" if max_speed is not None else "-",
        ))
        tier1.add_row(Tier1StatRow("Passengers", fmt_int(passengers)))
        tier1.add_row(Tier1StatRow("Max SI", fmt_int(max_si)))
        self._add_section(tier1)

        # --- General ---
        weight = deep_get(item, "Properties", "Weight")
        spawned_weight = deep_get(item, "Properties", "SpawnedWeight")

        general = InfoboxSection("General")
        general.add_row(StatRow("Type", vehicle_type))
        general.add_row(StatRow(
            "Weight", f"{fmt_int(weight)} kg" if weight is not None else "-"
        ))
        general.add_row(StatRow(
            "Spawned Weight",
            f"{fmt_int(spawned_weight)} kg" if spawned_weight is not None else "-",
        ))
        self._add_section(general)

        # --- Vehicle ---
        item_cap = deep_get(item, "Properties", "ItemCapacity")
        weight_cap = deep_get(item, "Properties", "WeightCapacity")
        wheel_grip = deep_get(item, "Properties", "WheelGrip")
        engine = deep_get(item, "Properties", "EnginePower")

        vehicle = InfoboxSection("Vehicle")
        vehicle.add_row(StatRow("Passengers", fmt_int(passengers)))
        if item_cap is not None:
            vehicle.add_row(StatRow("Item Capacity", fmt_int(item_cap)))
        if weight_cap is not None:
            vehicle.add_row(StatRow("Weight Capacity", f"{_fv(weight_cap, 1)} kg"))
        if wheel_grip is not None and vehicle_type in ("Land", "Amphibious"):
            vehicle.add_row(StatRow("Wheel Grip", _fv(wheel_grip, 1)))
        if engine is not None:
            vehicle.add_row(StatRow("Engine Power", fmt_int(engine)))
        vehicle.add_row(StatRow(
            "Max Speed",
            f"{fmt_int(max_speed)} km/h" if max_speed is not None else "-",
        ))
        vehicle.add_row(StatRow("Max SI", fmt_int(max_si)))

        # Attachment slots
        att_slots = item.get("AttachmentSlots") or []
        if att_slots:
            slot_names = ", ".join(s.get("Name", "?") for s in att_slots)
            vehicle.add_row(StatRow("Att. Slots", slot_names))
        self._add_section(vehicle)

        # --- Economy ---
        max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
        min_tt = deep_get(item, "Properties", "Economy", "MinTT")
        durability = deep_get(item, "Properties", "Economy", "Durability")
        decay = deep_get(item, "Properties", "Economy", "Decay")
        fuel_name = deep_get(item, "Fuel", "Name")
        fuel_active = deep_get(item, "Properties", "Economy", "FuelConsumptionActive")
        fuel_passive = deep_get(item, "Properties", "Economy", "FuelConsumptionPassive")

        econ = InfoboxSection("Economy")
        econ.add_row(StatRow(
            "Max TT", f"{_fv(max_tt, 2)} PED" if max_tt is not None else "-"
        ))
        econ.add_row(StatRow(
            "Min TT", f"{_fv(min_tt, 2)} PED" if min_tt is not None else "-"
        ))
        econ.add_row(StatRow("Durability", fmt_int(durability)))
        if decay is not None:
            econ.add_row(StatRow("Decay", f"{_fv(decay, 2)} PEC/km"))
        if fuel_name:
            econ.add_row(StatRow("Fuel", fuel_name))
        if fuel_active is not None:
            econ.add_row(StatRow("Active Use", f"{_fv(fuel_active, 4)} PED/km"))
        if fuel_passive is not None:
            econ.add_row(StatRow("Passive Use", f"{_fv(fuel_passive, 4)} PED/min"))
        self._add_section(econ)

        # --- Defense (if any) ---
        defense = deep_get(item, "Properties", "Defense")
        total_def = armor_total_defense(item)
        if defense and total_def and total_def > 0:
            def_section = InfoboxSection("Defense")
            def_section.add_widget(DefenseBreakdownWidget(defense))
            self._add_section(def_section)

        self._add_infobox_stretch()

        # --- Article area ---
        self._set_article_title(name)
        description = deep_get(item, "Properties", "Description") or ""
        self._set_description_html(description)

        # --- Acquisition panel ---
        self._acquisition_section = DataSection("Acquisition", expanded=True)
        self._acquisition_section.set_loading()
        self._add_article_section(self._acquisition_section)

        # --- Usage panel ---
        self._usage_section = DataSection("Usage", expanded=True)
        self._usage_section.set_loading()
        self._add_article_section(self._usage_section)

        if self._data_client and name:
            def fetch_data(item_name=name):
                acq_data = self._data_client.get_acquisition(item_name)
                self._acquisition_loaded.emit(acq_data)
                usage_data = self._data_client.get_usage(item_name)
                self._usage_loaded.emit(usage_data)

            threading.Thread(
                target=fetch_data, daemon=True, name="vehicle-data-fetch"
            ).start()

    def _on_acquisition_loaded(self, data: dict):
        if not hasattr(self, "_acquisition_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Vehicle")
        self._acquisition_section.set_content(build_acquisition_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))

    def _on_usage_loaded(self, data: dict):
        if not hasattr(self, "_usage_section"):
            return
        url = exchange_url(self._item, self._nexus_base_url, "Vehicle")
        self._usage_section.set_content(build_usage_content(
            data, exchange_link=url, on_navigate=self.entity_navigate.emit))
