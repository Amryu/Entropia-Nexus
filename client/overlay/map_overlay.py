"""Map overlay — always-on-top interactive map with search, info panel, and layer filters."""

from __future__ import annotations

import os
import re
import threading
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QComboBox, QLineEdit, QApplication,
)
from PyQt6.QtCore import Qt, QPoint, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import QPixmap

import requests

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon
from ..ui.widgets.map_canvas import MapCanvas
from ..ui.pages.maps_page import (
    PLANET_GROUPS, _LAYER_DEFS, _planet_slug,
    _fuzzy_score, _precompute_mob_area_data,
    _SearchResultsList, _LocationInfoPanel,
    _MAX_SEARCH_RESULTS,
)
from ..core.logger import get_logger

if TYPE_CHECKING:
    from ..api.data_client import DataClient
    from .overlay_manager import OverlayManager

log = get_logger("MapOverlay")

# --- Colors (same as detail overlay dark theme) ---
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TAB_BG = "rgba(25, 25, 40, 180)"
TAB_ACTIVE_BG = "rgba(60, 60, 90, 180)"
TAB_HOVER_BG = "rgba(50, 50, 70, 160)"
CONTENT_BG = "rgba(30, 30, 45, 160)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
TEXT_BRIGHT = "#ffffff"
ACCENT = "#00ccff"
FOOTER_BG = "rgba(25, 25, 40, 160)"
BADGE_BG = "rgba(50, 50, 70, 160)"

# --- SVG icons ---
_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

_MAP_SVG = (
    '<path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5'
    '.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5z'
    'M15 19l-6-2.11V5l6 2.11V19z"/>'
)

# Button style (matching detail overlay)
_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    f"  background-color: {TAB_HOVER_BG};"
    "}"
)

# --- Size presets: (width, height) ---
_SIZE_PRESETS = [
    (480, 360),   # Small
    (680, 480),   # Medium
    (920, 620),   # Large
]
_SIZE_LABELS = ["S", "M", "L"]
_SIZE_TOOLTIPS = ["Small (480\u00d7360)", "Medium (680\u00d7480)", "Large (920\u00d7620)"]

# Layout constants
_TITLE_H = 24
_FOOTER_H = 24
_SIDEBAR_W = 28
_LAYER_BTN_SIZE = 22

# Image cache dir (shared with maps page)
_IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "maps")

# Overlay panel styles
_PANEL_BG = "rgba(17, 17, 23, 224)"
_PANEL_BORDER = "#555555"
_PANEL_RADIUS = 6


class _InfoPanelWrapper(QWidget):
    """Top-level frameless wrapper around _LocationInfoPanel.

    Floats next to the map overlay. NOT registered with OverlayManager
    (MapOverlay manages its visibility directly) to avoid snap-jitter
    when dragging the map overlay.
    """

    def __init__(self, info_panel: _LocationInfoPanel, *, config):
        super().__init__()
        self._info_panel = info_panel

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(config.overlay_opacity)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        info_panel.setParent(self)
        layout.addWidget(info_panel)

    def set_wants_visible(self, visible: bool):
        if visible:
            self.show()
        else:
            self.hide()

    def wheelEvent(self, event):
        event.accept()


# Module-level callback set by app.py to open an entity in the detail overlay.
# Signature: (item: dict) -> None   where item = {"Name": ..., "Type": ...}
_open_entity_callback = None


