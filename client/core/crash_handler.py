"""Crash handler — collects diagnostic info and shows a user-facing dialog.

Installs hooks for both main-thread and background-thread exceptions.
The crash report intentionally excludes personal data (file paths,
player names, tokens) and only includes technical diagnostics.
"""

from __future__ import annotations

import os
import platform
import sys
import threading
import traceback
from datetime import datetime, timezone

_qt_app = None  # set by set_qt_app() once QApplication exists
_original_excepthook = sys.excepthook
_showing_dialog = False  # prevent re-entrant crash dialogs


def install() -> None:
    """Install global exception hooks. Call early in app.main()."""
    sys.excepthook = _on_main_exception
    threading.excepthook = _on_thread_exception


def set_qt_app(app) -> None:
    """Register the QApplication instance so crash dialogs can be shown."""
    global _qt_app
    _qt_app = app


# ------------------------------------------------------------------
# Exception hooks
# ------------------------------------------------------------------

def _on_main_exception(exc_type, exc_value, exc_tb):
    """Handle uncaught exceptions on the main thread."""
    # Don't catch KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        _original_excepthook(exc_type, exc_value, exc_tb)
        return

    report = _collect_report(exc_type, exc_value, exc_tb)
    _handle_crash(report)


def _on_thread_exception(args):
    """Handle uncaught exceptions in background threads (Python 3.8+)."""
    if args.exc_type is SystemExit:
        return

    report = _collect_report(args.exc_type, args.exc_value, args.exc_traceback,
                             thread_name=args.thread.name if args.thread else None)
    _handle_crash(report)


# ------------------------------------------------------------------
# Report collection
# ------------------------------------------------------------------

def _collect_report(exc_type, exc_value, exc_tb, *, thread_name=None) -> str:
    """Build a diagnostic crash report string. No personal data."""
    sections = []

    # Header
    sections.append("Entropia Nexus Crash Report")
    sections.append("=" * 40)

    # Environment
    version = _get_version()
    pyqt_version = _get_pyqt_version()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    sections.append(f"Version:   {version}")
    sections.append(f"Timestamp: {now}")
    sections.append(f"Python:    {sys.version.split()[0]}")
    sections.append(f"PyQt6:     {pyqt_version}")
    sections.append(f"Platform:  {platform.platform()}")
    if thread_name:
        sections.append(f"Thread:    {thread_name}")
    sections.append("")

    # Exception
    sections.append("Exception")
    sections.append("-" * 40)
    sections.append(f"Type:    {exc_type.__name__ if exc_type else 'Unknown'}")
    sections.append(f"Message: {exc_value}")
    sections.append("")
    if exc_tb:
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        # Sanitize file paths: replace the user-specific prefix with "..."
        sanitized = _sanitize_paths("".join(tb_lines))
        sections.append(sanitized.rstrip())
    sections.append("")

    # Active threads
    sections.append("Active Threads")
    sections.append("-" * 40)
    for t in sorted(threading.enumerate(), key=lambda t: t.name):
        daemon = ", daemon" if t.daemon else ""
        alive = "alive" if t.is_alive() else "dead"
        sections.append(f"  - {t.name} ({alive}{daemon})")
    sections.append("")

    # Recent log messages
    sections.append("Recent Log Messages")
    sections.append("-" * 40)
    logs = _get_recent_logs()
    if logs:
        for line in logs:
            sections.append(f"  {_sanitize_paths(line)}")
    else:
        sections.append("  (no log messages captured)")

    return "\n".join(sections)


def _get_version() -> str:
    try:
        from ..updater import get_local_version
        return get_local_version()
    except Exception:
        return "unknown"


def _get_pyqt_version() -> str:
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR
        return PYQT_VERSION_STR
    except Exception:
        return "unknown"


def _get_recent_logs() -> list[str]:
    try:
        from .logger import get_recent_logs
        return get_recent_logs()
    except Exception:
        return []


def _sanitize_paths(text: str) -> str:
    """Replace user-specific path prefixes with '...' to avoid leaking usernames."""
    # Replace common path prefixes that contain the username
    home = os.path.expanduser("~")
    if home and home != "~":
        text = text.replace(home, "...")
        # Also replace with forward slashes (traceback may use either)
        text = text.replace(home.replace("\\", "/"), "...")
    return text


# ------------------------------------------------------------------
# Crash handling
# ------------------------------------------------------------------

def _handle_crash(report: str) -> None:
    """Show crash dialog or fall back to file + stderr."""
    global _showing_dialog
    if _showing_dialog:
        # Re-entrant crash — just print to stderr
        print(report, file=sys.stderr)
        return
    _showing_dialog = True

    # Always print to stderr as a baseline
    print(report, file=sys.stderr)

    # Try to show Qt dialog
    if _qt_app is not None and threading.current_thread() is threading.main_thread():
        try:
            _show_crash_dialog(report)
            return
        except Exception:
            pass

    # If we're on a background thread and Qt is available, schedule on main thread
    if _qt_app is not None:
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _show_crash_dialog(report))
            return
        except Exception:
            pass

    # Fallback: write to file
    _write_crash_file(report)


def _write_crash_file(report: str) -> None:
    """Write crash report to a file in the current directory."""
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = f"nexus-crash-{ts}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Crash report saved to: {path}", file=sys.stderr)
    except Exception:
        pass


def _show_crash_dialog(report: str) -> None:
    """Show a Qt dialog with the crash report."""
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
        QPushButton, QApplication, QFileDialog,
    )
    from PyQt6.QtGui import QFont
    from PyQt6.QtCore import Qt

    dialog = QDialog()
    dialog.setWindowTitle("Entropia Nexus \u2014 Unexpected Error")
    dialog.setMinimumSize(700, 500)
    dialog.setWindowFlags(
        dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
    )

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)

    # Header
    header = QLabel(
        "An unexpected error occurred. The report below contains "
        "diagnostic information that can help resolve the issue.\n"
        "No personal data is included."
    )
    header.setWordWrap(True)
    header.setStyleSheet("font-size: 13px; padding: 4px;")
    layout.addWidget(header)

    # Report text
    text_edit = QPlainTextEdit()
    text_edit.setPlainText(report)
    text_edit.setReadOnly(True)
    text_edit.setFont(QFont("Consolas", 9))
    text_edit.setStyleSheet(
        "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4;"
        " border: 1px solid #555; border-radius: 4px; padding: 8px; }"
    )
    layout.addWidget(text_edit, 1)

    # Buttons
    btn_row = QHBoxLayout()
    btn_row.addStretch()

    copy_btn = QPushButton("Copy to Clipboard")
    copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _copy():
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(report)
        copy_btn.setText("Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: copy_btn.setText("Copy to Clipboard"))

    copy_btn.clicked.connect(_copy)
    btn_row.addWidget(copy_btn)

    save_btn = QPushButton("Save to File")
    save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _save():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"nexus-crash-{ts}.txt"
        path, _ = QFileDialog.getSaveFileName(
            dialog, "Save Crash Report", default_name,
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report)
                save_btn.setText("Saved!")
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: save_btn.setText("Save to File"))
            except Exception as e:
                save_btn.setText(f"Error: {e}")

    save_btn.clicked.connect(_save)
    btn_row.addWidget(save_btn)

    close_btn = QPushButton("Close")
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.clicked.connect(dialog.accept)
    btn_row.addWidget(close_btn)

    layout.addLayout(btn_row)

    dialog.exec()
