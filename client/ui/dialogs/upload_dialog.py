"""Unified media upload dialog — screenshots and video clips.

Handles image uploads, video platform linking, budget display, and
checksum-based duplicate detection in a single dialog.
"""

import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFrame, QProgressBar, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from ..theme import (
    PRIMARY, SECONDARY, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    BORDER, HOVER,
    BADGE_HOF, BADGE_ATH, BADGE_GLOBAL,
    SUCCESS, ERROR,
)
from ...core.database import compute_file_hash
from ...core.logger import get_logger

log = get_logger("UploadDialog")

# Video platforms for clip sharing
_PLATFORMS = [
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/upload",
        "tip": "Upload your clip, then copy the video URL.",
    },
    {
        "name": "Twitch",
        "url": None,
        "tip": "Twitch clips are created from live streams.\n"
               "Copy the clip URL from your Twitch dashboard.",
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/upload",
        "tip": "Upload your clip, then copy the video URL.",
    },
]


class _BudgetWorker(QThread):
    """Fetch upload budget in background."""
    finished = pyqtSignal(dict)  # {images: {used, limit, remaining}, videos: ...}

    def __init__(self, nexus_client):
        super().__init__()
        self._client = nexus_client

    def run(self):
        try:
            budget = self._client.get_upload_budget()
            self.finished.emit(budget or {})
        except Exception:
            self.finished.emit({})


class _HashWorker(QThread):
    """Compute file hash in background."""
    finished = pyqtSignal(str)  # hex digest or ""

    def __init__(self, file_path: str):
        super().__init__()
        self._path = file_path

    def run(self):
        h = compute_file_hash(self._path)
        self.finished.emit(h or "")


class _ResolveAndUploadWorker(QThread):
    """Background worker: resolve server global, check budget, upload."""
    finished = pyqtSignal(dict)

    def __init__(self, nexus_client, db, screenshot_info, file_path,
                 video_url=None, file_hash=None):
        super().__init__()
        self._client = nexus_client
        self._db = db
        self._info = screenshot_info
        self._path = file_path
        self._video_url = video_url
        self._file_hash = file_hash

    def run(self):
        try:
            # 1. Check budget
            budget = self._client.get_upload_budget()
            if budget is None:
                self.finished.emit({
                    "success": False,
                    "error": "Failed to check upload budget. Are you logged in?",
                })
                return

            if self._video_url:
                remaining = budget.get("videos", budget.get("youtube", {})).get("remaining", 0)
                if remaining <= 0:
                    self.finished.emit({"success": False, "error": "Monthly video link budget exhausted."})
                    return
            else:
                remaining = budget.get("images", {}).get("remaining", 0)
                if remaining <= 0:
                    self.finished.emit({"success": False, "error": "Monthly image upload budget exhausted."})
                    return

            # 2. Resolve server global ID
            server_id = self._info.get("server_global_id")
            if not server_id:
                server_id = self._resolve_server_global()
            if not server_id:
                self.finished.emit({
                    "success": False,
                    "error": "Could not find matching global on server. "
                             "The global may not have been ingested yet.",
                })
                return

            # 3. Upload or link
            if self._video_url:
                result = self._client.submit_global_video(server_id, self._video_url)
            else:
                result = self._client.upload_global_media(server_id, self._path)

            if result is None:
                self.finished.emit({"success": False, "error": "Upload failed. Check logs for details."})
                return

            # 4. Update local DB
            ss_id = self._info.get("id")
            if ss_id:
                self._db.update_screenshot_upload(ss_id, "uploaded", server_id)
                if self._file_hash:
                    self._db.update_screenshot_hash(ss_id, self._file_hash)
                if self._video_url:
                    self._db.update_screenshot_video_url(ss_id, self._video_url)

            self.finished.emit({
                "success": True,
                "server_global_id": server_id,
                "budget_remaining": result.get("budget_remaining"),
            })
        except Exception as e:
            log.error("Upload worker error: %s", e)
            self.finished.emit({"success": False, "error": str(e)})

    def _resolve_server_global(self) -> int | None:
        """Search /api/globals for a matching server global."""
        player = self._info.get("player_name", "")
        target = self._info.get("target_name", "")
        if not player or not target:
            return None

        params = {"player": player, "target": target, "limit": "10"}
        result = self._client._session.get(
            self._client._url("/globals"),
            params=params,
            timeout=10,
        )
        if result.status_code != 200:
            return None

        data = result.json()
        globals_list = data.get("globals", [])
        if not globals_list:
            return None

        import datetime
        local_ts = self._info.get("timestamp", "")
        local_value = self._info.get("value", 0)

        best = None
        best_diff = float("inf")
        for g in globals_list:
            try:
                g_ts = g.get("timestamp", "")
                if local_ts and g_ts:
                    local_dt = datetime.datetime.fromisoformat(local_ts.replace("Z", "+00:00"))
                    g_dt = datetime.datetime.fromisoformat(str(g_ts).replace("Z", "+00:00"))
                    diff = abs((local_dt - g_dt).total_seconds())
                else:
                    diff = 0
                if local_value and abs(float(g.get("value", 0)) - float(local_value)) < 0.01:
                    diff -= 10000
                if diff < best_diff:
                    best_diff = diff
                    best = g
            except Exception:
                continue

        return best.get("id") if best else None


