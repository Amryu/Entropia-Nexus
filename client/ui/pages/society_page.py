"""Society page — view and manage an Entropia Nexus society."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextBrowser, QTextEdit, QLineEdit,
    QCheckBox, QDialog, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, BORDER, BORDER_HOVER,
    TEXT, TEXT_MUTED, ACCENT, ACCENT_LIGHT, SUCCESS, SUCCESS_BG,
    ERROR, ERROR_BG, WARNING, FONT_FAMILY, PAGE_HEADER_OBJECT_NAME,
)
from ..icons import svg_icon, svg_pixmap
from ...core.logger import get_logger

if TYPE_CHECKING:
    from ..signals import AppSignals
    from ...api.nexus_client import NexusClient

log = get_logger("SocietyPage")

# --- SVG icon paths (24x24 viewBox) ---

CROWN_SVG = '<path d="M5 16h14v2H5zm14-5.5l-3.5 2-3.5-4-3.5 4L5 10.5 6.5 18h11z"/>'

# Discord icon (simple gamepad-like shape)
_DISCORD_SVG = (
    '<path d="M20.317 4.37a19.8 19.8 0 0 0-4.885-1.515.074.074 0 0 0-.079.037'
    'c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0'
    ' 0-.617-1.25.077.077 0 0 0-.079-.037A19.74 19.74 0 0 0 3.677 4.37a.07.07'
    ' 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057'
    ' 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295'
    ' 1.227-1.994a.076.076 0 0 0-.041-.106 13.11 13.11 0 0 1-1.872-.892.077.077'
    ' 0 0 1-.008-.128c.126-.094.252-.192.372-.292a.074.074 0 0 1 .078-.01c3.928'
    ' 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.009c.12.1.246.199.373.293'
    'a.077.077 0 0 1-.006.127 12.3 12.3 0 0 1-1.873.892.077.077 0 0 0-.041.107'
    'c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.029 19.84 19.84 0 0 0'
    ' 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.06.06'
    ' 0 0 0-.031-.03z"/>'
)

# Crown color
CROWN_COLOR = "#fbbf24"

# --- Styles ---

_CARD_STYLE = (
    f"background: {SECONDARY}; border: 1px solid {BORDER};"
    f" border-radius: 6px; padding: 12px;"
)

_SECTION_LABEL_STYLE = (
    f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
    f" text-transform: uppercase; letter-spacing: 0.5px;"
    f" background: transparent; padding: 0; margin-bottom: 4px;"
)

_LINK_BTN_STYLE = (
    f"QPushButton {{ color: {ACCENT}; border: none; background: transparent;"
    f" text-align: left; padding: 0; font-size: 13px; }}"
    f"QPushButton:hover {{ color: {TEXT}; text-decoration: underline; }}"
)

_INPUT_STYLE = (
    f"color: {TEXT}; background: {PRIMARY}; border: 1px solid {BORDER};"
    f" border-radius: 4px; padding: 6px 8px;"
)

_BTN_STYLE = (
    f"QPushButton {{ background: {SECONDARY}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 12px; }}"
    f"QPushButton:hover {{ background: {HOVER}; border-color: {BORDER_HOVER}; }}"
)

_ACCENT_BTN_STYLE = (
    f"QPushButton {{ background: {ACCENT}; color: white; border: none;"
    f" border-radius: 4px; padding: 6px 12px; font-weight: bold; }}"
    f"QPushButton:hover {{ background: #4a9eff; }}"
)

_DANGER_BTN_STYLE = (
    f"QPushButton {{ color: {ERROR}; border: 1px solid {ERROR};"
    f" background: transparent; border-radius: 4px; padding: 6px 12px; }}"
    f"QPushButton:hover {{ background: {ERROR_BG}; }}"
)

_APPROVE_BTN_STYLE = (
    f"QPushButton {{ color: {SUCCESS}; border: 1px solid {SUCCESS};"
    f" background: transparent; border-radius: 4px; padding: 6px 12px; }}"
    f"QPushButton:hover {{ background: {SUCCESS_BG}; }}"
)

_REJECT_BTN_STYLE = (
    f"QPushButton {{ color: {ERROR}; border: 1px solid {ERROR};"
    f" background: transparent; border-radius: 4px; padding: 6px 12px; }}"
    f"QPushButton:hover {{ background: {ERROR_BG}; }}"
)

_MEMBER_ROW_STYLE = (
    f"QFrame {{ background: transparent; border: none; border-radius: 4px; padding: 2px 4px; }}"
    f"QFrame:hover {{ background: {HOVER}; }}"
)

_BADGE_STYLE = (
    f"background: {ACCENT}; color: white; border-radius: 8px;"
    f" font-size: 11px; font-weight: bold; padding: 1px 6px;"
    f" min-width: 16px;"
)


# ---------------------------------------------------------------------------
# Pending Requests Dialog
# ---------------------------------------------------------------------------

class _PendingRequestsDialog(QDialog):
    """Dialog showing pending join requests for the society leader."""

    request_action = pyqtSignal(int, str)  # (request_id, "approve" | "reject")
    open_profile = pyqtSignal(str)

    def __init__(self, pending: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pending Join Requests")
        self.setMinimumWidth(420)
        self.setMinimumHeight(200)
        self.setStyleSheet(
            f"QDialog {{ background: {PRIMARY}; color: {TEXT}; }}"
        )
        self._rows: dict[int, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        if not pending:
            empty = QLabel("No pending requests")
            empty.setStyleSheet(
                f"color: {TEXT_MUTED}; font-style: italic;"
                f" background: transparent; padding: 24px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            rows_layout = QVBoxLayout(container)
            rows_layout.setContentsMargins(0, 0, 0, 0)
            rows_layout.setSpacing(4)

            for req in pending:
                row = self._build_request_row(req)
                rows_layout.addWidget(row)
                self._rows[req.get("id", 0)] = row

            rows_layout.addStretch()
            scroll.setWidget(container)
            layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _build_request_row(self, req: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background: {SECONDARY}; border: 1px solid {BORDER};"
            f" border-radius: 4px; padding: 8px; }}"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        # User name button
        name = req.get("username", "Unknown")
        name_btn = QPushButton(name)
        name_btn.setStyleSheet(_LINK_BTN_STYLE)
        name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        name_btn.clicked.connect(lambda _, n=name: self.open_profile.emit(n))
        h.addWidget(name_btn)

        # Date
        date_str = req.get("created_at", "")
        if date_str:
            date_label = QLabel(date_str[:10])
            date_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
            )
            h.addWidget(date_label)

        h.addStretch()

        # Approve button
        approve = QPushButton("Approve")
        approve.setStyleSheet(_APPROVE_BTN_STYLE)
        approve.setCursor(Qt.CursorShape.PointingHandCursor)
        approve.clicked.connect(
            lambda _, rid=req.get("id", 0): self.request_action.emit(rid, "approve")
        )
        h.addWidget(approve)

        # Reject button
        reject = QPushButton("Reject")
        reject.setStyleSheet(_REJECT_BTN_STYLE)
        reject.setCursor(Qt.CursorShape.PointingHandCursor)
        reject.clicked.connect(
            lambda _, rid=req.get("id", 0): self.request_action.emit(rid, "reject")
        )
        h.addWidget(reject)

        return row

    def remove_request_row(self, request_id: int):
        """Remove a processed request row from the dialog."""
        row = self._rows.pop(request_id, None)
        if row:
            row.setParent(None)
            row.deleteLater()


# ---------------------------------------------------------------------------
# Society Page
# ---------------------------------------------------------------------------

class SocietyPage(QWidget):
    """Full society page for the PyQt6 desktop client."""

    # --- Signals ---
    navigation_changed = pyqtSignal(object)
    open_profile = pyqtSignal(str)

    # Cross-thread signals (private)
    _society_loaded = pyqtSignal(object)
    _save_result = pyqtSignal(bool, str)
    _request_result = pyqtSignal(int, bool, str)

    def __init__(self, *, signals: AppSignals, nexus_client: NexusClient,
                 parent=None):
        super().__init__(parent)
        self._signals = signals
        self._nexus_client = nexus_client

        self._identifier: str | None = None
        self._data: dict | None = None
        self._load_gen = 0
        self._editing = False
        self._pending_dialog: _PendingRequestsDialog | None = None

        # Build root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Outer scroll area wrapping everything
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        root.addWidget(self._scroll)

        # Inner content widget (rebuilt on navigate_to)
        self._content: QWidget | None = None

        # Connect cross-thread signals
        self._society_loaded.connect(self._on_society_loaded)
        self._save_result.connect(self._on_save_result)
        self._request_result.connect(self._on_request_result)

        # Show initial empty state
        self._show_empty_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def navigate_to(self, identifier: str):
        """Load and display a society by name or identifier."""
        self._identifier = identifier
        self._editing = False
        self._show_loading()
        self._load_society()
        self.navigation_changed.emit(identifier)

    def get_scroll_position(self) -> int:
        return self._scroll.verticalScrollBar().value()

    def set_scroll_position(self, pos: int):
        self._scroll.verticalScrollBar().setValue(pos)

    def set_sub_state(self, sub_state):
        """Called by MainWindow when restoring navigation history."""
        if sub_state and sub_state != self._identifier:
            self.navigate_to(sub_state)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_society(self):
        """Kick off a background thread to fetch society data."""
        self._load_gen += 1
        gen = self._load_gen
        identifier = self._identifier
        nc = self._nexus_client

        def _worker():
            data = nc.get_society(identifier)
            if gen == self._load_gen:
                self._society_loaded.emit(data)

        threading.Thread(
            target=_worker, daemon=True, name="society-load"
        ).start()

    def _on_society_loaded(self, data):
        """Handle society data arriving on the main thread."""
        if data is None:
            self._show_error("Society not found or failed to load.")
            return
        self._data = data
        self._rebuild_ui()

    # ------------------------------------------------------------------
    # UI states
    # ------------------------------------------------------------------

    def _swap_content(self, widget: QWidget):
        """Replace the scroll area content widget."""
        old = self._scroll.takeWidget()
        self._content = widget
        self._scroll.setWidget(widget)
        if old is not None and old is not widget:
            old.deleteLater()

    def _show_empty_state(self):
        """Show placeholder before any society is loaded."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 48, 24, 24)

        label = QLabel("Select a society")
        label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 16px; font-style: italic;"
            f" background: transparent;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()

        self._swap_content(w)

    def _show_loading(self):
        """Show loading indicator."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 48, 24, 24)

        label = QLabel("Loading society...")
        label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()

        self._swap_content(w)

    def _show_error(self, message: str):
        """Show an error message."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 48, 24, 24)

        label = QLabel(message)
        label.setStyleSheet(
            f"color: {ERROR}; font-size: 14px; background: transparent;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()

        self._swap_content(w)

    # ------------------------------------------------------------------
    # Main UI rebuild
    # ------------------------------------------------------------------

    def _rebuild_ui(self):
        """Build the complete society page from loaded data."""
        data = self._data
        if not data:
            return

        society = data.get("society", {})
        members = data.get("members", [])
        is_leader = data.get("isLeader", False)
        is_member = data.get("isMember", False)
        pending = data.get("pending", [])
        pending_count = data.get("pendingCount", 0)

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 24)
        page_layout.setSpacing(12)

        # --- Header Section ---
        self._build_header(page_layout, society, members, is_leader,
                           is_member, pending_count)

        # --- Content: two-card layout ---
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # Description card (stretch=2)
        desc_card = self._build_description_card(society, is_leader)
        cards_layout.addWidget(desc_card, stretch=2)

        # Members card (stretch=1)
        members_card = self._build_members_card(society, members)
        cards_layout.addWidget(members_card, stretch=1)

        page_layout.addLayout(cards_layout)
        page_layout.addStretch()

        self._swap_content(page)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self, parent_layout: QVBoxLayout, society: dict,
                      members: list, is_leader: bool, is_member: bool,
                      pending_count: int):
        """Build the header section with name, meta, and leader buttons."""
        # Society name + abbreviation
        name = society.get("name", "Unknown")
        abbrev = society.get("abbreviation")
        title_text = name
        if abbrev:
            title_text += f"  [{abbrev}]"

        title = QLabel(title_text)
        title.setObjectName(PAGE_HEADER_OBJECT_NAME)
        parent_layout.addWidget(title)

        # Meta row: leader name, member count, discord
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)

        # Leader name
        leader_id = society.get("leader_id")
        leader_name = self._find_member_name(members, leader_id)
        if leader_name:
            leader_label = QLabel("Leader:")
            leader_label.setStyleSheet(
                f"color: {TEXT_MUTED}; background: transparent; font-size: 13px;"
            )
            meta_row.addWidget(leader_label)

            leader_btn = QPushButton(leader_name)
            leader_btn.setStyleSheet(_LINK_BTN_STYLE)
            leader_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            leader_btn.clicked.connect(
                lambda _, n=leader_name: self.open_profile.emit(n)
            )
            meta_row.addWidget(leader_btn)

        # Member count
        member_count_label = QLabel(f"{len(members)} member{'s' if len(members) != 1 else ''}")
        member_count_label.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; font-size: 13px;"
        )
        meta_row.addWidget(member_count_label)

        # Discord link
        discord_code = society.get("discord_code")
        discord_public = society.get("discord_public", False)
        show_discord = discord_code and (discord_public or is_member)
        if show_discord:
            discord_btn = QPushButton("Discord")
            discord_btn.setIcon(svg_icon(_DISCORD_SVG, ACCENT, 16))
            discord_btn.setStyleSheet(_LINK_BTN_STYLE)
            discord_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            discord_btn.setToolTip(f"https://discord.gg/{discord_code}")
            discord_btn.clicked.connect(
                lambda _, code=discord_code: self._open_discord(code)
            )
            meta_row.addWidget(discord_btn)
        elif discord_code and not discord_public and not is_member:
            discord_label = QLabel("Discord: Members only")
            discord_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-style: italic;"
                f" background: transparent; font-size: 12px;"
            )
            meta_row.addWidget(discord_label)

        meta_row.addStretch()
        parent_layout.addLayout(meta_row)

        # Leader buttons row
        if is_leader:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            # Edit / Save / Cancel
            self._edit_btn = QPushButton("Edit")
            self._edit_btn.setStyleSheet(_BTN_STYLE)
            self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._edit_btn.clicked.connect(self._on_edit_clicked)
            btn_row.addWidget(self._edit_btn)

            self._save_btn = QPushButton("Save")
            self._save_btn.setStyleSheet(_ACCENT_BTN_STYLE)
            self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._save_btn.clicked.connect(self._on_save_clicked)
            self._save_btn.hide()
            btn_row.addWidget(self._save_btn)

            self._cancel_btn = QPushButton("Cancel")
            self._cancel_btn.setStyleSheet(_BTN_STYLE)
            self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._cancel_btn.clicked.connect(self._on_cancel_clicked)
            self._cancel_btn.hide()
            btn_row.addWidget(self._cancel_btn)

            # Pending invites button with badge
            pending_text = "Pending Requests"
            self._pending_btn = QPushButton(pending_text)
            self._pending_btn.setStyleSheet(_BTN_STYLE)
            self._pending_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._pending_btn.clicked.connect(self._on_pending_clicked)
            btn_row.addWidget(self._pending_btn)

            if pending_count > 0:
                badge = QLabel(str(pending_count))
                badge.setStyleSheet(_BADGE_STYLE)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setFixedHeight(18)
                btn_row.addWidget(badge)

            btn_row.addStretch()

            # Disband button
            disband_btn = QPushButton("Disband")
            disband_btn.setStyleSheet(_DANGER_BTN_STYLE)
            disband_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            disband_btn.clicked.connect(self._on_disband_clicked)
            btn_row.addWidget(disband_btn)

            parent_layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Description Card
    # ------------------------------------------------------------------

    def _build_description_card(self, society: dict, is_leader: bool) -> QFrame:
        """Build the description card (left side)."""
        card = QFrame()
        card.setStyleSheet(_CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        section_label = QLabel("DESCRIPTION")
        section_label.setStyleSheet(_SECTION_LABEL_STYLE)
        layout.addWidget(section_label)

        description = society.get("description") or ""

        # View mode: QTextBrowser
        self._desc_browser = QTextBrowser()
        self._desc_browser.setOpenExternalLinks(True)
        self._desc_browser.setStyleSheet(
            f"QTextBrowser {{ background: transparent; border: none;"
            f" color: {TEXT}; font-size: 13px; }}"
        )
        if description.strip():
            self._desc_browser.setHtml(self._sanitize_html(description))
        else:
            self._desc_browser.setHtml(
                f'<p style="color: {TEXT_MUTED}; font-style: italic;">'
                f"No description yet</p>"
            )
        layout.addWidget(self._desc_browser)

        # Edit mode widgets (hidden initially)
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(description)
        self._desc_edit.setStyleSheet(_INPUT_STYLE)
        self._desc_edit.setMinimumHeight(120)
        self._desc_edit.hide()
        layout.addWidget(self._desc_edit)

        # Discord input row
        self._discord_edit_row = QWidget()
        self._discord_edit_row.setStyleSheet("background: transparent;")
        discord_layout = QHBoxLayout(self._discord_edit_row)
        discord_layout.setContentsMargins(0, 4, 0, 0)
        discord_layout.setSpacing(8)

        discord_label = QLabel("Discord invite code:")
        discord_label.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; font-size: 13px;"
        )
        discord_layout.addWidget(discord_label)

        self._discord_input = QLineEdit()
        self._discord_input.setPlaceholderText("e.g. abc123")
        self._discord_input.setText(society.get("discord_code") or "")
        self._discord_input.setStyleSheet(_INPUT_STYLE)
        self._discord_input.setMaximumWidth(200)
        discord_layout.addWidget(self._discord_input)

        self._discord_public_cb = QCheckBox("Public")
        self._discord_public_cb.setChecked(society.get("discord_public", False))
        self._discord_public_cb.setToolTip(
            "If unchecked, only society members can see the Discord link"
        )
        discord_layout.addWidget(self._discord_public_cb)

        discord_layout.addStretch()
        self._discord_edit_row.hide()
        layout.addWidget(self._discord_edit_row)

        return card

    # ------------------------------------------------------------------
    # Members Card
    # ------------------------------------------------------------------

    def _build_members_card(self, society: dict, members: list) -> QFrame:
        """Build the members card (right side)."""
        card = QFrame()
        card.setStyleSheet(_CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        section_label = QLabel(f"MEMBERS ({len(members)})")
        section_label.setStyleSheet(_SECTION_LABEL_STYLE)
        layout.addWidget(section_label)

        # Scrollable member list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        members_layout = QVBoxLayout(container)
        members_layout.setContentsMargins(0, 0, 0, 0)
        members_layout.setSpacing(2)

        leader_id = society.get("leader_id")
        sorted_members = self._sort_members(members, leader_id)

        for member in sorted_members:
            row = self._build_member_row(member, leader_id)
            members_layout.addWidget(row)

        members_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return card

    def _build_member_row(self, member: dict, leader_id: int | None) -> QFrame:
        """Build a single member row with name and optional crown."""
        row = QFrame()
        row.setStyleSheet(_MEMBER_ROW_STYLE)
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)

        is_leader = member.get("id") == leader_id

        # Crown icon for leader
        if is_leader:
            crown_label = QLabel()
            crown_label.setPixmap(svg_pixmap(CROWN_SVG, CROWN_COLOR, 16))
            crown_label.setFixedSize(16, 16)
            crown_label.setStyleSheet("background: transparent;")
            crown_label.setToolTip("Society Leader")
            h.addWidget(crown_label)

        # Member name (clickable)
        display_name = self._get_display_name(member)
        name_btn = QPushButton(display_name)
        name_btn.setStyleSheet(_LINK_BTN_STYLE)
        name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        name_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_btn.clicked.connect(
            lambda _, n=display_name: self.open_profile.emit(n)
        )
        h.addWidget(name_btn)

        h.addStretch()

        return row

    # ------------------------------------------------------------------
    # Edit mode toggling
    # ------------------------------------------------------------------

    def _enter_edit_mode(self):
        """Switch description card to edit mode."""
        self._editing = True
        self._desc_browser.hide()
        self._desc_edit.show()
        self._discord_edit_row.show()
        self._edit_btn.hide()
        self._save_btn.show()
        self._cancel_btn.show()

    def _exit_edit_mode(self):
        """Switch description card back to view mode."""
        self._editing = False
        self._desc_browser.show()
        self._desc_edit.hide()
        self._discord_edit_row.hide()
        self._edit_btn.show()
        self._save_btn.hide()
        self._cancel_btn.hide()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_edit_clicked(self):
        self._enter_edit_mode()

    def _on_cancel_clicked(self):
        """Cancel editing and restore original values."""
        if self._data:
            society = self._data.get("society", {})
            self._desc_edit.setPlainText(society.get("description") or "")
            self._discord_input.setText(society.get("discord_code") or "")
            self._discord_public_cb.setChecked(
                society.get("discord_public", False)
            )
        self._exit_edit_mode()

    def _on_save_clicked(self):
        """Save society settings in a background thread."""
        if not self._identifier:
            return

        payload = {
            "description": self._desc_edit.toPlainText().strip(),
            "discord_code": self._discord_input.text().strip() or None,
            "discord_public": self._discord_public_cb.isChecked(),
        }

        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving...")

        self._load_gen += 1
        gen = self._load_gen
        nc = self._nexus_client
        identifier = self._identifier

        def _worker():
            result = nc.update_society(identifier, payload)
            if gen == self._load_gen:
                self._save_result.emit(
                    result is not None,
                    "" if result else "Failed to save society settings",
                )

        threading.Thread(
            target=_worker, daemon=True, name="society-save"
        ).start()

    def _on_save_result(self, success: bool, error_msg: str):
        """Handle save result on the main thread."""
        self._save_btn.setEnabled(True)
        self._save_btn.setText("Save")

        if success:
            self._exit_edit_mode()
            # Reload to reflect changes
            self._load_society()
        else:
            log.warning("Society save failed: %s", error_msg)
            QMessageBox.warning(self, "Save Failed", error_msg or "Unknown error")

    def _on_pending_clicked(self):
        """Open the pending requests dialog."""
        if not self._data:
            return
        pending = self._data.get("pending", [])
        dialog = _PendingRequestsDialog(pending, parent=self)
        dialog.request_action.connect(self._on_request_action)
        dialog.open_profile.connect(self.open_profile.emit)
        self._pending_dialog = dialog
        dialog.exec()
        self._pending_dialog = None

    def _on_request_action(self, request_id: int, action: str):
        """Handle approve/reject action in background."""
        nc = self._nexus_client

        def _worker():
            result = nc.handle_join_request(request_id, action)
            self._request_result.emit(
                request_id,
                result is not None,
                "" if result else f"Failed to {action} request",
            )

        threading.Thread(
            target=_worker, daemon=True, name=f"society-request-{action}"
        ).start()

    def _on_request_result(self, request_id: int, success: bool, error_msg: str):
        """Handle join request result on the main thread."""
        if success:
            # Remove the row from the dialog
            if self._pending_dialog:
                self._pending_dialog.remove_request_row(request_id)
            # Reload society data to update member list and pending count
            self._load_society()
        else:
            log.warning("Join request action failed: %s", error_msg)
            QMessageBox.warning(
                self, "Action Failed", error_msg or "Unknown error"
            )

    def _on_disband_clicked(self):
        """Handle disband with two-step confirmation."""
        result = QMessageBox.warning(
            self,
            "Disband Society",
            "Are you sure you want to disband this society?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        result2 = QMessageBox.critical(
            self,
            "Confirm Disband",
            "This action cannot be undone. All members will be removed.\n\n"
            "Do you really want to disband?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result2 != QMessageBox.StandardButton.Yes:
            return

        # TODO: Call disband API when available
        log.info("Disband confirmed for society: %s", self._identifier)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_member_name(members: list, leader_id: int | None) -> str | None:
        """Find the display name of a member by ID."""
        if leader_id is None:
            return None
        for m in members:
            if m.get("id") == leader_id:
                return SocietyPage._get_display_name(m)
        return None

    @staticmethod
    def _get_display_name(member: dict) -> str:
        """Return the best display name for a member."""
        eu_name = member.get("eu_name")
        if eu_name:
            return eu_name
        global_name = member.get("global_name")
        if global_name:
            return global_name
        username = member.get("username", "Unknown")
        discriminator = member.get("discriminator")
        if discriminator:
            return f"{username}#{discriminator}"
        return username

    @staticmethod
    def _sort_members(members: list, leader_id: int | None) -> list:
        """Sort members: leader first, then alphabetical by display name."""
        def sort_key(m):
            is_leader = 0 if m.get("id") == leader_id else 1
            name = SocietyPage._get_display_name(m).lower()
            return (is_leader, name)
        return sorted(members, key=sort_key)

    @staticmethod
    def _sanitize_html(html: str) -> str:
        """Basic HTML sanitization — strip script tags and event handlers."""
        import re
        # Remove script tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html,
                       flags=re.DOTALL | re.IGNORECASE)
        # Remove event handler attributes
        html = re.sub(r"\s+on\w+\s*=\s*[\"'][^\"']*[\"']", "", html,
                       flags=re.IGNORECASE)
        html = re.sub(r"\s+on\w+\s*=\s*\S+", "", html,
                       flags=re.IGNORECASE)
        return html

    @staticmethod
    def _open_discord(code: str):
        """Open a Discord invite link in the default browser."""
        import webbrowser
        webbrowser.open(f"https://discord.gg/{code}")
