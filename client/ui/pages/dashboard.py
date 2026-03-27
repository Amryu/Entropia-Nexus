"""Dashboard page — latest news, global ticker, trade ticker."""

import re
import webbrowser
from collections import deque, OrderedDict
from datetime import datetime, timedelta, timezone
from html import escape as _esc
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QTextBrowser,
    QGroupBox, QFrame, QScrollArea, QApplication, QToolTip, QStackedWidget,
    QPushButton,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QRect, QPointF
from PyQt6.QtGui import QColor, QCursor, QFontMetrics, QPainter, QPixmap, QPolygonF, QTextCursor, QTextDocument
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..theme import (
    TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, BORDER, HOVER, SECONDARY, PRIMARY,
    WARNING, SUCCESS, MAIN_DARK, FONT_FAMILY,
)
from ..icons import svg_icon, SETTINGS, BELL
from ...chat_parser.models import GlobalEvent, GlobalType, TradeChatMessage


NEWS_REFRESH_INTERVAL_MS = 60 * 1000  # 1 minute
NEWS_LIMIT = 500
MAX_TICKER_LINES = 200
_TRIM_BUFFER = 30  # let ticker grow this far before bulk trim
_MAX_GLOBAL_FINGERPRINTS = 500
_GLOBAL_INGEST_BATCH_WINDOW_MS = 50
_GLOBAL_INGEST_MAX_AGE = timedelta(minutes=10)  # Ignore ingested globals older than this
_GLOBAL_PLAYER_WIDTH_RATIO = 0.27
_GLOBAL_TARGET_WIDTH_RATIO = 0.35
_GLOBAL_TEXT_WIDTH_FUDGE = 0.95
_GLOBAL_CELL_PAD_PX = 8


def _global_fingerprint(event: GlobalEvent) -> tuple:
    """Fingerprint for dedup between local, history, and ingested globals."""
    return (
        event.global_type.value,
        event.player_name.lower(),
        event.target_name.lower(),
        round(event.value, 2),
    )

# View indices inside the dashboard QStackedWidget
_VIEW_LIST = 0
_VIEW_ARTICLE = 1

# Global type → (short label, color)
_GLOBAL_TYPE_LABELS = {
    GlobalType.KILL:      ("Hunt",  TEXT),
    GlobalType.TEAM_KILL: ("Hunt",  TEXT),
    GlobalType.DEPOSIT:   ("Mine",  WARNING),
    GlobalType.CRAFT:     ("Craft", SUCCESS),
    GlobalType.RARE_ITEM: ("Rare",  ACCENT),
}

# Item type → URL path segment (mirrors getTypeLink in nexus/src/lib/util.js)
_TYPE_PATHS = {
    "Weapon": "items/weapons",
    "Armor": "items/armors",
    "ArmorSet": "items/armorsets",
    "Material": "items/materials",
    "Blueprint": "items/blueprints",
    "Vehicle": "items/vehicles",
    "Pet": "items/pets",
    "Clothing": "items/clothing",
    "MedicalTool": "items/medicaltools/tools",
    "MedicalChip": "items/medicaltools/chips",
    "Refiner": "items/tools/refiners",
    "Scanner": "items/tools/scanners",
    "Finder": "items/tools/finders",
    "Excavator": "items/tools/excavators",
    "TeleportationChip": "items/tools/teleportationchips",
    "EffectChip": "items/tools/effectchips",
    "MiscTool": "items/tools/misctools",
    "WeaponAmplifier": "items/attachments/weaponamplifiers",
    "WeaponVisionAttachment": "items/attachments/weaponvisionattachments",
    "Absorber": "items/attachments/absorbers",
    "ArmorPlating": "items/attachments/armorplatings",
    "FinderAmplifier": "items/attachments/finderamplifiers",
    "Enhancer": "items/attachments/enhancers",
    "MindforceImplant": "items/attachments/mindforceimplants",
    "Consumable": "items/consumables/stimulants",
    "Capsule": "items/consumables/capsules",
    "Furniture": "items/furnishings/furniture",
    "Decoration": "items/furnishings/decorations",
    "StorageContainer": "items/furnishings/storagecontainers",
    "Sign": "items/furnishings/signs",
}

# Regex for parsing bracketed tokens in trade chat
_BRACKET_RE = re.compile(r'\[([^\]]+)\]')
_WAYPOINT_RE = re.compile(r'^(.+),\s*(\d+),\s*(\d+),\s*(\d+),\s*Waypoint$')
# Gender tag at end of item name: (M), (F), (M,L), (F,L) etc.
_GENDER_TAG_RE = re.compile(r'\s*\(([MF])(?:,([^)]+))?\)\s*$')

_LINK_STYLE = f'color:{ACCENT};text-decoration:underline'


def _elide_px(text: str, max_px: int, fm: QFontMetrics) -> str:
    """Truncate *text* so it fits within *max_px* pixels, adding '…'."""
    if max_px <= 0:
        return ""
    return fm.elidedText(text, Qt.TextElideMode.ElideRight, max_px)

# CSS for article HTML rendering (QTextBrowser supports CSS 2.1 subset)
_ARTICLE_CSS = f"""
    body {{
        background-color: {PRIMARY};
        color: {TEXT};
        font-family: {FONT_FAMILY};
        font-size: 14px;
        margin: 0;
        padding: 0 12px;
    }}
    h1, h2, h3, h4 {{ color: {TEXT}; }}
    h2 {{ font-size: 18px; margin-top: 16px; margin-bottom: 6px; }}
    h3 {{ font-size: 16px; margin-top: 12px; margin-bottom: 6px; }}
    a {{ color: {ACCENT}; }}
    blockquote {{
        border-left: 3px solid {ACCENT};
        padding-left: 12px;
        margin-top: 10px;
        margin-bottom: 10px;
        color: {TEXT_MUTED};
        font-style: italic;
    }}
    code {{
        background-color: {MAIN_DARK};
        padding: 2px 6px;
    }}
    pre {{
        background-color: {MAIN_DARK};
        border: 1px solid {BORDER};
        padding: 12px;
    }}
    hr {{
        border: none;
        border-top: 1px solid {BORDER};
        margin-top: 16px;
        margin-bottom: 16px;
    }}
    table {{
        border-collapse: collapse;
        margin-top: 10px;
        margin-bottom: 10px;
    }}
    td, th {{
        border: 1px solid {BORDER};
        padding: 4px 8px;
    }}
    th {{
        background-color: {SECONDARY};
    }}
    img {{
        max-width: 100%;
    }}
"""


