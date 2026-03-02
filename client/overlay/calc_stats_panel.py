"""Floating stats panel for the calculator tab — displays offensive stats."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)
from PyQt6.QtCore import Qt

from .detail_overlay import (
    BG_COLOR, TITLE_BG, FOOTER_BG, TEXT_COLOR, TEXT_DIM,
    TEXT_BRIGHT, ACCENT, SECTION_COLOR,
)

STATS_PANEL_W = 200
_TITLE_H = 24


# ---------------------------------------------------------------------------
# Stat row helper
# ---------------------------------------------------------------------------

def _stat_row(label: str, parent_layout: QVBoxLayout) -> QLabel:
    row = QWidget()
    row_l = QHBoxLayout(row)
    row_l.setContentsMargins(8, 1, 14, 1)
    row_l.setSpacing(4)

    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
    row_l.addWidget(lbl, 1)

    val = QLabel("-")
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;")
    row_l.addWidget(val, 0)

    parent_layout.addWidget(row)
    return val


def _section_label(text: str, parent_layout: QVBoxLayout):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {SECTION_COLOR}; font-size: 12px; font-weight: bold;"
        f" padding: 4px 8px 1px 8px; background: transparent;"
    )
    parent_layout.addWidget(lbl)


# ---------------------------------------------------------------------------
# CalcStatsPanel
# ---------------------------------------------------------------------------

class CalcStatsPanel(QWidget):
    """Top-level floating widget showing calculated offensive stats.

    Mirrors the _InfoPanelWrapper pattern from map_overlay.py:
    frameless, stays-on-top, translucent, NOT registered with OverlayManager.
    The parent overlay manages its visibility directly.
    """

    def __init__(self, *, config):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(config.overlay_opacity)
        self.setFixedWidth(STATS_PANEL_W)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._container = QWidget()
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px;"
        )
        outer.addWidget(self._container)

        main_layout = QVBoxLayout(self._container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        title = QWidget()
        title.setFixedHeight(_TITLE_H)
        title.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        t_layout = QHBoxLayout(title)
        t_layout.setContentsMargins(8, 0, 8, 0)
        lbl = QLabel("Stats")
        lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        t_layout.addWidget(lbl)
        main_layout.addWidget(title)

        # Scrollable body
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 6px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(80, 80, 100, 160); border-radius: 3px;"
            "  min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}"
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 4, 0, 4)
        self._body_layout.setSpacing(0)

        # --- Offensive section ---
        _section_label("Offensive", self._body_layout)
        self._total_dmg = _stat_row("Total Damage", self._body_layout)
        self._eff_dmg = _stat_row("Effective Dmg", self._body_layout)
        self._dps = _stat_row("DPS", self._body_layout)
        self._dpp = _stat_row("DPP", self._body_layout)
        self._crit_chance = _stat_row("Crit Chance", self._body_layout)
        self._crit_dmg = _stat_row("Crit Damage", self._body_layout)
        self._range = _stat_row("Range", self._body_layout)
        self._reload = _stat_row("Reload", self._body_layout)

        # --- Economy section ---
        _section_label("Economy", self._body_layout)
        self._efficiency = _stat_row("Efficiency", self._body_layout)
        self._decay = _stat_row("Decay", self._body_layout)
        self._ammo = _stat_row("Ammo Burn", self._body_layout)
        self._cost = _stat_row("Cost / use", self._body_layout)
        self._total_uses = _stat_row("Total Uses", self._body_layout)

        # --- Effects section ---
        _section_label("Effects", self._body_layout)
        self._effects_container = QWidget()
        self._effects_container.setStyleSheet("background: transparent;")
        self._effects_layout = QVBoxLayout(self._effects_container)
        self._effects_layout.setContentsMargins(8, 0, 14, 4)
        self._effects_layout.setSpacing(1)
        self._no_effects_lbl = QLabel("None")
        self._no_effects_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        self._effects_layout.addWidget(self._no_effects_lbl)
        self._body_layout.addWidget(self._effects_container)

        self._body_layout.addStretch(1)

        self._scroll.setWidget(body)
        main_layout.addWidget(self._scroll, 1)

    # --- Public API ---

    def set_max_height(self, h: int):
        """Constrain the panel to at most *h* pixels tall, then resize to fit content."""
        self.setMaximumHeight(h)
        self.adjustSize()

    def update_stats(self, stats):
        """Refresh all labels from a LoadoutStats instance."""
        self._total_dmg.setText(f"{stats.total_damage:.2f} HP")
        self._eff_dmg.setText(f"{stats.effective_damage:.2f} HP")
        self._dps.setText(f"{stats.dps:.2f}")
        self._dpp.setText(f"{stats.dpp:.4f}")
        self._crit_chance.setText(f"{stats.crit_chance * 100:.1f}%")
        self._crit_dmg.setText(f"{stats.crit_damage:.2f}x")
        self._range.setText(f"{stats.range:.1f}m")
        self._reload.setText(f"{stats.reload:.2f}s")
        self._efficiency.setText(f"{stats.efficiency:.1f}%")
        self._decay.setText(f"{stats.decay:.4f} PEC")
        self._ammo.setText(f"{int(round(stats.ammo_burn))}")
        self._cost.setText(f"{stats.cost:.4f} PEC")
        self._total_uses.setText(f"{stats.lowest_total_uses}")

        self._update_effects(stats.active_effects)
        # Force layout recalc so adjustSize uses correct content height
        self._effects_container.adjustSize()
        self._scroll.widget().adjustSize()
        self.adjustSize()

    def _update_effects(self, effects: list):
        # Clear existing — hide first so they don't affect sizeHint
        while self._effects_layout.count() > 0:
            item = self._effects_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        if not effects:
            lbl = QLabel("None")
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            self._effects_layout.addWidget(lbl)
            return

        for effect in effects:
            name = effect.get("name", "?")
            total = effect.get("signedTotal", 0)
            prefix = effect.get("prefix") or {}
            etype = prefix.get("type", "")

            if etype == "mult":
                val_str = f"{total:+.1f}%"
            elif etype == "add":
                val_str = f"{total:+.2f}"
            else:
                val_str = f"{total:+.2f}"

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(0, 0, 0, 0)
            r_layout.setSpacing(4)

            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 11px; background: transparent;"
            )
            r_layout.addWidget(n_lbl, 1)

            v_lbl = QLabel(val_str)
            positive = total > 0
            color = "#4ade80" if positive else "#f87171"
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            v_lbl.setStyleSheet(
                f"color: {color}; font-size: 11px; background: transparent;"
            )
            r_layout.addWidget(v_lbl, 0)

            self._effects_layout.addWidget(row)

    def set_wants_visible(self, visible: bool):
        if visible:
            self.show()
        else:
            self.hide()

    def wheelEvent(self, event):
        event.accept()
