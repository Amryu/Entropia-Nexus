"""Opt-in dialog for anonymized skill data contribution."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QFrame,
)
from PyQt6.QtCore import Qt

from ..theme import PRIMARY, SECONDARY, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, BORDER


class SkillDataOptinDialog(QDialog):
    """Ask the user to contribute anonymized skill data.

    After ``exec()``, read ``self.accepted`` and ``self.skills_changed``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contribute Skill Data")
        self.setMinimumWidth(480)
        self.setModal(True)

        self.accepted_result = False
        self.skills_changed = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("Contribute Skill Data")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        layout.addWidget(header)

        # Explanation
        body = QLabel(
            "Your recent skill scan was successful. Would you like to "
            "contribute your anonymized skill data to help build community tools "
            "like a Time-to-Train calculator and skill gain analysis?\n\n"
            "What is shared:\n"
            "\u2022 Your current skill point values from the scan\n"
            "\u2022 Skill gain events from your chat.log (amounts and timestamps)\n\n"
            "Your identity is not stored \u2014 only a one-way hash is used to "
            "link submissions from the same contributor, so bad data can be filtered."
        )
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {TEXT}; line-height: 1.5;")
        layout.addWidget(body)

        # Settings note
        note = QLabel("You can opt out at any time in Settings.")
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
        layout.addWidget(note)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(line)

        # "Skills changed?" question
        q_label = QLabel(
            "Have your skills changed since you opened the skill window "
            "and started scanning?"
        )
        q_label.setWordWrap(True)
        q_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        layout.addWidget(q_label)

        self._radio_no = QRadioButton("No, the scan data is current")
        self._radio_yes = QRadioButton("Yes, I may have gained skills during the scan")
        self._radio_no.setChecked(True)
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._radio_no, 0)
        self._radio_group.addButton(self._radio_yes, 1)
        layout.addWidget(self._radio_no)
        layout.addWidget(self._radio_yes)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        decline_btn = QPushButton("No Thanks")
        decline_btn.setStyleSheet(
            f"padding: 8px 20px; background: {SECONDARY}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 4px;"
        )
        decline_btn.clicked.connect(self._on_decline)
        btn_row.addWidget(decline_btn)

        accept_btn = QPushButton("Contribute")
        accept_btn.setStyleSheet(
            f"padding: 8px 20px; background: {ACCENT}; color: white; "
            f"border: none; border-radius: 4px;"
        )
        accept_btn.setDefault(True)
        accept_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(accept_btn)

        layout.addLayout(btn_row)

    def _on_accept(self):
        self.accepted_result = True
        self.skills_changed = self._radio_yes.isChecked()
        self.accept()

    def _on_decline(self):
        self.accepted_result = False
        self.skills_changed = False
        self.reject()