# Regex patterns for converting iframes to QTextBrowser-compatible HTML
_YT_IFRAME_WRAPPED_RE = re.compile(
    r'<div[^>]*class="video-embed-wrapper"[^>]*>\s*'
    r'<iframe[^>]*src="https?://(?:www\.)?youtube\.com/embed/([^"?\s]+)[^"]*"[^>]*>'
    r'\s*</iframe>\s*</div>',
    re.IGNORECASE | re.DOTALL,
)
_YT_IFRAME_BARE_RE = re.compile(
    r'<iframe[^>]*src="https?://(?:www\.)?youtube\.com/embed/([^"?\s]+)[^"]*"[^>]*>'
    r'\s*</iframe>',
    re.IGNORECASE | re.DOTALL,
)
_VIMEO_IFRAME_RE = re.compile(
    r'<iframe[^>]*src="https?://(?:player\.)?vimeo\.com/video/(\d+)[^"]*"[^>]*>'
    r'\s*</iframe>',
    re.IGNORECASE | re.DOTALL,
)
_RELATIVE_IMG_RE = re.compile(r'(<img[^>]*src=")(/[^"]+)(")', re.IGNORECASE)
_STANDALONE_IMG_RE = re.compile(r'(<img\s[^>]*>)', re.IGNORECASE)
_LEFTOVER_IFRAME_RE = re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL)
_EMPTY_VIDEO_DIV_RE = re.compile(
    r'<div[^>]*class="video-embed-wrapper"[^>]*>\s*</div>',
    re.IGNORECASE | re.DOTALL,
)


_YT_THUMB_MARKER = "img.youtube.com/vi/"


def _add_play_overlay(pixmap: QPixmap) -> QPixmap:
    """Composite a YouTube-style play button onto a video thumbnail."""
    # Create a fresh ARGB32 pixmap — downloaded images may use a format
    # that QPainter cannot composite onto (e.g. indexed-color JPEG decode).
    result = QPixmap(pixmap.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw original thumbnail
    painter.drawPixmap(0, 0, pixmap)

    cx = result.width() / 2.0
    cy = result.height() / 2.0
    radius = min(cx, cy) * 0.28

    # Semi-transparent dark circle
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 180))
    painter.drawEllipse(QPointF(cx, cy), radius, radius)

    # White play triangle
    painter.setBrush(QColor(255, 255, 255))
    half = radius * 0.45
    painter.drawPolygon(QPolygonF([
        QPointF(cx - half * 0.7, cy - half),
        QPointF(cx - half * 0.7, cy + half),
        QPointF(cx + half, cy),
    ]))

    painter.end()
    return result


def _yt_thumbnail_html(video_id: str, article_url: str | None) -> str:
    """Generate clickable YouTube thumbnail HTML."""
    thumb_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    if article_url:
        href = f"{article_url}?autoplay={video_id}"
    else:
        href = f"https://www.youtube.com/watch?v={video_id}"
    return f'<a href="{href}"><img src="{thumb_url}" width="480" style="border:none"/></a>'


def _prepare_html_for_textbrowser(html: str, base_url: str,
                                   article_id: int | None = None) -> str:
    """Transform article HTML for QTextBrowser rendering.

    - Converts YouTube iframes to clickable thumbnail images
    - Converts Vimeo iframes to text links
    - Makes relative image URLs absolute
    - Strips leftover iframes and empty wrapper divs
    """
    article_url = f"{base_url}/news/{article_id}" if article_id else None
    # YouTube iframes (wrapped in video-embed-wrapper div)
    html = _YT_IFRAME_WRAPPED_RE.sub(
        lambda m: _yt_thumbnail_html(m.group(1), article_url), html,
    )
    # Bare YouTube iframes (not wrapped)
    html = _YT_IFRAME_BARE_RE.sub(
        lambda m: _yt_thumbnail_html(m.group(1), article_url), html,
    )
    # Vimeo iframes → text link
    html = _VIMEO_IFRAME_RE.sub(
        lambda m: f'<a href="https://vimeo.com/{m.group(1)}">\u25b6 Watch on Vimeo</a>',
        html,
    )
    # Relative image URLs → absolute
    html = _RELATIVE_IMG_RE.sub(
        lambda m: f'{m.group(1)}{base_url}{m.group(2)}{m.group(3)}', html,
    )
    # Strip leftover iframes and empty video wrapper divs
    html = _LEFTOVER_IFRAME_RE.sub('', html)
    html = _EMPTY_VIDEO_DIV_RE.sub('', html)
    # Wrap standalone images in <div> so they render as block elements
    html = _STANDALONE_IMG_RE.sub(r'<div>\1</div>', html)
    return html


def _time_ago(iso_date: str) -> str:
    """Format an ISO date string as a relative time ago label."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        minutes = int(diff.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d, %Y")
    except Exception:
        return ""


def _format_date(iso_date: str) -> str:
    """Format an ISO date string as 'Month Day, Year'."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return ""


def _encode_slug(name: str) -> str:
    """Mirrors encodeURIComponentSafe from nexus/src/lib/util.js."""
    return quote(name.replace('~', '%7E'), safe='').replace('%20', '~')


def _strip_gender(name: str) -> str | None:
    """Strip gender tag from item name, preserving other tags.

    Returns the stripped name, or None if no gender tag was present.
    Examples:
        "Pixie Armor Plate (M)"    → "Pixie Armor Plate"
        "Pixie Armor Plate (M,L)"  → "Pixie Armor Plate (L)"
        "Pixie Armor Plate (L)"    → None  (no gender tag)
    """
    m = _GENDER_TAG_RE.search(name)
    if not m:
        return None
    base = name[:m.start()]
    other_tags = m.group(2)
    if other_tags:
        return f"{base} ({other_tags})"
    return base


def _resolve_item(name: str, item_lookup: dict) -> tuple[str, str] | None:
    """Look up item name in the lookup dict, trying gender-stripped variant first.

    Returns (canonical_name, type) or None.
    """
    stripped = _strip_gender(name)
    if stripped and stripped in item_lookup:
        return stripped, item_lookup[stripped]
    if name in item_lookup:
        return name, item_lookup[name]
    return None


def _format_trade_message(text: str, base_url: str,
                          item_lookup: dict) -> str:
    """Parse [brackets] in trade message, returning HTML with links."""
    parts = []
    last_end = 0

    for m in _BRACKET_RE.finditer(text):
        # Escaped plain text before this match
        if m.start() > last_end:
            parts.append(_esc(text[last_end:m.start()]))

        inner = m.group(1)
        wm = _WAYPOINT_RE.match(inner)

        if wm:
            # Waypoint — link copies coordinates on click
            display = _esc(m.group(0))
            href = f"wp:{_esc(inner)}"
            parts.append(
                f'<a href="{href}" style="{_LINK_STYLE}">{display}</a>'
            )
        else:
            # Item — resolve to wiki link
            resolved = _resolve_item(inner, item_lookup)
            if resolved:
                canon_name, item_type = resolved
                path = _TYPE_PATHS.get(item_type)
                if path:
                    href = f"{base_url}/{path}/{_encode_slug(canon_name)}"
                else:
                    href = f"{base_url}/search?q={quote(canon_name)}"
            else:
                href = f"{base_url}/search?q={quote(inner)}"
            display = _esc(m.group(0))
            parts.append(
                f'<a href="{href}" style="{_LINK_STYLE}">{display}</a>'
            )

        last_end = m.end()

    # Trailing plain text
    if last_end < len(text):
        parts.append(_esc(text[last_end:]))

    return ''.join(parts)


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

