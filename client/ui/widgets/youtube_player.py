"""YouTube embedded player widget using QWebEngineView.

Falls back to opening in the system browser if PyQt6-WebEngine is not installed.
"""

from __future__ import annotations

import webbrowser

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QUrl

from ...core.logger import get_logger

log = get_logger("YouTubePlayer")

# Try importing WebEngine — may not be installed
_WEBENGINE_AVAILABLE = False
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    _WEBENGINE_AVAILABLE = True
except ImportError:
    pass


def has_webengine() -> bool:
    """Check if PyQt6-WebEngine is available."""
    return _WEBENGINE_AVAILABLE


_EMBED_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; }}
  body {{ background: #000; overflow: hidden; }}
  iframe {{ width: 100vw; height: 100vh; border: none; }}
</style>
</head>
<body>
<iframe
  src="https://www.youtube-nocookie.com/embed/{video_id}?autoplay=1&rel=0"
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
</iframe>
</body>
</html>"""


class YouTubePlayerWidget(QWidget):
    """Embeds a YouTube video using QWebEngineView, or falls back to system browser."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._video_id = None
        self._view = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if _WEBENGINE_AVAILABLE:
            profile = QWebEngineProfile("youtube_player", self)
            profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            page = QWebEnginePage(profile, self)
            self._view = QWebEngineView(self)
            self._view.setPage(page)
            layout.addWidget(self._view)
        else:
            # Fallback: show a message with a button to open in browser
            self._fallback_label = QLabel(
                "PyQt6-WebEngine is not installed.\n"
                "Click below to watch in your browser."
            )
            self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._fallback_label.setStyleSheet("color: #aaa; font-size: 13px; padding: 20px;")
            layout.addWidget(self._fallback_label)

            self._open_btn = QPushButton("Open in Browser")
            self._open_btn.setStyleSheet(
                "QPushButton { background: #60b0ff; color: white; border: none; "
                "border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
                "QPushButton:hover { background: #4a9eff; }"
            )
            self._open_btn.clicked.connect(self._open_in_browser)
            self._open_btn.setVisible(False)
            layout.addWidget(self._open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

            layout.addStretch()

    def load_video(self, video_id: str):
        """Load a YouTube video by its ID (e.g., 'dQw4w9WgXcQ')."""
        self._video_id = video_id
        if self._view:
            html = _EMBED_HTML.format(video_id=video_id)
            self._view.setHtml(html, QUrl("https://www.youtube-nocookie.com"))
        else:
            self._open_btn.setVisible(True)

    def stop(self):
        """Stop playback and clear the view."""
        self._video_id = None
        if self._view:
            self._view.setHtml("")

    def _open_in_browser(self):
        if self._video_id:
            url = f"https://www.youtube.com/watch?v={self._video_id}"
            webbrowser.open(url)
            log.info("Opened YouTube video in browser: %s", url)
