"""Reusable confirmation dialog overlay — extends OverlayWidget with dark theme."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton, QScrollArea,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager

# --- Layout ---
DIALOG_WIDTH = 380

# --- Colors (matching scan_summary dark theme) ---
BG_COLOR = "rgba(20, 20, 30, 200)"
TITLE_BG = "rgba(30, 30, 45, 220)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
WARNING_COLOR = "#f59e0b"
WARNING_BG = "rgba(245, 158, 11, 20)"
ACCENT = "#00ccff"
FOOTER_BG = "rgba(25, 25, 40, 160)"
CANCEL_COLOR = "#ff6b6b"

# --- SVG icons ---
_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    "  background-color: rgba(60, 60, 80, 200);"
    "}"
)


class ConfirmOverlay(OverlayWidget):
    """Draggable confirmation dialog overlay with dark theme.

    Signals:
        confirmed: Emitted when the user clicks the confirm button.
        cancelled: Emitted when the user clicks cancel or closes.
    """

    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(
        self,
        *,
        config,
        config_path: str,
        manager: OverlayManager | None = None,
        title: str = "Confirm",
        message: str = "",
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="confirm_overlay_position",
            manager=manager,
        )
        self._click_origin: QPoint | None = None

        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        self._container.setFixedWidth(DIALOG_WIDTH)
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px; padding: 0px;"
        )

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._title_bar = self._build_title_bar(title)
        layout.addWidget(self._title_bar)

        # Body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 8)
        body_layout.setSpacing(8)

        # Message label
        self._message_label = QLabel(message)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 11px; background: transparent;"
        )
        body_layout.addWidget(self._message_label)

        # Detail area (scrollable, for listing items)
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setMaximumHeight(200)
        self._detail_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,40); border-radius: 3px;"
            "}"
        )
        self._detail_widget = QWidget()
        self._detail_widget.setStyleSheet("background: transparent;")
        self._detail_layout = QVBoxLayout(self._detail_widget)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(2)
        self._detail_scroll.setWidget(self._detail_widget)
        self._detail_scroll.setVisible(False)
        body_layout.addWidget(self._detail_scroll)

        # Footer note
        self._footer_note = QLabel("")
        self._footer_note.setWordWrap(True)
        self._footer_note.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        self._footer_note.setVisible(False)
        body_layout.addWidget(self._footer_note)

        layout.addWidget(body)

        # Footer buttons
        footer = QWidget()
        footer.setStyleSheet(
            f"background-color: {FOOTER_BG};"
            " border-bottom-left-radius: 8px;"
            " border-bottom-right-radius: 8px;"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 6)
        footer_layout.addStretch()

        self._cancel_btn = QPushButton(cancel_text)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(
            f"color: {CANCEL_COLOR}; font-size: 10px;"
            f" background: transparent; border: 1px solid {CANCEL_COLOR};"
            " border-radius: 3px; padding: 3px 12px;"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        footer_layout.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton(confirm_text)
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.setStyleSheet(
            f"color: {ACCENT}; font-size: 10px;"
            f" background: transparent; border: 1px solid {ACCENT};"
            " border-radius: 3px; padding: 3px 12px;"
        )
        self._confirm_btn.clicked.connect(self._on_confirm)
        footer_layout.addWidget(self._confirm_btn)

        layout.addWidget(footer)

        # Center on screen
        self._center_on_screen()

    def _build_title_bar(self, title: str) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {WARNING_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignVCenter)

        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(self._on_cancel)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    def _center_on_screen(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - DIALOG_WIDTH) // 2
            y = geo.y() + geo.height() // 3
            self.move(x, y)

    # --- Public API ---

    def set_message(self, text: str):
        self._message_label.setText(text)

    def set_footer_note(self, text: str):
        self._footer_note.setText(text)
        self._footer_note.setVisible(bool(text))

    def add_detail_line(self, text: str, *, color: str = TEXT_COLOR):
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent;"
        )
        self._detail_layout.addWidget(label)
        self._detail_scroll.setVisible(True)

    def set_shrinkage_warning(self, shrunk: dict[str, tuple[float, float]]):
        """Populate dialog for skill shrinkage confirmation.

        Args:
            shrunk: {skill_name: (old_value, new_value), ...}
        """
        self.set_message(
            "The following skills have fewer points than previously recorded:"
        )
        for name, (old_val, new_val) in shrunk.items():
            diff = new_val - old_val
            self.add_detail_line(
                f"  {name}: {old_val:.0f} \u2192 {new_val:.0f} ({diff:+.0f})",
                color=WARNING_COLOR,
            )
        self.set_footer_note(
            "This can happen when skills are sold in-game. Sync anyway?"
        )

    # --- Handlers ---

    def _on_confirm(self):
        self.confirmed.emit()
        self.set_wants_visible(False)
        self.close()

    def _on_cancel(self):
        self.cancelled.emit()
        self.set_wants_visible(False)
        self.close()