class _NewsFetcher(QThread):
    """Background thread to fetch news from the Nexus API."""
    finished = pyqtSignal(list)

    def __init__(self, nexus_client, limit=NEWS_LIMIT):
        super().__init__()
        self._client = nexus_client
        self._limit = limit

    def run(self):
        self.finished.emit(self._client.get_news(self._limit))


class _ArticleFetcher(QThread):
    """Background thread to fetch a single news article."""
    finished = pyqtSignal(object)  # dict | None

    def __init__(self, nexus_client, article_id: int):
        super().__init__()
        self._client = nexus_client
        self._article_id = article_id

    def run(self):
        self.finished.emit(self._client.get_news_article(self._article_id))


class _EventsFetcher(QThread):
    """Background thread to fetch events from the Nexus API."""
    finished = pyqtSignal(list)

    def __init__(self, nexus_client, limit=20):
        super().__init__()
        self._client = nexus_client
        self._limit = limit

    def run(self):
        self.finished.emit(self._client.get_events(self._limit))


class _ItemLookupLoader(QThread):
    """Background thread to build the item name→type dict."""
    finished = pyqtSignal(dict)

    def __init__(self, data_client):
        super().__init__()
        self._data_client = data_client

    def run(self):
        items = self._data_client.get_items()
        lookup = {}
        for item in items:
            name = item.get("Name")
            item_type = item.get("Type")
            if name and item_type:
                lookup[name] = item_type
        self.finished.emit(lookup)


_TICKER_HISTORY_MINUTES = 5


