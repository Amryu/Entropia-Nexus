"""Terms of Service / Disclaimer / Privacy Policy dialog for the desktop client."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QTextBrowser,
)
from PyQt6.QtCore import Qt

from ..theme import PRIMARY, SECONDARY, TEXT, TEXT_MUTED, ACCENT, BORDER, HOVER
from ..icons import svg_icon

# Bump this when the terms change — triggers re-acceptance.
TOS_VERSION = "1.0"

# Shield icon (24×24 viewBox)
_SHIELD_SVG = (
    '<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z'
    'm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>'
)

TOS_HTML = """\
<h2>Entropia Nexus Client — Terms of Use, Disclaimer &amp; Privacy</h2>
<p style="color: {muted};">Last updated: March 2, 2026</p>
<hr>

<h3>1. Nature of the Software</h3>
<p>
  Entropia Nexus Client ("the Software") is a community-built companion tool for the game
  Entropia Universe. It is <b>not affiliated with, endorsed by, or operated by MindArk PE AB</b>.
  The Software is provided as a convenience tool and carries no guarantee of fitness for any purpose.
</p>

<h3>2. Screen Capture &amp; OCR</h3>
<p>The Software captures screenshots of the <b>Entropia Universe game window only</b> using the
  Windows <code>PrintWindow</code> API. These screenshots are processed <b>entirely on your local
  machine</b> for optical character recognition (OCR) — for example, to read skill values or
  item data from the game interface.</p>
<ul>
  <li>Screenshots are <b>never transmitted</b> to any server.</li>
  <li>No other windows or desktop content are captured.</li>
  <li>OCR results stay on your machine unless you use features that explicitly sync data to your
      account (such as saving custom markup values).</li>
</ul>

<h3>3. Data Stored Locally</h3>
<p>The Software stores the following data on your computer:</p>
<ul>
  <li>Configuration and preferences (<code>config.json</code>)</li>
  <li>Cached reference data (skill names, rank thresholds, item data, font calibration)</li>
  <li>Authentication tokens from Entropia Nexus OAuth</li>
</ul>
<p>No personal data beyond your Entropia Nexus account information is stored locally.</p>

<h3>4. Data Sent to Servers</h3>
<p>The Software communicates with <code>api.entropianexus.com</code> for:</p>
<ul>
  <li>Fetching wiki data, skill references, exchange data, and map information</li>
  <li>Storing and retrieving user preferences (e.g. custom markup values) when logged in</li>
  <li>Checking for software updates</li>
</ul>
<p>Authentication uses Entropia Nexus OAuth (PKCE). The client does <b>not</b> handle or store
  any passwords — authentication is managed entirely through the Nexus website.</p>
<p>We do not sell or share your data with third parties, except as required by law or to protect
  the integrity of the service.</p>

<h3>5. Overlays</h3>
<p>The Software draws transparent overlay windows on top of the game for displaying information
  such as item details, maps, and scan results.</p>
<ul>
  <li>Overlays are <b>purely visual</b> — they do not modify the game client, game memory,
      network traffic, or game files in any way.</li>
  <li>Use of overlays is at your own discretion. Please consult MindArk's End User License
      Agreement (EULA) regarding third-party tools.</li>
</ul>

<h3>6. Auto-Updates</h3>
<p>The Software periodically checks for updates from the Entropia Nexus server. Updates are
  downloaded and applied only with your confirmation. Automatic update checks can be disabled
  in Settings.</p>

<h3>7. Intellectual Property</h3>
<p>Entropia Universe and all related content, trademarks, and intellectual property are owned by
  <b>MindArk PE AB</b>. This Software is a fan-made tool operated under principles of fair use
  for informational and community purposes. We do not claim ownership of any MindArk intellectual
  property.</p>
<p>The Software itself is proprietary. You may not reverse-engineer, redistribute, or modify it
  without explicit permission.</p>

<h3>8. Disclaimer of Liability</h3>
<p>THE SOFTWARE IS PROVIDED <b>"AS IS"</b> AND <b>"AS AVAILABLE"</b>, WITHOUT WARRANTY OF ANY KIND,
  EXPRESS OR IMPLIED.</p>
<p>To the maximum extent permitted by applicable law, the authors and contributors shall not be
  liable for any damages arising from the use of the Software, including but not limited to:</p>
<ul>
  <li>Game account restrictions or bans</li>
  <li>Loss of in-game items, currency (PED), or data</li>
  <li>Incorrect OCR readings or calculated values</li>
  <li>Financial decisions based on data provided by the Software</li>
  <li>Data loss or corruption on your system</li>
</ul>
<p>Community-contributed data (item stats, market values, wiki content) may be incomplete,
  outdated, or incorrect. Use at your own risk.</p>

<h3>9. Acceptable Use</h3>
<p>You agree not to:</p>
<ul>
  <li>Use the Software to exploit, cheat, or violate MindArk's EULA</li>
  <li>Reverse-engineer, decompile, or disassemble the Software</li>
  <li>Redistribute or share the Software without permission</li>
  <li>Use the Software for any illegal purpose</li>
</ul>

<h3>10. Changes to These Terms</h3>
<p>These terms may be updated at any time. When terms change, you will be prompted to review and
  accept the new version before continuing to use the Software.</p>

<h3>11. Contact</h3>
<p>If you have questions or concerns, contact us through the
  <a href="https://discord.gg/hBGKyJ6EDr" style="color: {accent};">Entropia Nexus Discord server</a>.
</p>
<p>For the full website Terms of Service and Privacy Policy, visit:<br>
  <a href="https://entropianexus.com/legal/terms" style="color: {accent};">entropianexus.com/legal/terms</a><br>
  <a href="https://entropianexus.com/legal/privacy" style="color: {accent};">entropianexus.com/legal/privacy</a>
</p>
""".format(muted=TEXT_MUTED, accent=ACCENT)


class TosDialog(QDialog):
    """Terms of Service acceptance / viewing dialog.

    In acceptance mode (default): shows Accept + Decline buttons.
    In read-only mode: shows only a Close button.
    """

    def __init__(self, *, read_only: bool = False, parent=None):
        super().__init__(parent)
        self._read_only = read_only
        self.setWindowTitle(
            "Terms of Use & Privacy" if read_only
            else "Terms of Use & Privacy — Please Review"
        )
        self.setMinimumSize(540, 420)
        self.resize(580, 540)
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
        icon_label.setPixmap(svg_icon(_SHIELD_SVG, ACCENT, 32).pixmap(32, 32))
        icon_label.setFixedSize(32, 32)
        header_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Terms of Use, Disclaimer & Privacy")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: bold;")
        header_text.addWidget(title)
        subtitle = QLabel(f"Version {TOS_VERSION}")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)
        layout.addLayout(header_row)

        # Separator
        layout.addWidget(self._separator())

        if not read_only:
            hint = QLabel(
                "Please read the following terms carefully before using the software."
            )
            hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        # Scrollable terms text
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(TOS_HTML)
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

        if read_only:
            btn_row.addStretch()
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(self._primary_btn_style())
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)
        else:
            decline_btn = QPushButton("Decline")
            decline_btn.setStyleSheet(self._secondary_btn_style())
            decline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            decline_btn.clicked.connect(self.reject)
            btn_row.addWidget(decline_btn)

            btn_row.addStretch()

            accept_btn = QPushButton("I Accept")
            accept_btn.setStyleSheet(self._primary_btn_style())
            accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            accept_btn.clicked.connect(self.accept)
            btn_row.addWidget(accept_btn)

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
                background-color: #4a9ae8;
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
