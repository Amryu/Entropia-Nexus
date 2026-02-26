"""Skills page — scan status, results, and upload to Nexus."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
)
from PyQt6.QtCore import Qt

from ...core.constants import EVENT_SKILLS_UPLOADED, EVENT_SKILLS_UPLOAD_FAILED


class SkillsPage(QWidget):
    """Skills scan status and upload functionality."""

    def __init__(self, *, signals, oauth, nexus_client):
        super().__init__()
        self._signals = signals
        self._oauth = oauth
        self._nexus_client = nexus_client
        self._last_scan_result = None

        layout = QVBoxLayout(self)

        header = QLabel("Skills")
        header.setObjectName("pageHeader")
        layout.addWidget(header)

        # Scan progress
        progress_group = QGroupBox("OCR Scan Progress")
        progress_layout = QVBoxLayout(progress_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximum(165)
        progress_layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("Waiting for scan...")
        progress_layout.addWidget(self._progress_label)

        layout.addWidget(progress_group)

        # Upload section
        upload_group = QGroupBox("Upload to Entropia Nexus")
        upload_layout = QVBoxLayout(upload_group)

        self._upload_status = QLabel("Scan skills first, then upload.")
        upload_layout.addWidget(self._upload_status)

        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload Skills")
        self._upload_btn.setEnabled(False)
        self._upload_btn.clicked.connect(self._on_upload)
        btn_row.addWidget(self._upload_btn)
        btn_row.addStretch()
        upload_layout.addLayout(btn_row)

        layout.addWidget(upload_group)

        # Results table
        results_group = QGroupBox("Scanned Skills")
        results_layout = QVBoxLayout(results_group)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Skill", "Rank", "Points", "Progress"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        results_layout.addWidget(self._table)

        layout.addWidget(results_group)

        # Connect signals
        signals.ocr_progress.connect(self._on_ocr_progress)
        signals.ocr_complete.connect(self._on_ocr_complete)
        signals.skills_uploaded.connect(self._on_upload_success)
        signals.skills_upload_failed.connect(self._on_upload_failed)
        signals.auth_state_changed.connect(self._on_auth_changed)

    def _on_ocr_progress(self, data):
        if hasattr(data, 'total_found'):
            self._progress_bar.setValue(data.total_found)
            self._progress_label.setText(
                f"Found {data.total_found}/{data.total_expected} skills"
            )

    def _on_ocr_complete(self, result):
        self._last_scan_result = result
        self._progress_label.setText(
            f"Scan complete: {result.total_found}/{result.total_expected} skills"
        )
        self._progress_bar.setValue(result.total_found)

        # Populate table
        skills = result.skills if hasattr(result, 'skills') else []
        self._table.setRowCount(len(skills))
        for i, skill in enumerate(skills):
            self._table.setItem(i, 0, QTableWidgetItem(skill.skill_name))
            self._table.setItem(i, 1, QTableWidgetItem(skill.rank))
            self._table.setItem(i, 2, QTableWidgetItem(f"{skill.current_points:.2f}"))
            self._table.setItem(i, 3, QTableWidgetItem(f"{skill.progress_percent:.1f}%"))

        # Enable upload if authenticated
        self._upload_btn.setEnabled(self._oauth.is_authenticated())
        self._upload_status.setText("Ready to upload." if self._oauth.is_authenticated()
                                    else "Login required to upload.")

    def _on_upload(self):
        if not self._last_scan_result or not self._oauth.is_authenticated():
            return

        self._upload_btn.setEnabled(False)
        self._upload_status.setText("Uploading...")

        skills = {s.skill_name: s.current_points
                  for s in self._last_scan_result.skills}

        import threading
        threading.Thread(
            target=self._do_upload, args=(skills,), daemon=True
        ).start()

    def _do_upload(self, skills):
        result = self._nexus_client.upload_skills(skills)
        from ...core.constants import EVENT_SKILLS_UPLOADED, EVENT_SKILLS_UPLOAD_FAILED
        if result:
            self._signals.skills_uploaded.emit(result)
        else:
            self._signals.skills_upload_failed.emit("Upload failed")

    def _on_upload_success(self, result):
        self._upload_status.setText("Upload successful!")
        self._upload_btn.setEnabled(True)

    def _on_upload_failed(self, error):
        self._upload_status.setText(f"Upload failed: {error}")
        self._upload_btn.setEnabled(True)

    def _on_auth_changed(self, state):
        if self._last_scan_result:
            self._upload_btn.setEnabled(state.authenticated)
            self._upload_status.setText(
                "Ready to upload." if state.authenticated else "Login required to upload."
            )