class MapOverlay(OverlayWidget):
    """Always-on-top map overlay with search, info panel, and layer filters."""

    _planet_data_ready = pyqtSignal(str)  # slug only; payload in _planet_data_payload

    def __init__(
        self,
        *,
        config,
        config_path: str,
        data_client: DataClient,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="map_overlay_position",
            manager=manager,
        )
        self._data_client = data_client
        self._planets: list[dict] = []
        self._current_slug: str | None = None
        self._loading = False
        self._pending_location_id: int | None = None
        self._selected_location: dict | None = None
        self._click_origin = None

        os.makedirs(_IMAGE_CACHE_DIR, exist_ok=True)

        # Current size preset index
        self._size_idx = max(0, min(getattr(config, "map_overlay_size", 1), 2))

        # Override OverlayWidget container — no padding, no border-radius (children handle it)
        self._container.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self._container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Title bar ---
        self._title_bar = self._build_title_bar()
        main_layout.addWidget(self._title_bar)

        # --- Body (hidden when minified) ---
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        body_outer = QVBoxLayout(self._body)
        body_outer.setContentsMargins(0, 0, 0, 0)
        body_outer.setSpacing(0)

        # Content row: sidebar + map area
        content_row = QWidget()
        content_row.setStyleSheet("background: transparent;")
        cr_layout = QHBoxLayout(content_row)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(0)

        # Left sidebar — layer filters
        self._sidebar = self._build_sidebar()
        cr_layout.addWidget(self._sidebar)

        # Map area (canvas + floating panels)
        self._map_area = QWidget()
        self._map_area.setStyleSheet(f"background: {CONTENT_BG}; border: none;")
        self._map_area_layout = QVBoxLayout(self._map_area)
        self._map_area_layout.setContentsMargins(0, 0, 0, 0)
        self._map_area_layout.setSpacing(0)

        self._canvas = MapCanvas(self._map_area)
        self._map_area_layout.addWidget(self._canvas)

        cr_layout.addWidget(self._map_area, 1)
        body_outer.addWidget(content_row, 1)

        # Footer
        self._footer = self._build_footer()
        body_outer.addWidget(self._footer)

        main_layout.addWidget(self._body, 1)

        # --- Floating panels (children of _map_area, positioned in resizeEvent) ---
        # Top-left: planet selector + search
        self._top_panel = QWidget(self._map_area)
        self._top_panel.setStyleSheet(
            f"background: {_PANEL_BG}; border: 1px solid {_PANEL_BORDER};"
            f" border-radius: {_PANEL_RADIUS}px;"
        )
        top_layout = QVBoxLayout(self._top_panel)
        top_layout.setContentsMargins(6, 4, 6, 4)
        top_layout.setSpacing(4)

        self._planet_combo = QComboBox()
        self._planet_combo.setMinimumWidth(220)
        self._planet_combo.setStyleSheet(
            f"QComboBox {{ background: rgba(15,15,20,200); color: {TEXT_COLOR};"
            f" border: 1px solid {_PANEL_BORDER}; border-radius: 4px;"
            f" padding: 3px 6px; font-size: 11px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background: rgba(15,15,20,240); color: {TEXT_COLOR};"
            f" border: 1px solid {_PANEL_BORDER}; selection-background-color: {TAB_HOVER_BG}; }}"
        )
        top_layout.addWidget(self._planet_combo)

        # Search row
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(0)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search locations...")
        self._search_input.setStyleSheet(
            f"background: rgba(15,15,20,200); color: {TEXT_COLOR};"
            f" border: 1px solid {_PANEL_BORDER}; border-radius: 4px;"
            f" padding: 3px 6px; font-size: 11px;"
        )
        search_row.addWidget(self._search_input, 1)

        self._search_clear_btn = QPushButton("\u2715")
        self._search_clear_btn.setFixedWidth(24)
        self._search_clear_btn.setFixedHeight(self._search_input.sizeHint().height())
        self._search_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_clear_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(15,15,20,200); color: {TEXT_DIM};"
            f" border: 1px solid {_PANEL_BORDER}; border-left: none;"
            f" border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            f" border-top-left-radius: 0; border-bottom-left-radius: 0;"
            f" font-size: 11px; padding: 0px; }}"
            f"QPushButton:hover {{ color: {TEXT_COLOR}; background: {TAB_HOVER_BG}; }}"
        )
        self._search_clear_btn.clicked.connect(self._clear_search)
        self._search_clear_btn.hide()
        search_row.addWidget(self._search_clear_btn)

        top_layout.addLayout(search_row)
        self._top_panel.adjustSize()

        # Search results dropdown
        self._search_dropdown = _SearchResultsList(self._map_area)
        self._search_dropdown.result_clicked.connect(self._on_search_result_clicked)
        self._search_dropdown.result_hovered.connect(self._on_search_result_hovered)
        self._search_input.installEventFilter(self)

        # Info panel — external top-level widget (floats to the right)
        self._info_panel = _LocationInfoPanel(None)
        self._info_panel.close_clicked.connect(self._hide_info_panel)
        self._info_panel.teleporter_clicked.connect(self._on_teleporter_clicked)
        self._info_panel.teleporter_hovered.connect(self._on_teleporter_hovered)
        self._info_panel.mob_clicked.connect(self._on_mob_clicked)

        self._info_wrapper = _InfoPanelWrapper(
            self._info_panel, config=config,
        )
        self._info_showing = False

        if manager:
            manager.opacity_changed.connect(self._info_wrapper.setWindowOpacity)

        # Loading label
        self._loading_label = QLabel("Loading map...", self._map_area)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 14px; background: transparent;"
        )
        self._loading_label.hide()

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

        # Apply initial size
        self._apply_size()

        # Load planets in background
        threading.Thread(target=self._fetch_planets, daemon=True, name="mapoverlay-planets").start()

    # --- Title bar ---

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(_TITLE_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # Map icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(svg_icon(_MAP_SVG, ACCENT, 14).pixmap(14, 14))
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # Title label (updated dynamically with location name)
        self._title_label = QLabel("Map")
        self._title_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        self._title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._title_label, 1, Qt.AlignmentFlag.AlignVCenter)

        # Size buttons [S] [M] [L]
        self._size_buttons: list[QPushButton] = []
        for i, label in enumerate(_SIZE_LABELS):
            btn = QPushButton(label)
            btn.setFixedSize(18, 18)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(_SIZE_TOOLTIPS[i])
            btn.setStyleSheet(self._size_btn_style(i == self._size_idx))
            btn.clicked.connect(lambda _, idx=i: self._set_size(idx))
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._size_buttons.append(btn)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close (Ctrl+M)")
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(self.toggle_visibility)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    @staticmethod
    def _size_btn_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ color: {ACCENT}; font-size: 10px; font-weight: 700;"
                f" background: {TAB_ACTIVE_BG}; border: 1px solid {ACCENT};"
                " border-radius: 3px; padding: 0px; }}"
            )
        return (
            f"QPushButton {{ color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
            f" background: transparent; border: 1px solid transparent;"
            " border-radius: 3px; padding: 0px; }}"
            f"QPushButton:hover {{ color: {TEXT_COLOR}; background: {TAB_HOVER_BG}; }}"
        )

    # --- Sidebar (layer filters) ---

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(_SIDEBAR_W)
        sidebar.setStyleSheet(f"background: {TAB_BG};")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(3, 4, 3, 4)
        layout.setSpacing(3)

        self._layer_buttons: list[tuple[QPushButton, set[str]]] = []
        for label, color, types, default_on in _LAYER_DEFS:
            btn = QPushButton(label)
            btn.setFixedSize(_LAYER_BTN_SIZE, _LAYER_BTN_SIZE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(default_on)
            btn.setToolTip(label)
            btn.setStyleSheet(self._layer_btn_style(color, default_on))
            btn.toggled.connect(
                lambda checked, b=btn, c=color: self._on_layer_toggled(b, c, checked)
            )
            layout.addWidget(btn)
            self._layer_buttons.append((btn, types))

        layout.addStretch(1)
        return sidebar

    @staticmethod
    def _layer_btn_style(color: str, active: bool) -> str:
        border = ACCENT if active else "transparent"
        return (
            f"QPushButton {{ color: {color}; font-size: 8px; font-weight: 700;"
            f" background: rgba(0,0,0,128); border: 1px solid {border};"
            f" border-radius: 3px; padding: 0px; }}"
            f"QPushButton:hover {{ background: rgba(0,0,0,190); }}"
        )

    # --- Footer ---

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(_FOOTER_H)
        footer.setStyleSheet(
            f"background-color: {FOOTER_BG};"
            " border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
        )
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(_SIDEBAR_W + 4, 2, 4, 3)
        layout.setSpacing(4)

        open_btn = QPushButton("Open in Maps tab")
        open_btn.setIcon(svg_icon(_MAP_SVG, ACCENT, 12))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; background: transparent;"
            " border: none; padding: 2px 4px;"
        )
        open_btn.clicked.connect(self._open_in_maps_tab)
        layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self._planet_label = QLabel("")
        self._planet_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        layout.addWidget(self._planet_label, 0, Qt.AlignmentFlag.AlignVCenter)

        return footer

    # --- Size management ---

    def _set_size(self, idx: int):
        if idx == self._size_idx:
            return
        self._size_idx = idx
        self._config.map_overlay_size = idx
        from ..core.config import save_config
        save_config(self._config, self._config_path)

        for i, btn in enumerate(self._size_buttons):
            btn.setStyleSheet(self._size_btn_style(i == idx))

        self._apply_size()
        # Reposition info panel for new size
        if self._info_showing:
            self._position_info_wrapper()

    def _apply_size(self):
        w, h = _SIZE_PRESETS[self._size_idx]
        total_h = h + _TITLE_H + _FOOTER_H
        self.setFixedSize(w, total_h)

    # --- Floating panel positioning ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_panels()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_panels()
        self._top_panel.raise_()
        self._search_dropdown.raise_()
        # Re-show info wrapper when manager shows us (e.g. game regains focus)
        if self._info_showing:
            self._info_wrapper.set_wants_visible(True)
            QTimer.singleShot(0, self._position_info_wrapper)

    def hideEvent(self, event):
        super().hideEvent(event)
        # Hide info wrapper when manager hides us (e.g. game loses focus)
        self._info_wrapper.hide()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_info_wrapper()

    def _position_panels(self):
        """Position floating panels within the map area."""
        margin = 8

        # Top-left: planet + search
        self._top_panel.move(margin, margin)
        self._top_panel.adjustSize()

        # Search dropdown below top panel
        drop_x = margin
        drop_y = margin + self._top_panel.height() + 2
        self._search_dropdown.move(drop_x, drop_y)
        self._search_dropdown.setFixedWidth(self._top_panel.width())

        # Loading label centered
        self._loading_label.setGeometry(
            0, 0, self._map_area.width(), self._map_area.height(),
        )

        # External info panel wrapper
        self._position_info_wrapper()

    def _position_info_wrapper(self):
        """Position the external info panel relative to this overlay.

        On Small size: float to the right of the overlay window.
        On Medium/Large: overlap the right side of the map area (inside bounds).
        Width always matches the search/planet top panel.
        """
        if not self._info_wrapper.isVisible():
            return
        gap = 4
        margin = 8
        panel_w = self._top_panel.width()
        self._info_panel.setFixedWidth(panel_w)
        self._info_wrapper.setFixedWidth(panel_w)

        # Compute content height: clear constraints, activate layout, then measure
        # (same pattern as _LocationInfoPanel._fit_height on the maps page)
        self._info_panel.setMinimumHeight(0)
        self._info_panel.setMaximumHeight(16777215)
        self._info_panel._layout.activate()
        self._info_panel._content.adjustSize()
        content_h = self._info_panel._content.sizeHint().height() + 2  # +2 for border

        if self._size_idx == 0:
            # Small — external, to the right, top-aligned with the map window
            max_h = max(1, self.height())
            self._info_wrapper.setFixedHeight(min(content_h, max_h))
            self._info_wrapper.move(
                self.x() + self.width() + gap,
                self.y(),
            )
        else:
            # Medium/Large — overlap right side of map area, respect padding
            max_h = max(1, self._map_area.height() - margin * 2)
            self._info_wrapper.setFixedHeight(min(content_h, max_h))
            map_global = self._map_area.mapToGlobal(QPoint(0, 0))
            panel_x = map_global.x() + self._map_area.width() - panel_w - margin
            panel_y = map_global.y() + margin
            self._info_wrapper.move(panel_x, panel_y)
        self._info_wrapper.raise_()

    # --- Minify (click title bar to collapse/expand) ---

    def _toggle_minify(self):
        expanding = not self._body.isVisible()
        self._body.setVisible(expanding)
        if expanding:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )
            self._apply_size()
            # Re-show info panel if a location was selected
            if self._info_showing:
                self._info_wrapper.set_wants_visible(True)
                self._position_info_wrapper()
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
            self.setFixedSize(self.width(), _TITLE_H)
            # Hide info panel when minified
            self._info_wrapper.set_wants_visible(False)

    def _ensure_expanded(self):
        """Un-minify if currently minified."""
        if not self._body.isVisible():
            self._toggle_minify()

    # --- Visibility toggle ---

    def toggle_visibility(self):
        """Toggle overlay visibility (used by Ctrl+M and close button)."""
        if self.isVisible() and self.wants_visible:
            self.set_wants_visible(False)
            self._info_wrapper.set_wants_visible(False)
        else:
            self._ensure_expanded()
            self.set_wants_visible(True)
            self.raise_()
            if self._info_showing:
                self._info_wrapper.set_wants_visible(True)
                self._position_info_wrapper()

    def set_wants_visible(self, visible: bool):
        super().set_wants_visible(visible)
        if not visible:
            self._info_wrapper.set_wants_visible(False)
        elif self._info_showing:
            self._info_wrapper.set_wants_visible(True)
            QTimer.singleShot(0, self._position_info_wrapper)

    def open_at_location(self, planet_name: str, location_id: int):
        """Show the overlay and navigate to a specific location."""
        self._ensure_expanded()
        self.set_wants_visible(True)
        self.raise_()
        self.navigate_to_location(planet_name, location_id)

    # --- Data loading ---

    def _fetch_planets(self):
        try:
            self._planets = self._data_client.get_planets()
        except Exception as e:
            log.error("Failed to fetch planets: %s", e)
            self._planets = []
        QTimer.singleShot(0, self._populate_planet_combo)

    def _populate_planet_combo(self):
        self._planet_combo.blockSignals(True)
        self._planet_combo.clear()

        planet_by_slug: dict[str, dict] = {}
        for p in self._planets:
            planet_by_slug[_planet_slug(p["Name"])] = p

        for group_name, entries in PLANET_GROUPS:
            self._planet_combo.addItem(f"\u2500\u2500 {group_name} \u2500\u2500")
            idx = self._planet_combo.count() - 1
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
            daemon=True, name=f"mapoverlay-{slug}",
        ).start()

    def _fetch_planet_data(self, slug: str):
        """Background: fetch locations + areas + mobspawns + image for a planet."""
        planet = None
        for p in self._planets:
            if _planet_slug(p["Name"]) == slug:
                planet = p
                break
        if not planet:
            log.error("Planet not found for slug: %s", slug)
            return

        planet_name = planet["Name"]

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

        # Merge by ID (same logic as MapsPage)
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

        _precompute_mob_area_data(merged)

        pixmap = self._load_planet_image(slug)

        if pixmap and not pixmap.isNull():
            # Pre-compute image coords in background (avoids main-thread freeze)
            from ..ui.widgets.map_canvas import precompute_image_coords, _EU_PER_TILE
            pmap = planet.get("Properties", {}).get("Map", {})
            map_w = pmap.get("Width", 1)
            img_w = pixmap.width() if pixmap.width() > 0 else 1
            img_tile_size = img_w / map_w
            eu_ratio = _EU_PER_TILE / img_tile_size
            eu_tile_size = img_tile_size * eu_ratio
            precompute_image_coords(merged, pmap, eu_ratio, eu_tile_size)

            self._planet_data_payload = (planet, pixmap, merged)
            self._planet_data_ready.emit(slug)

    def _load_planet_image(self, slug: str) -> QPixmap | None:
        cache_path = os.path.join(_IMAGE_CACHE_DIR, f"{slug}.jpg")

        if os.path.exists(cache_path):
            pm = QPixmap(cache_path)
            if not pm.isNull():
                return pm

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

    def _on_planet_data_ready(self, slug: str):
        payload = getattr(self, "_planet_data_payload", None)
        self._planet_data_payload = None
        if slug != self._current_slug or payload is None:
            return
        planet, pixmap, locations = payload
        self._loading = False
        self._loading_label.hide()
        self._hide_info_panel()
        self._canvas.set_planet(planet, pixmap, locations)
        self._on_layers_changed()
        self._apply_search()
        self._position_panels()
        self._top_panel.raise_()
        self._search_dropdown.raise_()

        self._planet_label.setText(planet.get("Name", ""))

        if self._pending_location_id is not None:
            loc_id = self._pending_location_id
            self._pending_location_id = None
            loc = self._canvas._find_by_id(loc_id)
            if loc:
                self._canvas.set_selected(loc_id)
                self._canvas.center_on_smart(loc)
                self._show_info_panel(loc)

    def navigate_to_location(self, planet_name: str, location_id: int):
        """Navigate to a specific location on a planet."""
        slug = _planet_slug(planet_name)
        if slug == self._current_slug and not self._loading:
            loc = self._canvas._find_by_id(location_id)
            if loc:
                self._canvas.set_selected(location_id)
                self._canvas.center_on_smart(loc)
                self._show_info_panel(loc)
        else:
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
        if has_text:
            self._search_input.setStyleSheet(
                f"background: rgba(15,15,20,200); color: {TEXT_COLOR};"
                f" border: 1px solid {_PANEL_BORDER}; border-right: none;"
                " border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
                " border-top-right-radius: 0; border-bottom-right-radius: 0;"
                " padding: 3px 6px; font-size: 11px;"
            )
        else:
            self._search_input.setStyleSheet(
                f"background: rgba(15,15,20,200); color: {TEXT_COLOR};"
                f" border: 1px solid {_PANEL_BORDER}; border-radius: 4px;"
                " padding: 3px 6px; font-size: 11px;"
            )
        self._search_timer.start()

    def _clear_search(self):
        self._search_input.clear()
        self._search_input.setFocus()

    def _apply_search(self):
        query = self._search_input.text().strip()
        if not query:
            self._canvas.set_search_results(set())
            self._search_dropdown.set_results([])
            return

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

        ids = {loc["Id"] for loc in results}
        self._canvas.set_search_results(ids)
        self._search_dropdown.set_results(results)
        self._position_panels()

    def _on_search_result_clicked(self, loc: dict):
        self._canvas.set_selected(loc.get("Id"))
        self._canvas.center_on_smart(loc)
        self._show_info_panel(loc)
        self._search_input.setFocus()

    def _on_search_result_hovered(self, loc: object):
        if loc and isinstance(loc, dict):
            self._canvas.set_hovered(loc.get("Id"))
            self._canvas.pan_to(loc)
        else:
            self._canvas.set_hovered(None)

    def _on_canvas_location_hovered(self, loc: object):
        if not self._search_dropdown.isVisible():
            return
        if loc and isinstance(loc, dict):
            self._search_dropdown.highlight_by_id(loc.get("Id"))
        else:
            self._search_dropdown.clear_highlight()

    def _on_canvas_location_clicked(self, loc: object):
        if loc and isinstance(loc, dict):
            self._canvas.center_on_smart(loc)
            self._show_info_panel(loc)
        else:
            self._hide_info_panel()

    # --- Info panel (external) ---

    def _show_info_panel(self, loc: dict):
        self._selected_location = loc
        planet = None
        for p in self._planets:
            if _planet_slug(p["Name"]) == self._current_slug:
                planet = p
                break
        if not planet:
            return

        # Update title with location name
        display_name = loc.get("_mob_display_name") or loc.get("Name") or ""
        self._title_label.setText(f"Map - {display_name}" if display_name else "Map")

        # Set width before building content so layout computes at correct width
        panel_w = self._top_panel.width()
        self._info_panel.setFixedWidth(panel_w)
        self._info_wrapper.setFixedWidth(panel_w)

        self._info_panel.set_location(loc, planet, self._canvas._locations)
        # Tighten padding for overlay context (set_location rebuilds _content)
        self._info_panel._layout.setContentsMargins(10, 4, 10, 8)
        self._info_showing = True
        self._info_wrapper.set_wants_visible(True)
        self._info_wrapper.raise_()
        # Defer positioning so Qt processes the freshly-built layout first
        QTimer.singleShot(0, self._position_info_wrapper)

    def _hide_info_panel(self):
        self._selected_location = None
        self._info_showing = False
        self._info_wrapper.set_wants_visible(False)
        self._info_panel.hide()
        self._canvas.set_selected(None)
        self._title_label.setText("Map")

    def _on_teleporter_hovered(self, tp: object):
        if tp and isinstance(tp, dict):
            self._canvas.set_hovered(tp.get("Id"))
            self._canvas.pan_to(tp)
        else:
            self._canvas.set_hovered(None)
            if self._selected_location:
                self._canvas.pan_to(self._selected_location)

    def _on_teleporter_clicked(self, tp: object):
        if tp and isinstance(tp, dict):
            self._canvas.set_selected(tp.get("Id"))
            self._canvas.center_on_smart(tp)
            self._show_info_panel(tp)

    def _on_mob_clicked(self, mob_name: str):
        if _open_entity_callback is not None:
            _open_entity_callback({"Name": mob_name, "Type": "Mob"})
            return
        # Fallback: open in browser
        import webbrowser
        from urllib.parse import quote as url_quote
        base_url = getattr(self._config, "nexus_base_url", "https://entropianexus.com")
        slug = re.sub(r"[^0-9a-zA-Z]", "", mob_name).lower()
        webbrowser.open(f"{base_url}/information/mobs/{url_quote(slug)}")

    # --- Navigation to Maps tab ---

    def _open_in_maps_tab(self):
        app = QApplication.instance()
        if not app:
            return
        for w in app.topLevelWidgets():
            if hasattr(w, "_ensure_page"):
                from ..ui.main_window import PAGE_MAPS
                w._sidebar.set_active(PAGE_MAPS)
                maps_page = w._ensure_page(PAGE_MAPS)
                if self._selected_location and hasattr(maps_page, "navigate_to_location"):
                    planet = None
                    for p in self._planets:
                        if _planet_slug(p["Name"]) == self._current_slug:
                            planet = p
                            break
                    if planet:
                        maps_page.navigate_to_location(
                            planet["Name"], self._selected_location.get("Id"),
                        )
                break

    # --- Mouse events: drag from title bar / sidebar / footer + click-to-minify ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
            # Allow drag from title bar, sidebar, and footer — not the map canvas
            local_x = event.position().x()
            local_y = event.position().y()
            in_map_area = (
                local_y > _TITLE_H
                and local_x > _SIDEBAR_W
                and local_y < self.height() - _FOOTER_H
            )
            if not in_map_area:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            else:
                self._drag_pos = None

    def mouseReleaseEvent(self, event):
        click_origin = self._click_origin
        self._click_origin = None
        super().mouseReleaseEvent(event)

        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (
                event.globalPosition().toPoint() - click_origin
            ).manhattanLength()
            if delta < 5:
                # Click (not drag) — toggle minify if in title bar area
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height()),
                ).y()
                if click_local.y() <= title_bottom:
                    self._toggle_minify()

    def wheelEvent(self, event):
        """Let the canvas handle zoom, then keep info panel above the map."""
        super().wheelEvent(event)
        if self._info_showing and self._info_wrapper.isVisible():
            self._info_wrapper.raise_()

    # --- Cleanup ---

    def closeEvent(self, event):
        self._wants_visible = False
        self._info_wrapper.set_wants_visible(False)
        self._info_wrapper.close()
        super().closeEvent(event)
