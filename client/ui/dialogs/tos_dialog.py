"""Terms of Service / Disclaimer / Privacy Policy dialog for the desktop client."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTextBrowser,
)
from PyQt6.QtCore import Qt

from ..theme import PRIMARY, SECONDARY, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, BORDER, HOVER
from ..icons import svg_icon

# Bump this when the terms change - triggers re-acceptance.
TOS_VERSION = "1.1"

# Shield icon (24x24 viewBox)
_SHIELD_SVG = (
    '<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z'
    'm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>'
)

TOS_HTML = """\
<h2>Entropia Nexus Client - Terms of Use, Disclaimer &amp; Privacy</h2>
<p style="color: {muted};">Last updated: March 12, 2026</p>
<hr>

<h3>1. Nature of the Software</h3>
<p>
  Entropia Nexus Client ("the Software") is a community-built companion tool for the game
  Entropia Universe. It is <b>not affiliated with, endorsed by, or operated by MindArk PE AB</b>.
  The Software is provided as a convenience tool and carries no guarantee of fitness for any purpose.
</p>

<h3>2. Screen Capture &amp; OCR</h3>
<p>The Software captures screenshots of the <b>Entropia Universe game window only</b> using
  Windows Graphics Capture (WGC) or the <code>PrintWindow</code> API as a fallback.
  These screenshots are processed <b>entirely on your local machine</b> for optical character
  recognition (OCR) - for example, to read skill values or item data from the game interface.</p>
<ul>
  <li>Game-window screenshots and recordings are processed locally by default.</li>
  <li>No other windows or desktop content are intentionally captured.</li>
  <li>Captured media stays on your device unless you explicitly choose to upload or share it.</li>
  <li>OCR results stay local unless you enable features that sync data to your account.</li>
</ul>

<h3>3. Data Stored Locally</h3>
<p>The Software stores the following data on your computer:</p>
<ul>
  <li>Configuration and preferences (<code>config.json</code>)</li>
  <li>Local SQLite data (for example: parsed chat events, OCR scan results, and media metadata)</li>
  <li>Captured screenshots/clips saved to your configured output folders</li>
  <li>Cached reference data/assets (skill names, rank thresholds, item data, templates, changelog)</li>
  <li>Authentication tokens from Entropia Nexus OAuth</li>
</ul>
<p>This local data can include game-related identifiers (such as player names) visible in parsed logs or captured events.</p>

<h3>4. Data Sent to Servers</h3>
<p>The Software communicates with <code>api.entropianexus.com</code> for:</p>
<ul>
  <li>Fetching wiki, map, market, profile, and other reference data used by the client</li>
  <li>Syncing account data when logged in (for example: skills, loadouts, preferences, profile details)</li>
  <li>Crowdsourced ingestion (when enabled): global events, filtered trade chat messages, and market price OCR observations</li>
  <li>Optional user-initiated uploads/sharing: profile images, global screenshots, and submitted external video URLs</li>
  <li>Checking for software updates</li>
</ul>
<p>Ingestion payloads can include game-related identifiers/content such as player names, target names,
  locations, trade messages, item names, prices/markup values, timestamps, and confidence scores.</p>
<p>Authentication uses Entropia Nexus OAuth (PKCE). The client does <b>not</b> handle or store
  any passwords - authentication is managed entirely through the Nexus website.</p>
<p>We do not sell or share your data with third parties, except as required by law or to protect
  the integrity of the service.</p>

<h3>5. Overlays</h3>
<p>The Software draws transparent overlay windows on top of the game for displaying information
  such as item details, maps, and scan results.</p>
<ul>
  <li>Overlays are <b>purely visual</b> - they do not modify the game client, game memory,
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
<p>The Software is distributed under the Entropia Nexus Source-Available License.
  Any use, redistribution, or modification must comply with that license.</p>

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
  <li>Use or redistribute the Software in violation of the Entropia Nexus license terms</li>
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
            else "Terms of Use & Privacy - Please Review"
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
