"""One-time dialog to choose the window capture backend for OCR."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextBrowser,
)
from PyQt6.QtCore import Qt

from ..theme import PRIMARY, SECONDARY, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, BORDER, HOVER
from ..icons import svg_icon

# Monitor/screen icon (24x24 viewBox)
_MONITOR_SVG = (
    '<path d="M21 2H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h7l-2 3v1h8v-1l-2-3h7c1.1'
    ' 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 12H3V4h18v10z"/>'
)

_BODY_HTML = """\
<h3>Screen Capture Method</h3>
<p>Choose how the client captures the game window for OCR.</p>

<table style="border-collapse: collapse; width: 100%;">
  <tr>
    <td style="padding: 6px 8px; font-weight: bold; color: {accent};">WGC</td>
    <td style="padding: 6px 8px;">{wgc_desc}</td>
  </tr>
  <tr>
    <td style="padding: 6px 8px; font-weight: bold; color: {accent};">BitBlt</td>
    <td style="padding: 6px 8px;">Direct read from game buffer, may not work on some systems.</td>
  </tr>
  <tr>
    <td style="padding: 6px 8px; font-weight: bold; color: {accent};">PrintWindow</td>
    <td style="padding: 6px 8px;">Forces a game redraw, can cause flickering. Use as a last resort.</td>
  </tr>
</table>

<p style="color: {muted}; font-size: 12px; margin-top: 16px;">
  You can change this later in <b>Settings &rarr; Window capture backend</b>.
</p>
"""


class CaptureBackendDialog(QDialog):
    """One-time capture backend choice dialog.

    After ``exec()``, read :attr:`chosen_backend` for the selected value
    (``"bitblt"``, ``"printwindow"``, or ``"wgc"``).  Defaults to
    ``"wgc"`` (borderless) or ``"bitblt"`` (bordered) if closed without choosing.
    """

    def __init__(self, borderless_supported: bool = False, parent=None):
        super().__init__(parent)
        self.chosen_backend = "wgc" if borderless_supported else "bitblt"
        self.setWindowTitle("Screen Capture Method")
        self.setMinimumSize(420, 380)
        self.resize(480, 430)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {SECONDARY}; }}
            QLabel {{ background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(svg_icon(_MONITOR_SVG, ACCENT, 32).pixmap(32, 32))
        icon_label.setFixedSize(32, 32)
        header_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Screen Capture Method")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: bold;")
        header_text.addWidget(title)
        subtitle = QLabel("Choose how the game window is captured")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)
        layout.addLayout(header_row)

        # Separator
        layout.addWidget(self._separator())

        # Body
        if borderless_supported:
            wgc_desc = "Mandatory for HDR users, no yellow border on your system."
        else:
            wgc_desc = "Mandatory for HDR users, causes a yellow border on your system."

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(_BODY_HTML.format(
            accent=ACCENT, muted=TEXT_MUTED, wgc_desc=wgc_desc,
        ))
        browser.setStyleSheet(f"""
            QTextBrowser {{
                background: {PRIMARY};
                color: {TEXT};
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.6;
            }}
            QScrollBar:vertical {{
                background: {PRIMARY}; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        layout.addWidget(browser, 1)

        # Buttons
        layout.addWidget(self._separator())
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        pw_btn = QPushButton("PrintWindow")
        pw_btn.setStyleSheet(self._secondary_btn_style())
        pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pw_btn.clicked.connect(lambda: self._choose("printwindow"))
        btn_row.addWidget(pw_btn)

        btn_row.addStretch()

        bitblt_btn = QPushButton("BitBlt")
        if borderless_supported:
            bitblt_btn.setStyleSheet(self._secondary_btn_style())
        else:
            bitblt_btn.setStyleSheet(self._primary_btn_style())
        bitblt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bitblt_btn.clicked.connect(lambda: self._choose("bitblt"))
        btn_row.addWidget(bitblt_btn)

        wgc_btn = QPushButton("WGC")
        if borderless_supported:
            wgc_btn.setStyleSheet(self._primary_btn_style())
        else:
            wgc_btn.setStyleSheet(self._secondary_btn_style())
        wgc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wgc_btn.clicked.connect(lambda: self._choose("wgc"))
        btn_row.addWidget(wgc_btn)

        layout.addLayout(btn_row)

    def _choose(self, backend: str) -> None:
        self.chosen_backend = backend
        self.accept()

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {BORDER}; max-height: 1px;")
        return sep

    @staticmethod
    def _primary_btn_style() -> str:
        return f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {TEXT};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """

    @staticmethod
    def _secondary_btn_style() -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """
