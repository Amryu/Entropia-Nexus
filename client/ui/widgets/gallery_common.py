"""Shared thumbnail loader and widget for gallery page and gallery overlay."""

import os
import sqlite3
import subprocess
import sys
import threading

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QMessageBox
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor

try:
    import cv2
except ImportError:
    cv2 = None

from ...core.logger import get_logger
from ..icons import svg_pixmap, UPLOAD, LINK, NOTES, GLOBE, STAR, IMAGE, CLIP, PLAY
from ..theme import (
    TEXT_MUTED, BORDER, SECONDARY, ACCENT,
    BADGE_HOF, BADGE_ATH, BADGE_GLOBAL, BADGE_NOTES,
    BADGE_UPLOADED, BADGE_UPLOAD_PENDING,
)

log = get_logger("Gallery")

# Default thumbnail dimensions (gallery page)
THUMB_WIDTH = 200
THUMB_HEIGHT = 130
THUMB_COLS = 4


# ------------------------------------------------------------------
# Thumbnail cache (SQLite)
# ------------------------------------------------------------------

class ThumbnailCache:
    """SQLite-backed thumbnail cache.

    Stores JPEG-compressed thumbnail bytes keyed by (path, mtime, width, height).
    Thread-safe: each thread gets its own connection via thread-local storage.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        # Create table using a temporary connection
        conn = self._get_conn()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS thumbnails ("
            "  path TEXT NOT NULL,"
            "  mtime REAL NOT NULL,"
            "  width INTEGER NOT NULL,"
            "  height INTEGER NOT NULL,"
            "  img_width INTEGER NOT NULL,"
            "  img_height INTEGER NOT NULL,"
            "  data BLOB NOT NULL,"
            "  PRIMARY KEY (path, width, height)"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thumbs_path ON thumbnails (path)"
        )
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def get(self, path: str, mtime: float,
            width: int, height: int) -> tuple[bytes, int, int] | None:
        """Return (jpeg_bytes, img_width, img_height) or None on miss."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data, img_width, img_height FROM thumbnails "
            "WHERE path = ? AND width = ? AND height = ? AND mtime = ?",
            (path, width, height, mtime),
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None

    def put(self, path: str, mtime: float,
            width: int, height: int,
            img_width: int, img_height: int,
            data: bytes) -> None:
        """Store a thumbnail."""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO thumbnails "
            "(path, mtime, width, height, img_width, img_height, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (path, mtime, width, height, img_width, img_height, data),
        )
        conn.commit()

    def prune(self, existing_paths: set[str]) -> None:
        """Remove entries for files that no longer exist."""
        conn = self._get_conn()
        all_paths = {r[0] for r in conn.execute(
            "SELECT DISTINCT path FROM thumbnails"
        ).fetchall()}
        stale = all_paths - existing_paths
        if stale:
            conn.executemany(
                "DELETE FROM thumbnails WHERE path = ?",
                [(p,) for p in stale],
            )
            conn.commit()


# Singleton cache instance (lazily initialized)
_thumb_cache: ThumbnailCache | None = None
_thumb_cache_lock = threading.Lock()


def get_thumbnail_cache() -> ThumbnailCache | None:
    """Return the global thumbnail cache, creating it if necessary."""
    global _thumb_cache
    if _thumb_cache is not None:
        return _thumb_cache
    with _thumb_cache_lock:
        if _thumb_cache is not None:
            return _thumb_cache
        try:
            db_dir = os.path.join(".", "data")
            os.makedirs(db_dir, exist_ok=True)
            _thumb_cache = ThumbnailCache(os.path.join(db_dir, "thumbs.db"))
        except Exception as e:
            log.warning("Failed to create thumbnail cache: %s", e)
        return _thumb_cache


# ------------------------------------------------------------------
# Thumbnail generation helpers
# ------------------------------------------------------------------

_MIN_CLIP_SIZE = 10_000  # clips under 10 KB are almost certainly truncated


def _read_video_frame(path: str):
    """Read first frame from a video, returning the image or None.

    cv2.VideoCapture.read() can hang indefinitely on truncated/corrupt
    files (especially when called from a QThread where it creates a
    spinning native FFmpeg thread).  Guard with size and metadata checks.
    """
    try:
        if os.path.getsize(path) < _MIN_CLIP_SIZE:
            return None
    except OSError:
        return None
    cap = cv2.VideoCapture(path)
    try:
        # Reject files where the decoder can't determine basic properties
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if w < 1 or h < 1:
            return None
        ret, frame = cap.read()
        return frame if ret else None
    finally:
        cap.release()


def _generate_thumbnail_bytes(
    path: str, file_type: str, tw: int, th: int,
) -> tuple[bytes, int, int] | None:
    """Generate a JPEG thumbnail and return (jpeg_bytes, width, height).

    Returns None if the source cannot be read.
    """
    if cv2 is None:
        return None

    source = None
    if file_type == "screenshot":
        source = cv2.imread(path)
    elif file_type == "clip":
        # Try cached .thumb.jpg sidecar first
        thumb_path = os.path.splitext(path)[0] + ".thumb.jpg"
        if os.path.isfile(thumb_path):
            source = cv2.imread(thumb_path)
        if source is None:
            source = _read_video_frame(path)
    if source is None:
        return None

    h, w = source.shape[:2]
    scale = min(tw / w, th / h)
    sw, sh = int(w * scale), int(h * scale)
    thumb = cv2.resize(source, (sw, sh), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None
    return (bytes(buf), sw, sh)


def _jpeg_to_qimage(data: bytes, width: int, height: int) -> QImage | None:
    """Convert JPEG bytes to a QImage."""
    qimg = QImage()
    if qimg.loadFromData(data, "JPEG"):
        return qimg
    return None


# ------------------------------------------------------------------
# Two-phase thumbnail loader
# ------------------------------------------------------------------

class ThumbnailLoader(QThread):
    """Background thread that scans directories and loads thumbnails.

    Phase 1: Scans directories, emits ``items_ready`` with file metadata
    (no thumbnails) so the UI can show placeholders immediately.

    Phase 2: Generates/loads thumbnails from the cache, emitting
    ``thumbnail_ready`` for each item so the UI updates progressively.

    The legacy ``loaded`` signal is still emitted at the end with all
    items (including qimages) for backwards compatibility.
    """

    items_ready = pyqtSignal(list)      # Phase 1: [{path, type, mtime, ...}]
    thumbnail_ready = pyqtSignal(str, object)  # Phase 2: (path, QImage)
    loaded = pyqtSignal(list)           # Legacy: all items with qimages

    def __init__(self, screenshot_dir: str, clip_dir: str, filter_type: str,
                 thumb_width: int = THUMB_WIDTH, thumb_height: int = THUMB_HEIGHT,
                 db=None):
        super().__init__()
        self._screenshot_dir = screenshot_dir
        self._clip_dir = clip_dir
        self._filter_type = filter_type
        self._thumb_width = thumb_width
        self._thumb_height = thumb_height
        self._db = db
        self._cancelled = False

    def cancel(self):
        """Request cancellation (checked between thumbnail generations)."""
        self._cancelled = True

    def run(self):
        # Phase 1: scan directories (fast — no image I/O)
        items = []
        if self._filter_type in ("all", "screenshots"):
            items.extend(self._scan_dir(self._screenshot_dir, "screenshot"))
        if self._filter_type in ("all", "clips"):
            items.extend(self._scan_dir(self._clip_dir, "clip"))
        items.sort(key=lambda x: x["mtime"], reverse=True)

        # Enrich with screenshot DB info
        if self._db and items:
            try:
                paths = [it["path"] for it in items]
                info_map = self._db.get_screenshot_info_batch(paths)
                for item in items:
                    item["screenshot_info"] = info_map.get(item["path"])
            except Exception:
                pass

        # Emit file list immediately (no thumbnails)
        self.items_ready.emit(items)

        if self._cancelled:
            return

        # Phase 2: serve cached thumbnails first, then generate misses.
        # Two passes ensure all previously-cached items appear immediately
        # even if the loader is cancelled during slow generation I/O.
        cache = get_thumbnail_cache()
        tw, th = self._thumb_width, self._thumb_height
        existing_paths = set()
        misses: list[dict] = []

        # Pass 1: serve cache hits (fast — SQLite lookups only)
        for item in items:
            if self._cancelled:
                break

            path = item["path"]
            existing_paths.add(path)

            if cache:
                cached = cache.get(path, item["mtime"], tw, th)
                if cached:
                    jpeg_bytes, iw, ih = cached
                    qimg = _jpeg_to_qimage(jpeg_bytes, iw, ih)
                    if qimg:
                        item["qimage"] = qimg
                        self.thumbnail_ready.emit(path, qimg)
                        continue

            misses.append(item)

        # Pass 2: generate thumbnails for cache misses (slow I/O)
        for item in misses:
            if self._cancelled:
                break

            path = item["path"]
            file_type = item["type"]
            try:
                result = _generate_thumbnail_bytes(path, file_type, tw, th)
                if result:
                    jpeg_bytes, sw, sh = result
                    if cache:
                        try:
                            cache.put(path, item["mtime"], tw, th,
                                      sw, sh, jpeg_bytes)
                        except Exception:
                            pass
                    qimg = _jpeg_to_qimage(jpeg_bytes, sw, sh)
                    if qimg:
                        item["qimage"] = qimg
                        self.thumbnail_ready.emit(path, qimg)
                        continue
                # Generation failed — mark pending for clips (might still be encoding)
                if file_type == "clip":
                    item["pending"] = True
            except Exception:
                if file_type == "clip":
                    item["pending"] = True

        # Prune stale cache entries (non-critical, skip on cancel)
        if cache and not self._cancelled and existing_paths:
            try:
                cache.prune(existing_paths)
            except Exception:
                pass

        # Legacy signal with all items
        if not self._cancelled:
            self.loaded.emit(items)

    def _scan_dir(self, base_dir: str, file_type: str) -> list[dict]:
        if not base_dir or not os.path.isdir(base_dir):
            return []
        items = []
        for root, dirs, files in os.walk(base_dir):
            for fname in files:
                if fname.startswith(".") or fname.endswith(".thumb.jpg"):
                    continue
                fpath = os.path.join(root, fname)
                ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
                if file_type == "screenshot" and ext in ("png", "jpg", "jpeg"):
                    items.append(self._make_item(fpath, "screenshot"))
                elif file_type == "clip" and ext in ("mp4", "mkv", "webm"):
                    items.append(self._make_item(fpath, "clip"))
        return items

    def _make_item(self, path: str, file_type: str) -> dict:
        """Create item dict with metadata only (no thumbnail yet)."""
        return {
            "path": path,
            "qimage": None,
            "type": file_type,
            "mtime": os.path.getmtime(path),
            "pending": False,
        }


def generate_clip_thumbnail(
    path: str,
    width: int = THUMB_WIDTH,
    height: int = THUMB_HEIGHT,
) -> QPixmap | None:
    """Try to generate a thumbnail from a video file. Returns None on failure."""
    if cv2 is None:
        return None
    try:
        # Try cached .thumb.jpg first
        thumb_path = os.path.splitext(path)[0] + ".thumb.jpg"
        source = None
        if os.path.isfile(thumb_path):
            source = cv2.imread(thumb_path)
        if source is None:
            source = _read_video_frame(path)
            if source is None:
                return None
        h, w = source.shape[:2]
        scale = min(width / w, height / h)
        sw, sh = int(w * scale), int(h * scale)
        thumb = cv2.resize(source, (sw, sh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, sw, sh, sw * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())
    except Exception:
        return None


_BADGE_ICON = 16        # icon size inside the badge
_BADGE_BG = 22          # dark circle diameter behind the icon
_BADGE_PAD = 4          # padding from thumbnail edges
_PLAY_SIZE = 36         # play button circle diameter
_PLAY_ICON = 22         # play triangle inside the circle
_BACKDROP = QColor(0, 0, 0, 160)


def _draw_badge(painter: QPainter, cx: int, cy: int,
                svg_data: str, color: str) -> None:
    """Draw an icon with a dark circular backdrop for contrast."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_BACKDROP)
    painter.drawEllipse(cx - _BADGE_BG // 2, cy - _BADGE_BG // 2,
                        _BADGE_BG, _BADGE_BG)
    pm = svg_pixmap(svg_data, color, _BADGE_ICON)
    painter.drawPixmap(cx - _BADGE_ICON // 2, cy - _BADGE_ICON // 2, pm)


class _BadgeLabel(QLabel):
    """QLabel that paints badge overlays on top of the thumbnail image."""

    def __init__(self, thumb: "ThumbnailWidget"):
        super().__init__()
        self._thumb = thumb

    def paintEvent(self, event):
        super().paintEvent(event)

        thumb = self._thumb
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        half = _BADGE_BG // 2

        # Bottom-left: file type indicator (image or clip icon)
        type_icon = IMAGE if thumb._type == "screenshot" else CLIP
        _draw_badge(painter,
                    _BADGE_PAD + half, h - _BADGE_PAD - half,
                    type_icon, "#ffffff")

        # Centered play button for video clips
        if thumb._type == "clip" and not thumb._pending:
            cx, cy = w // 2, h // 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_BACKDROP)
            painter.drawEllipse(
                cx - _PLAY_SIZE // 2, cy - _PLAY_SIZE // 2,
                _PLAY_SIZE, _PLAY_SIZE,
            )
            play_pm = svg_pixmap(PLAY, "#ffffff", _PLAY_ICON)
            # +1 right offset: play triangles look off-center without it
            painter.drawPixmap(
                cx - _PLAY_ICON // 2 + 1,
                cy - _PLAY_ICON // 2,
                play_pm,
            )

        # Top-right: upload status (always visible)
        info = thumb._screenshot_info
        tx = w - _BADGE_PAD - half
        ty = _BADGE_PAD + half
        if info and info.get("upload_status") == "uploaded":
            _draw_badge(painter, tx, ty, LINK, BADGE_UPLOADED)
        elif info and info.get("global_type"):
            _draw_badge(painter, tx, ty, UPLOAD, BADGE_UPLOAD_PENDING)
        else:
            _draw_badge(painter, tx, ty, UPLOAD, TEXT_MUTED)

        # DB-sourced badges (only if screenshot_info is available)
        if info:
            # Bottom-right: global type badge
            bx = w - _BADGE_PAD - half
            by = h - _BADGE_PAD - half
            if info.get("is_ath"):
                _draw_badge(painter, bx, by, STAR, BADGE_ATH)
            elif info.get("is_hof"):
                _draw_badge(painter, bx, by, STAR, BADGE_HOF)
            elif info.get("global_type"):
                _draw_badge(painter, bx, by, GLOBE, BADGE_GLOBAL)

            # Top-left: notes indicator
            if info.get("has_notes"):
                _draw_badge(painter, _BADGE_PAD + half, _BADGE_PAD + half,
                            NOTES, BADGE_NOTES)

        painter.end()


class ThumbnailWidget(QWidget):
    """A single thumbnail tile in the gallery grid."""

    clicked = pyqtSignal(str, str)  # (path, type)
    upload_clicked = pyqtSignal(str)  # path — emitted when upload badge is clicked

    def __init__(self, item: dict, thumb_width: int = THUMB_WIDTH,
                 thumb_height: int = THUMB_HEIGHT, parent=None):
        super().__init__(parent)
        self._path = item["path"]
        self._type = item["type"]
        self._screenshot_info = item.get("screenshot_info")
        self._thumb_width = thumb_width
        self._thumb_height = thumb_height
        self.setFixedSize(thumb_width + 8, thumb_height + 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(os.path.basename(self._path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Thumbnail image (with badge overlay painting)
        self._img_label = _BadgeLabel(self)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setFixedSize(thumb_width, thumb_height)
        self._img_label.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        self._pending = item.get("pending", False)
        self._no_preview_style = (
            self._img_label.styleSheet() + f" color: {TEXT_MUTED}; font-size: 11px;"
        )
        # Convert QImage → QPixmap on the main thread (thread-safe)
        qimg = item.get("qimage")
        if qimg is not None and not qimg.isNull():
            self._img_label.setPixmap(QPixmap.fromImage(qimg))
        elif self._pending:
            self._img_label.setText("Loading...")
            self._img_label.setStyleSheet(self._no_preview_style)
        else:
            self._img_label.setText("Loading...")
            self._img_label.setStyleSheet(self._no_preview_style)
        layout.addWidget(self._img_label)

        # Label: show "<value> PEDd - <mob>" for global-associated captures,
        # otherwise show the filename.
        info = self._screenshot_info
        if (info and info.get("global_type")
                and info.get("target_name")
                and info.get("value") is not None):
            name = f"{int(info['value'])} PED - {info['target_name']}"
        else:
            name = os.path.basename(self._path)
        max_chars = max(12, thumb_width // 7)
        if len(name) > max_chars:
            name = name[:max_chars - 3] + "..."
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        self.setStyleSheet(
            f"ThumbnailWidget {{ border-radius: 4px; }}"
            f"ThumbnailWidget:hover {{ background: {SECONDARY}; }}"
        )

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """Update the thumbnail image (e.g. after a pending clip finishes encoding)."""
        self._img_label.setText("")
        self._img_label.setPixmap(pixmap)
        self._img_label.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        self._pending = False

    def set_no_preview(self) -> None:
        """Switch from 'Loading...' to 'No Preview' after retries exhausted."""
        self._img_label.setText("No Preview")
        self._img_label.setStyleSheet(self._no_preview_style)
        self._pending = False

    def update_screenshot_info(self, info: dict | None):
        """Update badge info and repaint."""
        self._screenshot_info = info
        self._img_label.update()

    @property
    def _item(self) -> dict:
        return {"path": self._path, "type": self._type}

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Upload badge (top-right) is always clickable unless already uploaded
            info = self._screenshot_info
            already_uploaded = info and info.get("upload_status") == "uploaded"
            if not already_uploaded:
                img_x, img_y = 4, 4
                half = _BADGE_BG // 2
                bcx = img_x + self._thumb_width - _BADGE_PAD - half
                bcy = img_y + _BADGE_PAD + half
                pos = event.position()
                if abs(pos.x() - bcx) <= half and abs(pos.y() - bcy) <= half:
                    self.upload_clicked.emit(self._path)
                    return
            self.clicked.emit(self._path, self._type)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        open_action = menu.addAction("Open in Folder")
        notes_action = menu.addAction("Edit Notes")
        upload_action = None
        info = self._screenshot_info
        already_uploaded = info and info.get("upload_status") == "uploaded"
        if not already_uploaded:
            upload_action = menu.addAction("Upload to Nexus")
        delete_action = menu.addAction("Delete")
        action = menu.exec(event.globalPos())
        if action == open_action:
            self._open_in_folder()
        elif action == notes_action:
            self._edit_notes()
        elif upload_action and action == upload_action:
            self.upload_clicked.emit(self._path)
        elif action == delete_action:
            self._delete()

    def _open_in_folder(self):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self._path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self._path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(self._path)])

    def _edit_notes(self):
        """Open an inline notes editor dialog."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Notes")
        dialog.setMinimumWidth(300)
        lay = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setMaximumHeight(100)
        if self._screenshot_info and self._screenshot_info.get("has_notes"):
            # Fetch full notes from the parent's db if available
            from ...core.database import Database
            for w in self.window().findChildren(QWidget):
                db = getattr(w, "_db", None)
                if isinstance(db, Database):
                    rec = db.get_screenshot_by_path(self._path)
                    if rec and rec.get("notes"):
                        text_edit.setPlainText(rec["notes"])
                    break
        lay.addWidget(text_edit)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)

        def _save():
            notes = text_edit.toPlainText().strip()
            from ...core.database import Database
            for w in self.window().findChildren(QWidget):
                db = getattr(w, "_db", None)
                if isinstance(db, Database):
                    db.update_screenshot_notes_by_path(self._path, notes)
                    if self._screenshot_info:
                        self._screenshot_info["has_notes"] = bool(notes)
                    self.update()
                    break
            dialog.accept()

        save_btn.clicked.connect(_save)
        dialog.exec()

    def _delete(self):
        filename = os.path.basename(self._path)
        reply = QMessageBox.question(
            self, "Delete Capture",
            f"Are you sure you want to delete '{filename}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(self._path)
            # Also remove from local screenshot DB
            try:
                from ...core.database import Database
                for w in self.window().findChildren(QWidget):
                    db = getattr(w, "_db", None)
                    if isinstance(db, Database):
                        db.delete_screenshot_by_path(self._path)
                        break
            except Exception:
                pass
            self.hide()
            self.deleteLater()
        except OSError as e:
            log.error("Failed to delete %s: %s", self._path, e)


class _EncodingBadgeLabel(QLabel):
    """QLabel that paints a progress bar overlay on a thumbnail placeholder."""

    def __init__(self, parent: "EncodingThumbnailWidget"):
        super().__init__()
        self._thumb = parent

    def paintEvent(self, event):
        super().paintEvent(event)
        pct = self._thumb._progress
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Clip icon badge (bottom-left)
        half = _BADGE_BG // 2
        _draw_badge(painter, _BADGE_PAD + half, h - _BADGE_PAD - half,
                    CLIP, "#ffffff")

        # Progress bar (bottom, full width minus padding)
        bar_h = 4
        bar_y = h - bar_h - 2
        bar_x = 4
        bar_w = w - 8

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 2, 2)

        # Fill
        if pct > 0:
            fill_w = max(2, int(bar_w * pct / 100))
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)

        # Centered percentage text
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        text = f"{pct}%" if pct > 0 else "Encoding..."
        painter.drawText(0, 0, w, h - bar_h - 4,
                         Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


class EncodingThumbnailWidget(QWidget):
    """Placeholder thumbnail shown while a clip is being encoded."""

    def __init__(self, path: str, total_frames: int,
                 thumb_width: int = THUMB_WIDTH,
                 thumb_height: int = THUMB_HEIGHT, parent=None):
        super().__init__(parent)
        self._path = path
        self._total_frames = total_frames
        self._progress = 0  # 0-100
        self._thumb_width = thumb_width
        self._thumb_height = thumb_height
        self.setFixedSize(thumb_width + 8, thumb_height + 32)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._img_label = _EncodingBadgeLabel(self)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setFixedSize(thumb_width, thumb_height)
        self._img_label.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {ACCENT};"
            f" border-radius: 4px;"
        )
        layout.addWidget(self._img_label)

        name = os.path.basename(path)
        max_chars = max(12, thumb_width // 7)
        if len(name) > max_chars:
            name = name[:max_chars - 3] + "..."
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

    def set_progress(self, written: int, total: int) -> None:
        """Update the progress percentage."""
        if total > 0:
            self._progress = min(100, int(written * 100 / total))
        self._img_label.update()
