"""Label widget — customizable text label, static or event-driven."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox,
    QPushButton, QCheckBox, QComboBox, QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..grid_widget import GridWidget, WidgetContext
from ._common import C_TEXT, C_DIM

_ALIGN_MAP = {
    "Left":   Qt.AlignmentFlag.AlignLeft,
    "Center": Qt.AlignmentFlag.AlignHCenter,
    "Right":  Qt.AlignmentFlag.AlignRight,
}

_DIALOG_STYLE = """
    QDialog       { background: #1a1a2e; }
    QGroupBox     { color: #00ccff; border: 1px solid #333355; border-radius: 4px;
                    margin-top: 8px; padding-top: 6px; font-size: 11px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; top: 2px; }
    QLabel        { color: #cccccc; font-size: 11px; }
    QLineEdit, QSpinBox, QComboBox {
                    background: #252535; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px;
                    padding: 3px 6px; font-size: 11px; }
    QCheckBox     { color: #cccccc; font-size: 11px; }
    QCheckBox::indicator { width: 14px; height: 14px; }
    QPushButton   { background: #333350; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px;
                    padding: 4px 14px; font-size: 11px; }
    QPushButton:hover   { background: #404060; }
    QPushButton:pressed { background: #252540; }
"""


class _LabelConfigDialog(QDialog):
    """Configuration dialog for LabelWidget."""

    def __init__(
        self,
        cfg: dict,
        *,
        parent=None,
        event_bus=None,
        current_colspan: int = 3,
        current_rowspan: int = 2,
        max_cols: int = 50,
        max_rows: int = 50,
        widget_max_cols: int = 0,
        widget_max_rows: int = 0,
    ):
        super().__init__(parent)
        self._event_bus = event_bus
        self.setWindowTitle("Configure Label")
        self.setMinimumWidth(380)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        effective_max_cols = min(max_cols, widget_max_cols) if widget_max_cols > 0 else max_cols
        effective_max_rows = min(max_rows, widget_max_rows) if widget_max_rows > 0 else max_rows

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Text ────────────────────────────────────────────────────────────
        text_group = QGroupBox("Text")
        text_form  = QFormLayout(text_group)
        text_form.setSpacing(6)

        self._text_edit = QLineEdit(cfg.get("text", "Label"))
        text_form.addRow("Text:", self._text_edit)
        root.addWidget(text_group)

        # ── Appearance ──────────────────────────────────────────────────────
        app_group = QGroupBox("Appearance")
        app_form  = QFormLayout(app_group)
        app_form.setSpacing(6)

        # Font size (0 = auto-scale with tile size)
        self._font_spin = QSpinBox()
        self._font_spin.setRange(0, 72)
        self._font_spin.setSpecialValueText("Auto")
        self._font_spin.setValue(cfg.get("font_size", 0))
        app_form.addRow("Font size (0 = auto):", self._font_spin)

        # Color
        color_row = QHBoxLayout()
        self._color_edit = QLineEdit(cfg.get("color", "#e0e0e0"))
        self._color_edit.setFixedWidth(90)
        self._color_btn  = QPushButton()
        self._color_btn.setFixedSize(26, 26)
        self._color_btn.setStyleSheet(
            f"background: {cfg.get('color', '#e0e0e0')}; border: 1px solid #666;"
        )
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.setToolTip("Pick colour")
        self._color_btn.clicked.connect(self._pick_color)
        self._color_edit.textChanged.connect(self._sync_color_btn)
        color_row.addWidget(self._color_edit)
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        app_form.addRow("Color:", color_row)

        # Alignment
        self._align_combo = QComboBox()
        self._align_combo.addItems(list(_ALIGN_MAP.keys()))
        self._align_combo.setCurrentText(cfg.get("alignment", "Center"))
        app_form.addRow("Alignment:", self._align_combo)

        # Checkboxes row
        checks_row = QHBoxLayout()
        self._bold_check  = QCheckBox("Bold")
        self._bold_check.setChecked(cfg.get("bold", False))
        self._italic_check = QCheckBox("Italic")
        self._italic_check.setChecked(cfg.get("italic", False))
        self._wrap_check  = QCheckBox("Word wrap")
        self._wrap_check.setChecked(cfg.get("word_wrap", False))
        checks_row.addWidget(self._bold_check)
        checks_row.addWidget(self._italic_check)
        checks_row.addWidget(self._wrap_check)
        checks_row.addStretch()
        app_form.addRow("Style:", checks_row)

        root.addWidget(app_group)

        # ── Dynamic data ────────────────────────────────────────────────────
        dyn_group = QGroupBox("Dynamic data (optional)")
        dyn_form  = QFormLayout(dyn_group)
        dyn_form.setSpacing(6)

        self._event_edit = QLineEdit(cfg.get("event", ""))
        self._event_edit.setPlaceholderText("e.g. skill_gain  (leave blank for static)")

        ev_row = QHBoxLayout()
        ev_row.addWidget(self._event_edit)
        if event_bus is not None:
            ev_browse_btn = QPushButton("Browse…")
            ev_browse_btn.setFixedWidth(70)
            ev_browse_btn.clicked.connect(self._browse_event)
            ev_row.addWidget(ev_browse_btn)
        dyn_form.addRow("EventBus event:", ev_row)

        self._field_edit = QLineEdit(cfg.get("event_field", ""))
        self._field_edit.setPlaceholderText("dict key or object attr — blank = str(data)")
        dyn_form.addRow("Data field:", self._field_edit)

        root.addWidget(dyn_group)

        # ── Size ────────────────────────────────────────────────────────────
        size_group = QGroupBox("Size (tiles)")
        size_form  = QFormLayout(size_group)
        size_form.setSpacing(6)

        self._cs_spin = QSpinBox()
        self._cs_spin.setRange(1, effective_max_cols)
        self._cs_spin.setValue(current_colspan)
        size_form.addRow("Width (colspan):", self._cs_spin)

        self._rs_spin = QSpinBox()
        self._rs_spin.setRange(1, effective_max_rows)
        self._rs_spin.setValue(current_rowspan)
        size_form.addRow("Height (rowspan):", self._rs_spin)

        root.addWidget(size_group)

        # ── Buttons ─────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        # Style OK button accent
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setStyleSheet(
                "QPushButton { background: #305090; border-color: #4070b0; }"
                "QPushButton:hover { background: #3a60a8; }"
            )
        root.addWidget(btns)

    def _pick_color(self) -> None:
        from PyQt6.QtWidgets import QColorDialog
        current = QColor(self._color_edit.text())
        if not current.isValid():
            current = QColor("#e0e0e0")
        color = QColorDialog.getColor(current, self, "Choose colour")
        if color.isValid():
            self._color_edit.setText(color.name())

    def _browse_event(self) -> None:
        from ..event_explorer_dialog import EventExplorerDialog
        dlg = EventExplorerDialog(
            event_bus=self._event_bus,
            initial_event=self._event_edit.text().strip(),
            initial_field=self._field_edit.text().strip(),
            parent=self,
        )
        if dlg.exec():
            if dlg.selected_event:
                self._event_edit.setText(dlg.selected_event)
            if dlg.selected_field:
                self._field_edit.setText(dlg.selected_field)

    def _sync_color_btn(self, text: str) -> None:
        c = QColor(text)
        if c.isValid():
            self._color_btn.setStyleSheet(
                f"background: {c.name()}; border: 1px solid #666;"
            )

    def get_result(self) -> dict:
        return {
            "text":        self._text_edit.text(),
            "font_size":   self._font_spin.value(),
            "color":       self._color_edit.text() or "#e0e0e0",
            "alignment":   self._align_combo.currentText(),
            "bold":        self._bold_check.isChecked(),
            "italic":      self._italic_check.isChecked(),
            "word_wrap":   self._wrap_check.isChecked(),
            "event":       self._event_edit.text().strip(),
            "event_field": self._field_edit.text().strip(),
            "__slot__": {
                "colspan": self._cs_spin.value(),
                "rowspan": self._rs_spin.value(),
            },
        }


class LabelWidget(GridWidget):
    """Customizable text label — static or event-driven.

    Config keys
    -----------
    text        str   Static text to display.
    font_size   int   Font size in px; 0 = auto-scale with tile size.
    color       str   CSS colour string.
    alignment   str   "Left" | "Center" | "Right"
    bold        bool  Bold text.
    italic      bool  Italic text.
    word_wrap   bool  Enable word wrapping.
    event       str   Optional EventBus event to listen to.
    event_field str   Field name to extract from event data dict/object.
    """

    WIDGET_ID    = "com.entropianexus.label"
    DISPLAY_NAME = "Label"
    DESCRIPTION  = "Customizable text label — static or event-driven via any EventBus event."
    DEFAULT_COLSPAN = 3
    DEFAULT_ROWSPAN = 2
    MIN_COLSPAN  = 1
    MIN_ROWSPAN  = 1

    def __init__(self, config: dict):
        super().__init__(config)
        self._label:  QLabel | None = None
        self._subscribed_event: str = ""

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        event = self._widget_config.get("event", "")
        if event:
            self._subscribe(event, self._on_event)
            self._subscribed_event = event

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(self._widget_config.get("text", "Label"))
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._label)

        self._apply_style()
        return w

    # ── Styling ─────────────────────────────────────────────────────────────

    def _apply_style(self, cell_height: int = 0) -> None:
        if self._label is None:
            return
        cfg    = self._widget_config
        color  = cfg.get("color", C_TEXT)
        size   = cfg.get("font_size") or 0
        if size == 0:
            from ._common import font_big
            size = font_big(cell_height) if cell_height > 0 else 14
        bold   = "bold"   if cfg.get("bold",   False) else "normal"
        italic = "italic" if cfg.get("italic", False) else "normal"
        align  = _ALIGN_MAP.get(cfg.get("alignment", "Center"), Qt.AlignmentFlag.AlignHCenter)

        self._label.setStyleSheet(
            f"color: {color}; font-size: {size}px;"
            f" font-weight: {bold}; font-style: {italic};"
        )
        self._label.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self._label.setWordWrap(cfg.get("word_wrap", False))

    # ── Event handling ───────────────────────────────────────────────────────

    def _on_event(self, data) -> None:
        if self._label is None:
            return
        field = self._widget_config.get("event_field", "")
        if field:
            text = str(data.get(field, "—")) if isinstance(data, dict) else str(getattr(data, field, "—"))
        elif data is not None:
            text = str(data)
        else:
            text = "—"
        self._label.setText(text)

    # ── Configuration ────────────────────────────────────────────────────────

    def configure(self, parent: QWidget, **kwargs) -> dict | None:
        dlg = _LabelConfigDialog(
            self._widget_config,
            parent=parent,
            event_bus=self._context.event_bus if self._context else None,
            current_colspan=kwargs.get("current_colspan", self.DEFAULT_COLSPAN),
            current_rowspan=kwargs.get("current_rowspan", self.DEFAULT_ROWSPAN),
            max_cols=kwargs.get("max_cols", 50),
            max_rows=kwargs.get("max_rows", 50),
            widget_max_cols=self.MAX_COLSPAN,
            widget_max_rows=self.MAX_ROWSPAN,
        )
        return dlg.get_result() if dlg.exec() else None

    def on_config_changed(self, config: dict) -> None:
        new_event = config.get("event", "")
        old_event = self._subscribed_event

        super().on_config_changed(config)  # merges into _widget_config

        # Re-wire EventBus subscription if event changed
        if new_event != old_event:
            if old_event:
                self._unsubscribe(old_event, self._on_event)
            if new_event:
                self._subscribe(new_event, self._on_event)
            self._subscribed_event = new_event

        # Refresh visual
        if self._label:
            self._label.setText(self._widget_config.get("text", "Label"))
        self._apply_style()

    def on_resize(self, width: int, height: int) -> None:
        self._apply_style(cell_height=height)

    def get_config(self) -> dict:
        return dict(self._widget_config)