class _TickerHistoryLoader(QThread):
    """Fetch recent globals and trade messages to pre-populate tickers."""

    finished = pyqtSignal(dict)  # {"globals": [...], "trades": [...]}

    def __init__(self, nexus_client):
        super().__init__()
        self._client = nexus_client

    def run(self):
        since = (
            datetime.now(timezone.utc) - timedelta(minutes=_TICKER_HISTORY_MINUTES)
        ).isoformat()
        result: dict = {"globals": [], "trades": []}
        # Globals — public endpoint, always available
        try:
            data = self._client.get_globals(since=since, limit=200)
            if data and data.get("globals"):
                result["globals"] = data["globals"]
        except Exception:
            pass
        # Trades — requires auth
        if self._client.is_authenticated():
            try:
                data = self._client.get_ingested_trades(since=since, limit=200)
                if data and data.get("trades"):
                    result["trades"] = data["trades"]
            except Exception:
                pass
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class _NewsRow(QFrame):
    """Single compact clickable news row: [source] title ... date."""

    clicked = pyqtSignal(dict)  # emits the full post dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._post: dict | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            _NewsRow {{
                background-color: transparent;
                border-bottom: 1px solid {BORDER};
                padding: 0px;
            }}
            _NewsRow:hover {{
                background-color: {HOVER};
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)

        # Source badge
        self._source = QLabel()
        self._source.setFixedWidth(52)
        self._source.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._source)

        # Title
        self._title = QLabel()
        self._title.setStyleSheet(
            f"font-size: 12px; color: {TEXT}; background: transparent;"
        )
        row.addWidget(self._title, 1)

        # Date
        self._date = QLabel()
        self._date.setStyleSheet(
            f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;"
        )
        row.addWidget(self._date)

    def set_data(self, post: dict):
        self._post = post
        self._title.setText(post.get("title", ""))
        date = post.get("date", "")
        self._date.setText(_time_ago(date) if date else "")

        source = post.get("source", "nexus")
        if source == "steam":
            self._source.setText("EU News")
            self._source.setStyleSheet(
                "font-size: 10px; font-weight: bold; padding: 1px 4px;"
                "border-radius: 3px; background: #1b2838; color: #66c0f4;"
            )
        else:
            self._source.setText("Nexus")
            self._source.setStyleSheet(
                "font-size: 10px; font-weight: bold; padding: 1px 4px;"
                "border-radius: 3px; background: #000; color: #fff;"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._post:
            self.clicked.emit(self._post)
        super().mousePressEvent(event)


def _is_event_active(ev: dict) -> bool:
    """Return True if the event is currently live."""
    now = datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(ev["start_date"].replace("Z", "+00:00"))
    except Exception:
        return False
    if start > now:
        return False
    end_str = ev.get("end_date")
    if end_str:
        try:
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            return end > now
        except Exception:
            pass
    # No end date — active for 24h after start
    return (now - start).total_seconds() < 86400


def _event_status_text(ev: dict) -> tuple[str, str]:
    """Return (label, color) for the event status."""
    now = datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(ev["start_date"].replace("Z", "+00:00"))
    except Exception:
        return ("", TEXT_MUTED)
    if _is_event_active(ev):
        return ("Live", SUCCESS)
    if start > now:
        diff = start - now
        days = diff.days
        hours = int(diff.total_seconds() // 3600)
        if hours < 1:
            mins = max(1, int(diff.total_seconds() // 60))
            label = f"in {mins}m"
        elif hours < 24:
            label = f"in {hours}h"
        elif days < 7:
            label = f"in {days}d"
        else:
            label = start.strftime("%b %d")
        return (label, TEXT_MUTED)
    return ("Ended", TEXT_MUTED)


class _EventRow(QFrame):
    """Single compact clickable event row: [date] [type] title ... status."""

    clicked = pyqtSignal(dict)  # emits the full event dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event: dict | None = None
        self.setStyleSheet(f"""
            _EventRow {{
                background-color: transparent;
                border-bottom: 1px solid {BORDER};
                padding: 0px;
            }}
            _EventRow:hover {{
                background-color: {HOVER};
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)

        # Date block (compact: "MAR 27")
        self._date_label = QLabel()
        self._date_label.setFixedWidth(52)
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_label.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {TEXT_MUTED};"
            " background: transparent;"
        )
        row.addWidget(self._date_label)

        # Type badge
        self._type_badge = QLabel()
        self._type_badge.setFixedWidth(52)
        self._type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._type_badge)

        # Title + location
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(0)
        self._title = QLabel()
        self._title.setStyleSheet(
            f"font-size: 12px; color: {TEXT}; background: transparent;"
        )
        info.addWidget(self._title)
        self._location = QLabel()
        self._location.setStyleSheet(
            f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;"
        )
        info.addWidget(self._location)
        row.addLayout(info, 1)

        # Status label (Live / in Xh / Ended)
        self._status = QLabel()
        self._status.setStyleSheet(
            f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;"
        )
        row.addWidget(self._status)

    def set_data(self, ev: dict):
        self._event = ev
        if ev.get("link"):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # Date block
        try:
            dt = datetime.fromisoformat(ev["start_date"].replace("Z", "+00:00"))
            self._date_label.setText(dt.strftime("%b\n%d").upper())
        except Exception:
            self._date_label.setText("")

        # Type badge
        if ev.get("type") == "official":
            self._type_badge.setText("Official")
            self._type_badge.setStyleSheet(
                "font-size: 10px; font-weight: bold; padding: 1px 4px;"
                f"border-radius: 3px; background: {ACCENT}; color: #fff;"
            )
        else:
            self._type_badge.setText("Player")
            self._type_badge.setStyleSheet(
                "font-size: 10px; font-weight: bold; padding: 1px 4px;"
                "border-radius: 3px; background: #000; color: #fff;"
            )

        self._title.setText(ev.get("title", ""))

        # Location + time
        parts = []
        try:
            dt = datetime.fromisoformat(ev["start_date"].replace("Z", "+00:00"))
            parts.append(dt.strftime("%H:%M UTC"))
        except Exception:
            pass
        loc = ev.get("location")
        if loc:
            parts.append(loc)
        self._location.setText(" \u2022 ".join(parts))
        self._location.setVisible(bool(parts))

        # Status
        label, color = _event_status_text(ev)
        self._status.setText(label)
        style = f"font-size: 11px; background: transparent; color: {color};"
        if label == "Live":
            style += " font-weight: bold;"
        self._status.setStyleSheet(style)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._event:
            self.clicked.emit(self._event)
        super().mousePressEvent(event)


class _ArticleBrowser(QTextBrowser):
    """QTextBrowser that loads HTTP images asynchronously and opens links externally."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._image_cache: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._current_html = ""
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)

    def setArticleHtml(self, html: str):
        """Set article HTML, resetting pending image state."""
        self._pending.clear()
        self._current_html = html
        self.setHtml(html)

    def loadResource(self, type_: int, url: QUrl):
        if type_ == QTextDocument.ResourceType.ImageResource:
            url_str = url.toString()
            if url_str in self._image_cache:
                return self._image_cache[url_str]
            if url.scheme() in ("http", "https") and url_str not in self._pending:
                self._pending.add(url_str)
                reply = self._nam.get(QNetworkRequest(url))
                reply.finished.connect(lambda r=reply, u=url: self._on_image_loaded(r, u))
                return QPixmap()
        return super().loadResource(type_, url)

    def _on_image_loaded(self, reply: QNetworkReply, url: QUrl):
        url_str = url.toString()
        self._pending.discard(url_str)
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                if _YT_THUMB_MARKER in url_str:
                    pixmap = _add_play_overlay(pixmap)
                self._image_cache[url_str] = pixmap
                self.document().addResource(
                    QTextDocument.ResourceType.ImageResource, url, pixmap,
                )
            else:
                self._image_cache[url_str] = QPixmap()
        else:
            self._image_cache[url_str] = QPixmap()
        reply.deleteLater()
        # Re-render once all pending images have loaded
        if not self._pending and self._current_html:
            scroll_pos = self.verticalScrollBar().value()
            self.setHtml(self._current_html)
            self.verticalScrollBar().setValue(scroll_pos)


class _ArticleView(QWidget):
    """Full-page article detail view with back button."""

    back_clicked = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # Back button
        back_btn = QPushButton("\u2190  Back to News")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {TEXT_MUTED};
                font-size: 12px;
                padding: 4px 0;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {ACCENT};
            }}
        """)
        back_btn.setFixedWidth(140)
        back_btn.clicked.connect(self.back_clicked.emit)
        layout.addWidget(back_btn)

        # Title
        self._title = QLabel()
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {TEXT};"
            "background: transparent; padding: 8px 0 4px 0;"
        )
        layout.addWidget(self._title)

        # Meta row: source badge + author + date
        self._meta = QLabel()
        self._meta.setStyleSheet(
            f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;"
            "padding: 0 0 8px 0;"
        )
        layout.addWidget(self._meta)

        # Content browser (lightweight QTextBrowser with async image loading)
        content_wrapper = QFrame()
        content_wrapper.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        wrapper_layout = QVBoxLayout(content_wrapper)
        wrapper_layout.setContentsMargins(1, 1, 1, 1)

        self._content = _ArticleBrowser()
        self._content.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {PRIMARY};
                color: {TEXT};
                border: none;
            }}
        """)
        self._content.anchorClicked.connect(self._on_link_clicked)
        wrapper_layout.addWidget(self._content)

        layout.addWidget(content_wrapper, 1)

        # External link button
        self._ext_link_btn = QPushButton()
        self._ext_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ext_link_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {ACCENT};
                font-size: 12px;
                padding: 6px 0;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {ACCENT_HOVER};
            }}
        """)
        self._ext_link_btn.hide()
        self._ext_link_btn.clicked.connect(self._open_external)
        layout.addWidget(self._ext_link_btn)

        self._external_url = ""

    def show_article(self, article: dict, list_post: dict):
        """Populate the view with article data."""
        self._title.setText(article.get("title", list_post.get("title", "")))

        # Meta
        source = article.get("source", list_post.get("source", "nexus"))
        source_label = "EU News" if source == "steam" else "Nexus"
        author = article.get("author_name") or article.get("global_name", "")
        date = _format_date(
            article.get("created_at", list_post.get("date", ""))
        )
        meta_parts = [source_label]
        if author:
            meta_parts.append(f"By {author}")
        if date:
            meta_parts.append(date)
        self._meta.setText("  \u00b7  ".join(meta_parts))

        # Content
        base_url = self._config.nexus_base_url if self._config else "https://www.entropianexus.com"
        content_html = article.get("content_html", "")
        if content_html:
            body = _prepare_html_for_textbrowser(
                content_html, base_url, article_id=article.get("id"),
            )
        else:
            body = f"<p>{_esc(article.get('summary', list_post.get('summary', '')))}</p>"
        html = f"<html><head><style>{_ARTICLE_CSS}</style></head><body>{body}</body></html>"
        self._content.setArticleHtml(html)

        # External link
        link = article.get("link", "")
        url = list_post.get("url", "")
        if link:
            self._external_url = link
            label = "View on Steam \u2192" if source == "steam" else "View original source \u2192"
            self._ext_link_btn.setText(label)
            self._ext_link_btn.show()
        elif url and url.startswith("http"):
            self._external_url = url
            self._ext_link_btn.setText("View in browser \u2192")
            self._ext_link_btn.show()
        else:
            self._ext_link_btn.hide()
            self._external_url = ""

    def show_summary_only(self, post: dict):
        """Show a post that has no fetchable content (external link only)."""
        self._title.setText(post.get("title", ""))

        source = post.get("source", "nexus")
        source_label = "EU News" if source == "steam" else "Nexus"
        date = _format_date(post.get("date", ""))
        meta_parts = [source_label]
        if date:
            meta_parts.append(date)
        self._meta.setText("  \u00b7  ".join(meta_parts))

        summary = _esc(post.get("summary", ""))
        html = f"<html><head><style>{_ARTICLE_CSS}</style></head><body><p>{summary}</p></body></html>"
        self._content.setArticleHtml(html)

        url = post.get("url", "")
        if url:
            full_url = url
            if url.startswith("/"):
                full_url = (self._config.nexus_base_url if self._config else "") + url
            self._external_url = full_url
            label = "View on Steam \u2192" if source == "steam" else "View in browser \u2192"
            self._ext_link_btn.setText(label)
            self._ext_link_btn.show()
        else:
            self._ext_link_btn.hide()
            self._external_url = ""

    def show_loading(self):
        """Show loading state while article is being fetched."""
        self._title.setText("")
        self._meta.setText("")
        html = f'<html><head><style>{_ARTICLE_CSS}</style></head>'
        html += f'<body><p style="color:{TEXT_MUTED}">Loading article...</p></body></html>'
        self._content.setArticleHtml(html)
        self._ext_link_btn.hide()

    def _open_external(self):
        if self._external_url:
            webbrowser.open(self._external_url)

    def _on_link_clicked(self, url: QUrl):
        """Open all article links in the system browser."""
        webbrowser.open(url.toString())


# ---------------------------------------------------------------------------
# Main dashboard page
# ---------------------------------------------------------------------------

class DashboardPage(QWidget):
    """Dashboard showing latest news, global events ticker, and trade chat ticker."""

    # Emitted when the user navigates into/out of an article view.
    # sub_state: "article" when viewing an article, None when on the list.
    navigation_changed = pyqtSignal(object)  # str | None
    open_settings = pyqtSignal()
    open_notifications = pyqtSignal()

    def __init__(self, *, signals, db, nexus_client, data_client, config):
        super().__init__()
        self._signals = signals
        self._db = db
        self._nexus_client = nexus_client
        self._data_client = data_client
        self._config = config
        self._live = False
        self._global_lines = 0
        self._global_events: deque[GlobalEvent] = deque(maxlen=MAX_TICKER_LINES)
        self._global_fingerprints: OrderedDict[tuple, None] = OrderedDict()
        self._trade_lines = 0
        self._trade_html: deque[str] = deque(maxlen=MAX_TICKER_LINES)
        self._fetcher = None
        self._events_fetcher = None
        self._article_fetcher = None
        self._item_lookup: dict[str, str] = {}
        self._item_loader = None
        self._seen_ids: set[int] | None = None  # None = first load not done yet
        self._seen_event_fingerprints: set[tuple] | None = None
        self._pending_post: dict | None = None  # post being loaded
        self._pending_ingested_globals: deque[GlobalEvent] = deque()
        self._active_feed = "news"  # "news" or "events"

        # Root layout with stacked widget for list/article views
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # --- View 0: News list + tickers ---
        list_view = QWidget()
        layout = QVBoxLayout(list_view)

        # Feed section — News / Events toggle
        feed_box = QGroupBox()
        feed_box.setTitle("")  # no title text — tabs replace it
        feed_layout = QVBoxLayout(feed_box)
        feed_layout.setContentsMargins(4, 0, 4, 4)
        feed_layout.setSpacing(0)

        # Toggle header row
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 4)
        toggle_row.setSpacing(4)

        self._news_tab = QPushButton("News")
        self._events_tab = QPushButton("Events")
        for btn in (self._news_tab, self._events_tab):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
        self._news_tab.clicked.connect(lambda: self._switch_feed("news"))
        self._events_tab.clicked.connect(lambda: self._switch_feed("events"))
        toggle_row.addWidget(self._news_tab, 1)
        toggle_row.addWidget(self._events_tab, 1)
        feed_layout.addLayout(toggle_row)

        # Stacked feed content
        self._feed_stack = QStackedWidget()

        # --- News feed (index 0) ---
        news_scroll = QScrollArea()
        news_scroll.setWidgetResizable(True)
        news_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        news_scroll.setStyleSheet("QScrollArea { border: none; }")

        self._news_container = QWidget()
        self._news_layout = QVBoxLayout(self._news_container)
        self._news_layout.setContentsMargins(0, 0, 0, 0)
        self._news_layout.setSpacing(0)
        self._news_layout.addStretch()

        news_scroll.setWidget(self._news_container)

        self._news_rows: list[_NewsRow] = []
        self._posts_empty = QLabel("Loading...")
        self._posts_empty.setObjectName("mutedText")
        self._posts_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._news_layout.insertWidget(0, self._posts_empty)

        self._feed_stack.addWidget(news_scroll)  # index 0

        # --- Events feed (index 1) ---
        events_scroll = QScrollArea()
        events_scroll.setWidgetResizable(True)
        events_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        events_scroll.setStyleSheet("QScrollArea { border: none; }")

        self._events_container = QWidget()
        self._events_layout = QVBoxLayout(self._events_container)
        self._events_layout.setContentsMargins(0, 0, 0, 0)
        self._events_layout.setSpacing(0)
        self._events_layout.addStretch()

        events_scroll.setWidget(self._events_container)

        self._event_rows: list[_EventRow] = []
        self._events_empty = QLabel("Loading...")
        self._events_empty.setObjectName("mutedText")
        self._events_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._events_layout.insertWidget(0, self._events_empty)

        self._feed_stack.addWidget(events_scroll)  # index 1

        feed_layout.addWidget(self._feed_stack)
        self._update_feed_tabs()

        layout.addWidget(feed_box, 3)

        # Tickers (globals + trade)
        ticker_row = QWidget()
        ticker_layout = QHBoxLayout(ticker_row)
        ticker_layout.setContentsMargins(0, 0, 0, 0)
        ticker_layout.setSpacing(4)

        # Global ticker
        global_box = QWidget()
        global_layout = QVBoxLayout(global_box)
        global_layout.setContentsMargins(0, 0, 0, 0)
        global_layout.setSpacing(2)
        global_layout.addLayout(self._build_ticker_header("Globals"))
        self._global_log = QTextEdit()
        self._global_log.setReadOnly(True)
        self._global_log.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        global_layout.addWidget(self._global_log)
        ticker_layout.addWidget(global_box, 1)

        # Trade ticker
        trade_box = QWidget()
        trade_layout = QVBoxLayout(trade_box)
        trade_layout.setContentsMargins(0, 0, 0, 0)
        trade_layout.setSpacing(2)
        trade_layout.addLayout(self._build_ticker_header("Trade"))
        self._trade_log = QTextBrowser()
        self._trade_log.setOpenLinks(False)
        self._trade_log.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._trade_log.anchorClicked.connect(self._on_trade_link)
        trade_layout.addWidget(self._trade_log)
        ticker_layout.addWidget(trade_box, 1)

        layout.addWidget(ticker_row, 2)

        self._stack.addWidget(list_view)  # index 0

        # --- View 1: Article detail ---
        self._article_view = _ArticleView(config)
        self._article_view.back_clicked.connect(self._show_list_view)
        self._stack.addWidget(self._article_view)  # index 1

        # Connect signals
        signals.catchup_complete.connect(self._on_catchup_complete)
        signals.global_event.connect(self._on_global)
        signals.ingested_global.connect(self._on_ingested_global)
        signals.trade_chat.connect(self._on_trade_chat)
        signals.config_changed.connect(lambda _cfg: self._rebuild_globals())

        # News + events refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._fetch_news)
        self._refresh_timer.timeout.connect(self._fetch_events)
        self._refresh_timer.start(NEWS_REFRESH_INTERVAL_MS)

        # Initial fetches
        self._fetch_news()
        self._fetch_events()
        self._load_item_lookup()
        self._ticker_loader = None
        self._load_ticker_history()

        # Debounce timer for re-rendering globals on resize
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(100)
        self._resize_timer.timeout.connect(self._rebuild_globals)

        # Coalesce short ingested-global bursts to avoid main-thread stalls.
        self._ingested_flush_timer = QTimer(self)
        self._ingested_flush_timer.setSingleShot(True)
        self._ingested_flush_timer.setInterval(_GLOBAL_INGEST_BATCH_WINDOW_MS)
        self._ingested_flush_timer.timeout.connect(self._flush_ingested_globals)

    # --- Ticker header ---

    _TICKER_BTN_STYLE = (
        "QPushButton { background: transparent; border: none; padding: 0; }"
        f"QPushButton:hover {{ background: {HOVER}; border-radius: 3px; }}"
    )

    def _build_ticker_header(self, title: str) -> QHBoxLayout:
        """Build a header row with title label + settings/notification buttons."""
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(2)

        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-weight: bold; color: {TEXT};")
        row.addWidget(lbl)
        row.addStretch()

        gear_btn = QPushButton()
        gear_btn.setFixedSize(20, 20)
        gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gear_btn.setIcon(svg_icon(SETTINGS, TEXT_MUTED, 14))
        gear_btn.setStyleSheet(self._TICKER_BTN_STYLE)
        gear_btn.setToolTip("Dashboard settings")
        gear_btn.clicked.connect(self.open_settings.emit)
        row.addWidget(gear_btn)

        bell_btn = QPushButton()
        bell_btn.setFixedSize(20, 20)
        bell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bell_btn.setIcon(svg_icon(BELL, TEXT_MUTED, 14))
        bell_btn.setStyleSheet(self._TICKER_BTN_STYLE)
        bell_btn.setToolTip("Notification settings")
        bell_btn.clicked.connect(self.open_notifications.emit)
        row.addWidget(bell_btn)

        return row

    # --- View switching ---

    def _show_list_view(self):
        self._stack.setCurrentIndex(_VIEW_LIST)
        self.navigation_changed.emit(None)

    def _show_article_view(self):
        self._stack.setCurrentIndex(_VIEW_ARTICLE)
        self.navigation_changed.emit("article")

    def set_sub_state(self, state):
        """Restore view from navigation history."""
        if state == "article":
            self._stack.setCurrentIndex(_VIEW_ARTICLE)
        else:
            self._stack.setCurrentIndex(_VIEW_LIST)

    # --- Item lookup ---

    def _load_item_lookup(self):
        if self._item_loader and self._item_loader.isRunning():
            return
        self._item_loader = _ItemLookupLoader(self._data_client)
        self._item_loader.finished.connect(self._on_item_lookup_loaded)
        self._item_loader.start()

    def _on_item_lookup_loaded(self, lookup: dict):
        self._item_lookup = lookup

    # --- News ---

    def showEvent(self, event):
        """Refresh feeds immediately when the tab becomes visible."""
        super().showEvent(event)
        self._fetch_news()
        self._fetch_events()

    def _fetch_news(self):
        if self._fetcher and self._fetcher.isRunning():
            return
        self._fetcher = _NewsFetcher(self._nexus_client)
        self._fetcher.finished.connect(self._on_news_loaded)
        self._fetcher.start()

    def _fetch_events(self):
        if self._events_fetcher and self._events_fetcher.isRunning():
            return
        self._events_fetcher = _EventsFetcher(self._nexus_client)
        self._events_fetcher.finished.connect(self._on_events_loaded)
        self._events_fetcher.start()

    def _on_news_loaded(self, posts: list):
        # --- Notification for new posts ---
        current_ids = {p.get("id") for p in posts if p.get("id") is not None}
        if self._seen_ids is None:
            # First load — seed the set, don't notify
            self._seen_ids = current_ids
        else:
            new_ids = current_ids - self._seen_ids
            self._seen_ids = current_ids
            if new_ids and self._active_feed != "news":
                self._news_tab.setProperty("highlight", True)
                self._update_feed_tabs()
            # Notify for genuinely new posts (most recent first in list)
            for post in posts:
                pid = post.get("id")
                if pid in new_ids:
                    self._signals.new_news_post.emit(
                        post.get("title", "News"),
                        post.get("summary", ""),
                    )

        # --- Update news rows ---

        # Grow the row pool as needed
        while len(self._news_rows) < len(posts):
            row = _NewsRow()
            row.clicked.connect(self._on_news_row_clicked)
            idx = len(self._news_rows)
            self._news_layout.insertWidget(idx, row)
            self._news_rows.append(row)

        for i, row in enumerate(self._news_rows):
            if i < len(posts):
                row.set_data(posts[i])
                row.show()
            else:
                row.hide()

        if len(posts) == 0:
            self._posts_empty.setText("No posts available")
        self._posts_empty.setVisible(len(posts) == 0)

    # --- Article navigation ---

    def _on_news_row_clicked(self, post: dict):
        """User clicked a news row — fetch full article and show detail view."""
        article_id = post.get("id")
        has_content = post.get("has_content", False)

        if article_id and has_content:
            # Fetch full article — defer view switch to _on_article_loaded.
            self._pending_post = post
            self.setCursor(Qt.CursorShape.WaitCursor)
            self._fetch_article(article_id)
        elif article_id:
            # No content — show summary in detail view
            self._article_view.show_summary_only(post)
            self._show_article_view()
        else:
            # Fallback: open URL in browser
            url = post.get("url", "")
            if url:
                base = self._config.nexus_base_url
                if url.startswith("/"):
                    url = base + url
                webbrowser.open(url)

    def _fetch_article(self, article_id: int):
        if self._article_fetcher and self._article_fetcher.isRunning():
            self._article_fetcher.quit()
            self._article_fetcher.wait(1000)
        self._article_fetcher = _ArticleFetcher(self._nexus_client, article_id)
        self._article_fetcher.finished.connect(self._on_article_loaded)
        self._article_fetcher.start()

    def _on_article_loaded(self, article: dict | None):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        post = self._pending_post or {}
        if article:
            self._article_view.show_article(article, post)
        else:
            # Fetch failed — show summary fallback
            self._article_view.show_summary_only(post)
        self._show_article_view()

    # --- Events ---

    def _on_events_loaded(self, events: list):
        """Handle fetched events list — update rows and notify for changes."""
        # Build fingerprints: (id, active_state) to detect new events and
        # state transitions (upcoming → live → ended).
        def _fp(ev):
            return (ev.get("id"), _is_event_active(ev))

        current_fps = {_fp(ev) for ev in events}

        if self._seen_event_fingerprints is None:
            self._seen_event_fingerprints = current_fps
        else:
            new_fps = current_fps - self._seen_event_fingerprints
            gone_fps = self._seen_event_fingerprints - current_fps
            self._seen_event_fingerprints = current_fps
            changed = new_fps | gone_fps
            if changed and self._active_feed != "events":
                self._events_tab.setProperty("highlight", True)
                self._update_feed_tabs()

            # Emit signal for genuinely new/changed events
            for ev in events:
                if _fp(ev) in new_fps:
                    detail = ""
                    if _is_event_active(ev):
                        detail = "Event is now live!"
                    else:
                        try:
                            dt = datetime.fromisoformat(
                                ev["start_date"].replace("Z", "+00:00"))
                            detail = dt.strftime("%b %d, %H:%M UTC")
                        except Exception:
                            pass
                    loc = ev.get("location")
                    if loc:
                        detail = f"{detail} \u2022 {loc}" if detail else loc
                    self._signals.new_event.emit(
                        ev.get("title", "Event"), detail)

        # Update event rows
        while len(self._event_rows) < len(events):
            row = _EventRow()
            row.clicked.connect(self._on_event_row_clicked)
            idx = len(self._event_rows)
            self._events_layout.insertWidget(idx, row)
            self._event_rows.append(row)

        for i, row in enumerate(self._event_rows):
            if i < len(events):
                row.set_data(events[i])
                row.show()
            else:
                row.hide()

        if len(events) == 0:
            self._events_empty.setText("No upcoming events")
        self._events_empty.setVisible(len(events) == 0)

    def _on_event_row_clicked(self, ev: dict):
        """Open event link in browser, if available."""
        link = ev.get("link")
        if link:
            webbrowser.open(link)

    # --- Feed toggle ---

    _TAB_STYLE_ACTIVE = (
        f"QPushButton {{ background: {ACCENT}; color: #fff; border: 1px solid {ACCENT};"
        f" font-weight: bold; font-size: 12px; padding: 4px 14px;"
        f" border-radius: 4px; }}"
    )
    _TAB_STYLE_INACTIVE = (
        f"QPushButton {{ background: transparent; color: {TEXT_MUTED};"
        f" border: 1px solid {BORDER};"
        f" font-size: 12px; padding: 4px 14px; border-radius: 4px; }}"
        f"QPushButton:hover {{ background: {HOVER}; }}"
    )
    _TAB_STYLE_HIGHLIGHT = (
        f"QPushButton {{ background: transparent; color: {ACCENT};"
        f" border: 1px solid {ACCENT};"
        f" font-weight: bold; font-size: 12px; padding: 4px 14px;"
        f" border-radius: 4px; }}"
        f"QPushButton:hover {{ background: {HOVER}; }}"
    )

    def _switch_feed(self, feed: str):
        """Switch between news and events feeds."""
        self._active_feed = feed
        if feed == "news":
            self._feed_stack.setCurrentIndex(0)
            self._news_tab.setProperty("highlight", False)
        else:
            self._feed_stack.setCurrentIndex(1)
            self._events_tab.setProperty("highlight", False)
        self._update_feed_tabs()

    def _update_feed_tabs(self):
        """Apply active/inactive/highlight styling to feed tabs."""
        if self._active_feed == "news":
            self._news_tab.setStyleSheet(self._TAB_STYLE_ACTIVE)
            if self._events_tab.property("highlight"):
                self._events_tab.setStyleSheet(self._TAB_STYLE_HIGHLIGHT)
            else:
                self._events_tab.setStyleSheet(self._TAB_STYLE_INACTIVE)
        else:
            self._events_tab.setStyleSheet(self._TAB_STYLE_ACTIVE)
            if self._news_tab.property("highlight"):
                self._news_tab.setStyleSheet(self._TAB_STYLE_HIGHLIGHT)
            else:
                self._news_tab.setStyleSheet(self._TAB_STYLE_INACTIVE)

    # --- Ticker helpers ---

    @staticmethod
    def _append_line(text_edit: QTextEdit, text: str) -> None:
        text_edit.setUpdatesEnabled(False)
        text_edit.append(text)
        text_edit.setUpdatesEnabled(True)

    def _on_catchup_complete(self, _data):
        self._live = True

    # --- Ticker history (pre-populate on startup) ---

    def _load_ticker_history(self):
        self._ticker_loader = _TickerHistoryLoader(self._nexus_client)
        self._ticker_loader.finished.connect(self._on_ticker_history)
        self._ticker_loader.start()

    def _on_ticker_history(self, data: dict):
        """Populate tickers with recent server data, oldest first."""
        added_globals = 0
        for g in sorted(data["globals"], key=lambda x: x.get("timestamp", "")):
            try:
                gt = GlobalType(g["type"])
            except ValueError:
                continue
            if self._on_global(GlobalEvent(
                timestamp=datetime.fromisoformat(g["timestamp"]),
                global_type=gt,
                player_name=g.get("player", ""),
                target_name=g.get("target", ""),
                value=float(g.get("value", 0)),
                value_unit=g.get("unit", "PED"),
                is_hof=bool(g.get("hof")),
                is_ath=bool(g.get("ath")),
            ), render=False):
                added_globals += 1

        if added_globals:
            self._rebuild_globals()

        for t in sorted(data["trades"], key=lambda x: x.get("timestamp", "")):
            self._render_trade(TradeChatMessage(
                timestamp=datetime.fromisoformat(t["timestamp"]),
                channel=t.get("channel", "Trade"),
                username=t.get("username", ""),
                message=t.get("message", ""),
            ))

    def _on_global(self, data: GlobalEvent, *, render: bool = True) -> bool:
        fp = _global_fingerprint(data)
        if fp in self._global_fingerprints:
            return False
        self._global_fingerprints[fp] = None
        if len(self._global_fingerprints) > _MAX_GLOBAL_FINGERPRINTS:
            self._global_fingerprints.popitem(last=False)
        self._global_events.append(data)
        if render:
            self._render_global(data)
        return True

    def _on_ingested_global(self, data: dict):
        """Convert server dict to GlobalEvent and display in ticker."""
        try:
            gt = GlobalType(data.get("type", ""))
        except ValueError:
            return
        event = GlobalEvent(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            global_type=gt,
            player_name=data.get("player", ""),
            target_name=data.get("target", ""),
            value=float(data.get("value", 0)),
            value_unit=data.get("unit", "PED"),
            location=data.get("location"),
            is_hof=bool(data.get("hof")),
            is_ath=bool(data.get("ath")),
        )
        # Skip historical globals that were recently ingested but happened long ago
        now = datetime.now(event.timestamp.tzinfo)
        if now - event.timestamp > _GLOBAL_INGEST_MAX_AGE:
            return
        self._pending_ingested_globals.append(event)
        if not self._ingested_flush_timer.isActive():
            self._ingested_flush_timer.start()

    def _flush_ingested_globals(self):
        """Flush queued ingested globals in a single render pass."""
        if not self._pending_ingested_globals:
            return
        pending = list(self._pending_ingested_globals)
        self._pending_ingested_globals.clear()

        if len(pending) == 1:
            self._on_global(pending[0], render=True)
            return

        added = 0
        for event in pending:
            if self._on_global(event, render=False):
                added += 1
        if added:
            self._rebuild_globals()

    def _should_show_global(self, data: GlobalEvent) -> bool:
        """Check dashboard config filters for globals."""
        min_val = getattr(self._config, "dashboard_globals_min_value", 0)
        if min_val > 0 and data.value < min_val:
            return False
        blocked = getattr(self._config, "dashboard_globals_blocked_types", [])
        if blocked and data.global_type.value in blocked:
            return False
        return True

    def _global_to_html(
        self,
        data: GlobalEvent,
        *,
        fm: QFontMetrics | None = None,
        player_px: int | None = None,
        target_px: int | None = None,
    ) -> str | None:
        """Return the HTML row for a single GlobalEvent, or None if filtered."""
        if not self._should_show_global(data):
            return None
        label, label_color = _GLOBAL_TYPE_LABELS.get(
            data.global_type, ("?", TEXT_MUTED)
        )
        badge = ""
        if data.is_ath:
            badge = f'<b style="color:{ACCENT}">ATH</b>'
        elif data.is_hof:
            badge = f'<b style="color:{ACCENT}">HoF</b>'
        _td = 'white-space:nowrap;padding:1px 4px'
        if fm is None or player_px is None or target_px is None:
            fm, player_px, target_px = self._global_text_metrics()
        player = _esc(_elide_px(data.player_name, player_px, fm))
        target = _esc(_elide_px(data.target_name, target_px, fm))
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0"'
            f' style="margin:0;table-layout:fixed">'
            f'<tr>'
            f'<td width="8%" style="{_td};color:{label_color}">{label}</td>'
            f'<td width="27%" style="{_td}">{player}</td>'
            f'<td width="35%" style="{_td};color:{TEXT_MUTED}">{target}</td>'
            f'<td width="22%" style="{_td}" align="right">'
            f'{data.value:.2f} {_esc(data.value_unit)}</td>'
            f'<td width="8%" style="{_td}" align="right">{badge}</td>'
            f'</tr></table>'
        )

    def _global_text_metrics(self) -> tuple[QFontMetrics, int, int]:
        """Build shared text metrics for global ticker row rendering."""
        fm = QFontMetrics(self._global_log.document().defaultFont())
        vw = max(0, self._global_log.viewport().width())
        player_px = max(
            12,
            int(vw * _GLOBAL_PLAYER_WIDTH_RATIO * _GLOBAL_TEXT_WIDTH_FUDGE)
            - _GLOBAL_CELL_PAD_PX,
        )
        target_px = max(
            12,
            int(vw * _GLOBAL_TARGET_WIDTH_RATIO * _GLOBAL_TEXT_WIDTH_FUDGE)
            - _GLOBAL_CELL_PAD_PX,
        )
        return fm, player_px, target_px

    def _render_global(self, data):
        """Render a single GlobalEvent into the globals ticker."""
        html = self._global_to_html(data)
        if html is None:
            return
        self._append_line(self._global_log, html)
        self._global_lines += 1
        if self._global_lines > MAX_TICKER_LINES + _TRIM_BUFFER:
            self._rebuild_globals()

    def _rebuild_globals(self):
        """Re-render all stored globals with current viewport width."""
        fm, player_px, target_px = self._global_text_metrics()
        rows = []
        for event in self._global_events:
            html = self._global_to_html(
                event,
                fm=fm,
                player_px=player_px,
                target_px=target_px,
            )
            if html is not None:
                rows.append(html)
        # Trim to MAX_TICKER_LINES
        if len(rows) > MAX_TICKER_LINES:
            rows = rows[-MAX_TICKER_LINES:]
        self._global_log.setHtml("".join(rows))
        self._global_lines = len(rows)
        # Keep scroll at bottom so newest globals are visible
        cursor = self._global_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._global_log.setTextCursor(cursor)

    def _rebuild_trades(self):
        """Bulk-replace trade ticker HTML from the stored deque."""
        rows = list(self._trade_html)
        self._trade_log.setHtml("".join(rows))
        self._trade_lines = len(rows)
        # Keep scroll at bottom so newest trades are visible
        cursor = self._trade_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._trade_log.setTextCursor(cursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def _should_show_trade(self, data) -> bool:
        """Check dashboard config filters for trade messages."""
        # Player blocklist
        blocklist = getattr(self._config, "dashboard_trade_blocklist", [])
        if blocklist:
            uname = data.username.lower()
            if any(b.lower() == uname for b in blocklist):
                return False
        # Planet filter (whitelist — empty means show all)
        planet_filter = getattr(self._config, "dashboard_trade_planet_filter", [])
        if planet_filter:
            channel_lower = data.channel.lower()
            if not any(p.lower() in channel_lower for p in planet_filter):
                return False
        # Keyword blacklist (regex)
        blacklist = getattr(self._config, "dashboard_trade_blacklist", [])
        if blacklist:
            for pattern in blacklist:
                try:
                    if re.search(pattern, data.message, re.IGNORECASE):
                        return False
                except re.error:
                    if pattern.lower() in data.message.lower():
                        return False
        return True

    def _on_trade_chat(self, data):
        if not self._live:
            return
        self._render_trade(data)

    def _render_trade(self, data):
        """Render a single trade message into the trade ticker."""
        if not self._should_show_trade(data):
            return
        prefix = (
            f'<span style="color:{ACCENT}">'
            f'[{_esc(data.channel)}:{_esc(data.username)}]</span> '
        )
        body = _format_trade_message(
            data.message, self._config.nexus_base_url, self._item_lookup
        )
        html = prefix + body
        self._trade_html.append(html)
        self._append_line(self._trade_log, html)
        self._trade_lines += 1
        if self._trade_lines > MAX_TICKER_LINES + _TRIM_BUFFER:
            self._rebuild_trades()

    def _on_trade_link(self, url: QUrl):
        """Handle clicks on waypoint / item links in the trade ticker."""
        if url.scheme() == "wp":
            # Copy the full waypoint text to clipboard
            coords = url.toString(QUrl.ComponentFormattingOption.FullyDecoded)
            coords = coords.removeprefix("wp:")
            clipboard = QApplication.clipboard()
            clipboard.setText(f"[{coords}]")
            QToolTip.showText(
                QCursor.pos(), "Copied!", self._trade_log, QRect(), 1500
            )
        else:
            webbrowser.open(url.toString())

    def cleanup(self):
        """Stop timers and background threads."""
        self._refresh_timer.stop()
        self._ingested_flush_timer.stop()
        if self._fetcher and self._fetcher.isRunning():
            self._fetcher.quit()
            self._fetcher.wait(2000)
        if self._events_fetcher and self._events_fetcher.isRunning():
            self._events_fetcher.quit()
            self._events_fetcher.wait(2000)
        if self._article_fetcher and self._article_fetcher.isRunning():
            self._article_fetcher.quit()
            self._article_fetcher.wait(2000)
        if self._item_loader and self._item_loader.isRunning():
            self._item_loader.quit()
            self._item_loader.wait(2000)
