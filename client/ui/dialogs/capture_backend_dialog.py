"""One-time dialog shown when WGC borderless capture is not supported.

Explains the trade-off between PrintWindow (no border, potential flickering)
and WGC (no game interference, yellow border) and lets the user choose.
"""

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
<p>Your version of Windows does not support borderless screen capture.
The client needs to choose how to capture the game window for OCR.</p>

<h4 style="color: {accent};">Option 1: PrintWindow</h4>
<ul>
  <li><b>No yellow border</b> around the game window.</li>
  <li>May have issues with certain hardware and refresh rates.</li>
  <li>May cause <b>occasional black flickering</b> in the game. If this
      happens, switch to WGC in settings.</li>
</ul>

<h4 style="color: {accent};">Option 2: Windows Graphics Capture</h4>
<ul>
  <li><b>No game interference</b> &mdash; does not touch the game's rendering pipeline.</li>
  <li>A <b>permanent yellow border</b> will be visible around the game window
      while the client is running. This is a Windows system limitation that
      cannot be removed on your OS version.</li>
  <li>This is supported in a newer version of Windows 10, so an update may resolve this.</li>
</ul>

<p style="color: {muted}; font-size: 12px; margin-top: 16px;">
  You can change this later in <b>Settings &rarr; Window capture backend</b>.
</p>
"""


class CaptureBackendDialog(QDialog):
    """One-time capture backend choice dialog.

    Returns ``QDialog.DialogCode.Accepted`` if the user chose WGC (yellow
    border), ``QDialog.DialogCode.Rejected`` if they chose PrintWindow.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screen Capture Method")
        self.setMinimumSize(480, 380)
        self.resize(520, 440)
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
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(_BODY_HTML.format(accent=ACCENT, muted=TEXT_MUTED))
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

        wgc_btn = QPushButton("Use WGC")
        wgc_btn.setStyleSheet(self._secondary_btn_style())
        wgc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wgc_btn.clicked.connect(self.accept)
        btn_row.addWidget(wgc_btn)

        btn_row.addStretch()

        pw_btn = QPushButton("Use PrintWindow")
        pw_btn.setStyleSheet(self._primary_btn_style())
        pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pw_btn.clicked.connect(self.reject)
        btn_row.addWidget(pw_btn)

        layout.addLayout(btn_row)

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
