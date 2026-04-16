"""Reusable video player widget with controls bar, seek bar, volume.

QVideoWidget renders via a native GPU surface for smooth playback.
Controls sit below the video in a normal layout.
After the video ends the last frame is retained on screen.

Keyboard shortcuts (when the player widget has focus):
    Left/Right  — seek ±5 s
    ,  .        — step one frame backward/forward
    Space       — toggle play / pause
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
    QSizePolicy, QStyle,
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QGuiApplication

from ...core.logger import get_logger

log = get_logger("VideoPlayer")

SEEK_STEP_MS = 5000
DEFAULT_FRAME_MS = 33

# Lazy import — importing PyQt6.QtMultimedia eagerly causes the Qt FFmpeg
# backend to spin up ~16 native threads, one of which busy-loops at 100% CPU
# on some platforms.  Deferring the import to first use avoids burning a core
# for users who never open a video.
_MULTIMEDIA_CHECKED = False
_MULTIMEDIA_AVAILABLE = False
QMediaPlayer = None
QAudioOutput = None
QVideoWidget = None


def has_multimedia() -> bool:
    global _MULTIMEDIA_CHECKED, _MULTIMEDIA_AVAILABLE
    global QMediaPlayer, QAudioOutput, QVideoWidget
    if not _MULTIMEDIA_CHECKED:
        _MULTIMEDIA_CHECKED = True
        try:
            from PyQt6.QtMultimedia import (
                QMediaPlayer as _QMP, QAudioOutput as _QAO,
            )
            from PyQt6.QtMultimediaWidgets import QVideoWidget as _QVW
            QMediaPlayer = _QMP
            QAudioOutput = _QAO
            QVideoWidget = _QVW
            _MULTIMEDIA_AVAILABLE = True
        except ImportError:
            _MULTIMEDIA_AVAILABLE = False
    return _MULTIMEDIA_AVAILABLE


# ------------------------------------------------------------------
# Click-to-seek slider
# ------------------------------------------------------------------

class _ClickSeekSlider(QSlider):
    """QSlider that jumps to the clicked position instead of paging."""

    seek_to = pyqtSignal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                int(event.position().x()), self.width(),
            )
            self.setValue(val)
            self.seek_to.emit(val)
        super().mousePressEvent(event)


# ------------------------------------------------------------------
# Styles
# ------------------------------------------------------------------

_BAR_STYLE = "background: rgba(0, 0, 0, 180);"

_SLIDER_STYLE = (
    "QSlider {{ background: transparent; }}"
    "QSlider::groove:horizontal {{"
    "  background: rgba(100,100,120,200); height: 4px; border-radius: 2px;"
    "}}"
    "QSlider::handle:horizontal {{"
    "  background: {a}; width: 10px; height: 10px;"
    "  margin: -3px 0; border-radius: 5px;"
    "}}"
    "QSlider::sub-page:horizontal {{"
    "  background: {a}; border-radius: 2px;"
    "}}"
).format(a="#00ccff")

_BTN_STYLE = (
    "QPushButton {"
    "  background: rgba(40,40,55,200);"
    "  border: 1px solid rgba(80,80,100,180);"
    "  border-radius: 4px; padding: 2px;"
    "}"
    "QPushButton:hover {"
    "  background: rgba(60,60,80,220);"
    "  border-color: #00ccff;"
    "}"
)


# ------------------------------------------------------------------
# Main widget
# ------------------------------------------------------------------

class VideoPlayerWidget(QWidget):
    """Video player with GPU-rendered video and a persistent controls bar.

    Emits *video_resolution_changed(width, height)* when the native video
    dimensions become known so the parent can adjust aspect ratio.
    """

    video_resolution_changed = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None, *, icon_helper=None):
        super().__init__(parent)
        self._icon_helper = icon_helper
        self._video_widget: QVideoWidget | None = None
        self._seeking = False
        self._duration_ms = 0
        self._ended = False
        self._native_width = 0
        self._native_height = 0

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._mm = has_multimedia()
        self._build_ui()

        # Create the media pipeline once — reused across load() calls.
        if self._mm:
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(self._vol_slider.value() / 100.0)
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_output)
            self._player.setVideoOutput(self._video_widget)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.playbackStateChanged.connect(self._on_state_changed)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        else:
            self._audio_output = None
            self._player = None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if self._mm:
            self._video_widget = QVideoWidget()
            self._video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
            )
            self._video_widget.setFocusProxy(self)
            self._video_widget.installEventFilter(self)
            root.addWidget(self._video_widget, 1)
        else:
            ph = QLabel("Video playback not available\n(install PyQt6-Multimedia)")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet("color: #888; background: rgba(15,15,25,200);")
            root.addWidget(ph, 1)

        self._controls_bar = self._build_controls()
        root.addWidget(self._controls_bar)

    def _build_controls(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(_BAR_STYLE)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)

        self._seek_slider = _ClickSeekSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._seek_slider.setStyleSheet(_SLIDER_STYLE)
        lay.addWidget(self._seek_slider)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(24, 24)
        self._play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._play_btn.setStyleSheet(_BTN_STYLE)
        row.addWidget(self._play_btn)

        self._stop_btn = QPushButton()
        self._stop_btn.setFixedSize(24, 24)
        self._stop_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._stop_btn.setStyleSheet(_BTN_STYLE)
        row.addWidget(self._stop_btn)

        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet(
            "color: #e0e0e0; font-size: 11px; font-family: monospace;"
            " background: transparent;"
        )
        row.addWidget(self._time_label)
        row.addStretch()

        self._vol_label = QLabel()
        self._vol_label.setStyleSheet("background: transparent;")
        row.addWidget(self._vol_label)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(70)
        self._vol_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._vol_slider.setStyleSheet(_SLIDER_STYLE)
        row.addWidget(self._vol_slider)

        lay.addLayout(row)

        # Signals
        self._play_btn.clicked.connect(self._toggle_play_pause)
        self._stop_btn.clicked.connect(self._on_stop)
        self._seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._seek_slider.sliderMoved.connect(self._on_seek_moved)
        self._seek_slider.seek_to.connect(self._on_seek_clicked)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)

        # Icons
        self._update_play_icon(False)
        self._update_stop_icon()
        self._update_vol_icon()

        return bar

    # ------------------------------------------------------------------
    # Event filter — click on video toggles play/pause
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._video_widget and event.type() == QEvent.Type.MouseButtonPress:
            self._toggle_play_pause()
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._seek_relative(-SEEK_STEP_MS)
        elif key == Qt.Key.Key_Right:
            self._seek_relative(SEEK_STEP_MS)
        elif key == Qt.Key.Key_Comma:
            self._step_frame(-1)
        elif key == Qt.Key.Key_Period:
            self._step_frame(1)
        elif key == Qt.Key.Key_Space:
            self._toggle_play_pause()
        else:
            super().keyPressEvent(event)

    def _seek_relative(self, delta_ms: int):
        if not self._player:
            return
        pos = max(0, min(self._duration_ms, self._player.position() + delta_ms))
        self._player.setPosition(pos)
        if self._ended:
            self._ended = False
            self._player.play()

    def _step_frame(self, direction: int):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        frame_ms = self._frame_duration_ms()
        pos = max(0, min(self._duration_ms, self._player.position() + direction * frame_ms))
        self._player.setPosition(pos)
        if self._ended and direction == -1:
            self._ended = False

    def _frame_duration_ms(self) -> int:
        if self._player:
            fps = self._player.metaData().value(self._player.metaData().Key.VideoFrameRate)
            if fps and fps > 0:
                return max(1, int(1000 / fps))
        return DEFAULT_FRAME_MS

    # ------------------------------------------------------------------
    # Icons
    # ------------------------------------------------------------------

    def _update_play_icon(self, playing: bool):
        if self._icon_helper:
            from ..icons import PLAY, PAUSE
            self._play_btn.setIcon(self._icon_helper(PAUSE if playing else PLAY, 14))
        else:
            self._play_btn.setText("||" if playing else ">")

    def _update_stop_icon(self):
        if self._icon_helper:
            from ..icons import STOP_SQUARE
            self._stop_btn.setIcon(self._icon_helper(STOP_SQUARE, 14))
        else:
            self._stop_btn.setText("[]")

    def _update_vol_icon(self):
        if self._icon_helper:
            from ..icons import VOLUME
            self._vol_label.setPixmap(self._icon_helper(VOLUME, 14).pixmap(14, 14))
        else:
            self._vol_label.setText("Vol")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def native_size(self) -> tuple[int, int]:
        return self._native_width, self._native_height

    def controls_height(self) -> int:
        return self._controls_bar.sizeHint().height()

    def load(self, path: str) -> bool:
        if not self._player:
            return False
        self.stop()
        self._native_width = 0
        self._native_height = 0
        self._player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        return True

    def play(self):
        if not self._player:
            return
        if self._ended:
            self._ended = False
            self._player.setPosition(0)
        self._player.play()
        self.setFocus()

    def pause(self):
        if self._player:
            self._player.pause()

    def stop(self):
        if self._player:
            self._player.stop()
            self._player.setSource(QUrl())
        self._duration_ms = 0
        self._ended = False
        self._seek_slider.setValue(0)
        self._seek_slider.setRange(0, 0)
        self._time_label.setText("00:00 / 00:00")
        self._update_play_icon(False)

    def is_loaded(self) -> bool:
        return self._player is not None and not self._player.source().isEmpty()

    # ------------------------------------------------------------------
    # Seek bar
    # ------------------------------------------------------------------

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        self._seeking = False
        if self._player:
            self._player.setPosition(self._seek_slider.value())
            if self._ended:
                self._ended = False
                self._player.play()

    def _on_seek_moved(self, value: int):
        if self._player and self._seeking:
            self._time_label.setText(
                f"{self._fmt(value)} / {self._fmt(self._duration_ms)}"
            )

    def _on_seek_clicked(self, value: int):
        if self._player:
            self._player.setPosition(value)
            if self._ended:
                self._ended = False
                self._player.play()

    # ------------------------------------------------------------------
    # Player signals
    # ------------------------------------------------------------------

    def _on_duration_changed(self, ms: int):
        self._duration_ms = ms
        self._seek_slider.setRange(0, ms)

    def _on_position_changed(self, ms: int):
        if not self._seeking:
            self._seek_slider.setValue(ms)
        self._time_label.setText(
            f"{self._fmt(ms)} / {self._fmt(self._duration_ms)}"
        )

    def _on_state_changed(self, state):
        self._update_play_icon(
            state == QMediaPlayer.PlaybackState.PlayingState
        )

    def _on_media_status_changed(self, status):
        if not self._player:
            return
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._detect_resolution()
        elif status == QMediaPlayer.MediaStatus.BufferedMedia:
            if not self._native_width:
                self._detect_resolution()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._ended = True
            if self._duration_ms > 0:
                self._player.setPosition(self._duration_ms - 50)
                QTimer.singleShot(50, lambda: (
                    self._player.pause() if self._player else None
                ))
            self._update_play_icon(False)

    def _detect_resolution(self):
        if not self._player or self._native_width:
            return
        sink = self._video_widget.videoSink() if self._video_widget else None
        if sink:
            vs = sink.videoSize()
            if vs.width() > 0 and vs.height() > 0:
                self._native_width = vs.width()
                self._native_height = vs.height()
                self.video_resolution_changed.emit(vs.width(), vs.height())
                return
        res = self._player.metaData().value(self._player.metaData().Key.Resolution)
        if res and res.width() > 0 and res.height() > 0:
            self._native_width = res.width()
            self._native_height = res.height()
            self.video_resolution_changed.emit(res.width(), res.height())

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _toggle_play_pause(self):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def _on_stop(self):
        if self._player:
            self._player.stop()
            self._ended = False
            self._update_play_icon(False)

    def _on_volume_changed(self, value: int):
        if self._audio_output:
            self._audio_output.setVolume(value / 100.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(ms: int) -> str:
        total_s = max(0, ms // 1000)
        h, rem = divmod(total_s, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