# Keep backward-compatible alias
ScreenshotUploadDialog = None  # replaced below


class MediaUploadDialog(QDialog):
    """Unified upload dialog for screenshots and video clips.

    Features:
    - Budget display (fetched on open)
    - Checksum duplicate detection
    - Video platform linking (YouTube, Twitch, Vimeo) for clips
    - Image upload for both globals and non-global screenshots
    """

    upload_completed = pyqtSignal(str, int)  # (file_path, server_global_id)

    def __init__(self, file_path: str, screenshot_info: dict, db, nexus_client,
                 *, parent=None):
        super().__init__(parent)
        self._path = file_path
        self._info = screenshot_info
        self._db = db
        self._client = nexus_client
        self._worker = None
        self._budget_worker = None
        self._hash_worker = None
        self._file_hash = None
        self._is_clip = screenshot_info.get("file_type", "screenshot") == "clip"
        self._has_global = bool(screenshot_info.get("global_type"))

        title = "Upload Clip" if self._is_clip else "Upload Screenshot"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {SECONDARY}; color: {TEXT}; }}
            QLabel {{ background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # --- Preview ---
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(400, 220, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            preview_label.setPixmap(scaled)
        else:
            preview_label.setText("Preview unavailable")
            preview_label.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(preview_label)

        # --- Budget bar ---
        budget_frame = QFrame()
        budget_frame.setStyleSheet(
            f"QFrame {{ background: {HOVER}; border: none; "
            f"border-radius: 4px; }}"
        )
        budget_lay = QVBoxLayout(budget_frame)
        budget_lay.setContentsMargins(10, 8, 10, 10)
        budget_lay.setSpacing(2)

        self._budget_img_label = QLabel("Images: loading...")
        self._budget_img_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        budget_lay.addWidget(self._budget_img_label)
        self._budget_img_bar = QProgressBar()
        self._budget_img_bar.setMaximumHeight(6)
        self._budget_img_bar.setTextVisible(False)
        self._budget_img_bar.setRange(0, 100)
        self._budget_img_bar.setStyleSheet(
            f"QProgressBar {{ background: {BORDER}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}"
        )
        budget_lay.addWidget(self._budget_img_bar)

        if self._is_clip:
            budget_lay.addSpacing(8)
            self._budget_vid_label = QLabel("Videos: loading...")
            self._budget_vid_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            budget_lay.addWidget(self._budget_vid_label)
            self._budget_vid_bar = QProgressBar()
            self._budget_vid_bar.setMaximumHeight(6)
            self._budget_vid_bar.setTextVisible(False)
            self._budget_vid_bar.setRange(0, 30)
            self._budget_vid_bar.setStyleSheet(
                f"QProgressBar {{ background: {BORDER}; border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}"
            )
            budget_lay.addWidget(self._budget_vid_bar)
        else:
            self._budget_vid_label = None
            self._budget_vid_bar = None

        layout.addWidget(budget_frame)

        # --- Global info ---
        global_type = screenshot_info.get("global_type")
        if global_type:
            info_frame = QFrame()
            info_frame.setStyleSheet(
                f"QFrame {{ background: {HOVER}; border: 1px solid {BORDER}; "
                f"border-radius: 6px; padding: 8px; }}"
            )
            info_layout = QHBoxLayout(info_frame)
            info_layout.setContentsMargins(8, 6, 8, 6)

            type_text = global_type.replace("_", " ").title()
            is_ath = screenshot_info.get("is_ath")
            is_hof = screenshot_info.get("is_hof")
            badge_color = BADGE_ATH if is_ath else (BADGE_HOF if is_hof else BADGE_GLOBAL)
            badge_label = "ATH" if is_ath else ("HoF" if is_hof else "Global")

            type_lbl = QLabel(f'<span style="color:{badge_color}; font-weight:bold;">'
                              f'{badge_label}</span> — {type_text}')
            type_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
            info_layout.addWidget(type_lbl)

            target = screenshot_info.get("target_name", "")
            value = screenshot_info.get("value", 0)
            detail = f"{target}"
            if value:
                detail += f" — {float(value):.2f} PED"
            detail_lbl = QLabel(detail)
            detail_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            info_layout.addWidget(detail_lbl)
            info_layout.addStretch()
            layout.addWidget(info_frame)
        else:
            no_global = QLabel("No associated global event — upload requires a global.")
            no_global.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(no_global)

        # --- Checksum status ---
        self._hash_label = QLabel("")
        self._hash_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._hash_label.setWordWrap(True)
        layout.addWidget(self._hash_label)

        # --- Notes ---
        notes_label = QLabel("Notes (optional)")
        notes_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(notes_label)

        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(50)
        self._notes_edit.setPlaceholderText("Add a note about this capture...")
        self._notes_edit.setStyleSheet(
            f"QTextEdit {{ background: {HOVER}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; font-size: 12px; }}"
        )
        existing_notes = screenshot_info.get("notes", "")
        if existing_notes:
            self._notes_edit.setPlainText(existing_notes)
        layout.addWidget(self._notes_edit)

        # --- Video platform section (clips only) ---
        self._video_url_edit = None
        self._link_btn = None
        if self._is_clip:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {BORDER};")
            layout.addWidget(sep)

            vid_header = QLabel("Link Video")
            vid_header.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT};")
            layout.addWidget(vid_header)

            vid_hint = QLabel(
                "Upload your clip to a video platform, then paste the URL below."
            )
            vid_hint.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
            vid_hint.setWordWrap(True)
            layout.addWidget(vid_hint)

            # Platform buttons
            plat_row = QHBoxLayout()
            plat_row.setSpacing(6)
            for platform in _PLATFORMS:
                btn = QPushButton(platform["name"])
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {HOVER};
                        color: {TEXT};
                        border: 1px solid {BORDER};
                        border-radius: 4px;
                        padding: 6px 12px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {ACCENT};
                        color: white;
                        border-color: {ACCENT};
                    }}
                """)
                btn.setToolTip(platform["tip"])
                btn.clicked.connect(lambda checked, p=platform: self._on_platform_click(p))
                plat_row.addWidget(btn)
            plat_row.addStretch()
            layout.addLayout(plat_row)

            self._platform_status = QLabel("")
            self._platform_status.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
            self._platform_status.setWordWrap(True)
            layout.addWidget(self._platform_status)

            # URL input + link button
            url_row = QHBoxLayout()
            url_row.setSpacing(6)
            self._video_url_edit = QLineEdit()
            self._video_url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
            self._video_url_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {PRIMARY};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 4px;
                    padding: 6px 8px;
                    font-size: 12px;
                }}
                QLineEdit:focus {{ border-color: {ACCENT}; }}
            """)
            self._video_url_edit.returnPressed.connect(self._on_link_video)
            url_row.addWidget(self._video_url_edit, 1)

            self._link_btn = QPushButton("Link")
            self._link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._link_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
                QPushButton:disabled {{ background-color: {HOVER}; color: {TEXT_MUTED}; }}
            """)
            self._link_btn.clicked.connect(self._on_link_video)
            if not self._has_global:
                self._link_btn.setEnabled(False)
            url_row.addWidget(self._link_btn)
            layout.addLayout(url_row)

        # --- Status ---
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {HOVER}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; }}"
        )
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        upload_label = "Upload Image" if self._is_clip else "Upload"
        self._upload_btn = QPushButton(upload_label)
        self._upload_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: white; "
            f"border: none; border-radius: 4px; padding: 6px 18px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #4a9eff; }}"
            f"QPushButton:disabled {{ background: {HOVER}; color: {TEXT_MUTED}; }}"
        )
        self._upload_btn.clicked.connect(self._start_upload)
        btn_row.addWidget(self._upload_btn)
        layout.addLayout(btn_row)

        # Disable upload if no global
        if not self._has_global:
            self._upload_btn.setEnabled(False)
            self._status.setText("Upload requires an associated global event.")
            self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")

        # --- Start background workers ---
        self._start_budget_fetch()
        self._start_hash_check()

    # ------------------------------------------------------------------
    # Background workers
    # ------------------------------------------------------------------

    def _start_budget_fetch(self):
        self._budget_worker = _BudgetWorker(self._client)
        self._budget_worker.finished.connect(self._on_budget_loaded)
        self._budget_worker.start()

    def _on_budget_loaded(self, budget: dict):
        self._budget_worker = None
        imgs = budget.get("images", {})
        img_used = imgs.get("used", 0)
        img_limit = imgs.get("limit", 100)
        img_remaining = imgs.get("remaining", img_limit - img_used)
        self._budget_img_label.setText(f"Images: {img_remaining} / {img_limit} remaining")
        self._budget_img_bar.setRange(0, img_limit)
        self._budget_img_bar.setValue(img_remaining)

        if self._budget_vid_label:
            vids = budget.get("videos", budget.get("youtube", {}))
            vid_used = vids.get("used", 0)
            vid_limit = vids.get("limit", 30)
            vid_remaining = vids.get("remaining", vid_limit - vid_used)
            self._budget_vid_label.setText(f"Videos: {vid_remaining} / {vid_limit} remaining")
            self._budget_vid_bar.setRange(0, vid_limit)
            self._budget_vid_bar.setValue(vid_remaining)

        if not budget:
            self._budget_img_label.setText("Budget unavailable — are you logged in?")

    def _start_hash_check(self):
        self._hash_worker = _HashWorker(self._path)
        self._hash_worker.finished.connect(self._on_hash_computed)
        self._hash_worker.start()

    def _on_hash_computed(self, file_hash: str):
        self._hash_worker = None
        self._file_hash = file_hash or None
        if not file_hash:
            return

        # Check for duplicates
        dup = self._db.get_uploaded_screenshot_by_hash(file_hash)
        if dup:
            uploaded_at = dup.get("uploaded_at", "unknown date")
            self._hash_label.setText(
                f"This file appears to have been uploaded before ({uploaded_at}). "
                f"You can still upload it again."
            )
            self._hash_label.setStyleSheet(f"color: #e0a030; font-size: 11px;")

    # ------------------------------------------------------------------
    # Video platform linking (clips)
    # ------------------------------------------------------------------

    def _on_platform_click(self, platform: dict):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._path)

        if platform["url"]:
            webbrowser.open(platform["url"])
            self._platform_status.setText(
                f"Clip path copied to clipboard. {platform['name']} opened in browser."
            )
            self._platform_status.setStyleSheet(f"font-size: 11px; color: {ACCENT};")
        else:
            self._platform_status.setText(
                f"Clip path copied to clipboard. {platform['tip']}"
            )
            self._platform_status.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")

    def _on_link_video(self):
        if not self._video_url_edit:
            return
        url = self._video_url_edit.text().strip()
        if not url:
            return

        server_global_id = self._info.get("server_global_id")
        if not server_global_id:
            self._status.setText("Cannot link: no server global associated.")
            self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")
            return

        self._link_btn.setEnabled(False)
        self._link_btn.setText("Linking...")

        try:
            result = self._client.submit_global_video(server_global_id, url)
            if result and result.get("success"):
                ss_id = self._info.get("id")
                if ss_id and self._db:
                    self._db.update_screenshot_video_url(ss_id, url)
                    self._db.update_screenshot_upload(ss_id, "uploaded")

                self._status.setText("Video linked successfully!")
                self._status.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
                self._video_url_edit.setEnabled(False)
                self._link_btn.setText("Linked")
                self.upload_completed.emit(self._path, server_global_id)
            elif result and result.get("error"):
                self._status.setText(result["error"])
                self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")
                self._link_btn.setEnabled(True)
                self._link_btn.setText("Link")
            else:
                self._status.setText("Failed to link video. Please try again.")
                self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")
                self._link_btn.setEnabled(True)
                self._link_btn.setText("Link")
        except Exception as e:
            log.error("Failed to link video: %s", e)
            self._status.setText(f"Error: {e}")
            self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")
            self._link_btn.setEnabled(True)
            self._link_btn.setText("Link")

    # ------------------------------------------------------------------
    # Image upload
    # ------------------------------------------------------------------

    def _start_upload(self):
        self._upload_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._status.setText("Uploading...")
        self._status.setStyleSheet(f"color: {ACCENT}; font-size: 11px;")

        # Save notes
        notes = self._notes_edit.toPlainText().strip()
        if notes:
            self._db.update_screenshot_notes_by_path(self._path, notes)

        self._worker = _ResolveAndUploadWorker(
            self._client, self._db, self._info, self._path,
            file_hash=self._file_hash,
        )
        self._worker.finished.connect(self._on_upload_finished)
        self._worker.start()

    def _on_upload_finished(self, result):
        self._worker = None
        if result.get("success"):
            server_id = result.get("server_global_id", 0)
            remaining = result.get("budget_remaining")
            msg = "Upload successful!"
            if remaining is not None:
                msg += f" ({remaining} remaining this month)"
            self._status.setText(msg)
            self._status.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
            self._upload_btn.setText("Done")
            self._upload_btn.setEnabled(False)
            self._cancel_btn.setText("Close")
            self._cancel_btn.setEnabled(True)
            self.upload_completed.emit(self._path, server_id)
        else:
            error = result.get("error", "Unknown error")
            self._status.setText(f"Error: {error}")
            self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")
            self._upload_btn.setEnabled(True)
            self._cancel_btn.setEnabled(True)


# Backward-compatible alias
ScreenshotUploadDialog = MediaUploadDialog
