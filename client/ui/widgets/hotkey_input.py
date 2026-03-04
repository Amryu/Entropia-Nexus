"""Click-to-record hotkey input widget.

Click the button to start capturing, press a key combo to assign,
Esc to cancel. Modifier-only presses are ignored (waits for trigger key).
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence

from ..theme import ACCENT, BORDER, TEXT_MUTED

# Qt key codes for modifier keys (ignored as trigger keys)
_MODIFIER_KEYS = {
    Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
    Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
}


class HotkeyInput(QPushButton):
    """A button that captures keyboard combos on click.

    Stores combos as lowercase ``+``-separated strings matching the
    ``keyboard`` library format (e.g. ``"ctrl+f"``, ``"f3"``).
    """

    combo_changed = pyqtSignal(str)

    def __init__(self, combo: str = "", parent=None):
        super().__init__(parent)
        self._combo = combo
        self._capturing = False
        self.setFixedWidth(140)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._update_display()
        self.clicked.connect(self._start_capture)

    # --- Public API ---

    @property
    def combo(self) -> str:
        return self._combo

    @combo.setter
    def combo(self, value: str):
        self._combo = value
        self._update_display()

    def clear_combo(self):
        """Remove the current binding."""
        self._combo = ""
        self._update_display()
        self.combo_changed.emit("")

    # --- Capture lifecycle ---

    def _start_capture(self):
        self._capturing = True
        self.setText("Press a key\u2026")
        self.setStyleSheet(
            f"border: 1px solid {ACCENT}; color: {ACCENT}; padding: 4px 8px;"
        )
        self.grabKeyboard()

    def _finish_capture(self, new_combo: str):
        self._capturing = False
        self.releaseKeyboard()
        self._combo = new_combo
        self._update_display()
        self.combo_changed.emit(new_combo)

    def _cancel_capture(self):
        self._capturing = False
        self.releaseKeyboard()
        self._update_display()

    # --- Key handling ---

    def keyPressEvent(self, event):
        if not self._capturing:
            # Normal button behaviour (space/enter to click)
            super().keyPressEvent(event)
            return

        key = event.key()

        # Esc cancels capture
        if key == Qt.Key.Key_Escape:
            self._cancel_capture()
            return

        # Ignore modifier-only presses (wait for the trigger key)
        if key in _MODIFIER_KEYS:
            return

        # Build combo string
        modifiers = event.modifiers()
        parts: list[str] = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")

        # Convert Qt key to keyboard-library name (lowercase)
        key_name = QKeySequence(key).toString().lower()
        if key_name:
            parts.append(key_name)
            self._finish_capture("+".join(parts))

    def focusOutEvent(self, event):
        """Cancel capture if focus is lost (e.g. clicked elsewhere)."""
        if self._capturing:
            self._cancel_capture()
        super().focusOutEvent(event)

    # --- Display ---

    def _update_display(self):
        self.setStyleSheet(
            f"border: 1px solid {BORDER}; padding: 4px 8px;"
        )
        if self._combo:
            self.setText(self._format_combo(self._combo))
        else:
            self.setText("(not set)")
            self.setStyleSheet(
                f"border: 1px solid {BORDER}; color: {TEXT_MUTED}; padding: 4px 8px;"
            )

    @staticmethod
    def _format_combo(combo: str) -> str:
        """Format 'ctrl+f' as 'Ctrl+F' for display."""
        parts = combo.split("+")
        formatted = []
        for p in parts:
            if len(p) == 1:
                formatted.append(p.upper())
            elif p.startswith("f") and p[1:].isdigit():
                formatted.append(p.upper())  # F3, F7, etc.
            else:
                formatted.append(p.capitalize())
        return "+".join(formatted)
