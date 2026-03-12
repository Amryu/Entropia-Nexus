"""Graph widget — configurable chart with multiple data sources and chart types."""

from __future__ import annotations

import json
import os
from collections import deque
from typing import Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox,
    QComboBox, QGroupBox, QStackedWidget, QCheckBox, QDoubleSpinBox,
    QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QFont
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from ..grid_widget import GridWidget, WidgetContext
from ._common import font_title, C_ACCENT

_BG   = QColor(16, 16, 26)
_AXIS = QColor(80, 80, 100)

_CHART_TYPES  = ["Line", "Bar (Vertical)", "Bar (Horizontal)", "Returns", "Pie"]
_SOURCE_TYPES = ["EventBus Event", "File", "WebSocket", "HTTP API"]

_CT_TO_KEY = {
    "Line": "line", "Bar (Vertical)": "bar_v",
    "Bar (Horizontal)": "bar_h", "Returns": "returns", "Pie": "pie",
}
_CT_FROM_KEY = {v: k for k, v in _CT_TO_KEY.items()}
_ST_TO_KEY = {
    "EventBus Event": "event", "File": "file",
    "WebSocket": "websocket", "HTTP API": "http",
}
_ST_FROM_KEY = {v: k for k, v in _ST_TO_KEY.items()}

_PIE_COLORS = [
    QColor(0, 180, 120), QColor(80, 140, 200), QColor(200, 120, 60),
    QColor(180, 60, 120), QColor(120, 180, 60), QColor(60, 120, 180),
    QColor(180, 180, 60), QColor(60, 180, 180),
]


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

class _EventSource:
    def __init__(self, event: str, field: str, context: WidgetContext):
        self._event = event
        self._field = field
        self._ctx   = context
        self._cb    = None

    def start(self, on_value: Callable[[float], None]) -> None:
        def _handler(data):
            try:
                if self._field and isinstance(data, dict):
                    v = float(data.get(self._field, 0))
                elif self._field and data is not None:
                    v = float(getattr(data, self._field, 0))
                else:
                    v = float(data) if data is not None else 0.0
                on_value(v)
            except (TypeError, ValueError):
                pass
        self._cb = _handler
        if self._event:
            self._ctx.event_bus.subscribe(self._event, self._cb)

    def stop(self) -> None:
        if self._cb and self._event:
            try:
                self._ctx.event_bus.unsubscribe(self._event, self._cb)
            except Exception:
                pass
        self._cb = None


class _FileSource:
    def __init__(self, path: str, column, interval_ms: int):
        self._path     = path
        self._column   = column
        self._interval = max(500, interval_ms)
        self._timer: QTimer | None = None
        self._last_pos = 0
        self._on_value: Callable | None = None

    def start(self, on_value: Callable[[float], None]) -> None:
        self._on_value = on_value
        self._last_pos = 0
        self._timer = QTimer()
        self._timer.setInterval(self._interval)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _poll(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                f.seek(self._last_pos)
                lines = [ln.strip() for ln in f.readlines() if ln.strip()]
                self._last_pos = f.tell()
            if not lines:
                return
            last = lines[-1]
            if last.startswith("{"):
                data = json.loads(last)
                col = self._column if isinstance(self._column, str) else str(self._column)
                v = float(data.get(col, 0))
            else:
                parts = last.split(",")
                idx = int(self._column) if isinstance(self._column, int) else 0
                v = float(parts[idx])
            if self._on_value:
                self._on_value(v)
        except Exception:
            pass

    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None


class _WsSource:
    def __init__(self, url: str, field: str):
        self._url   = url
        self._field = field
        self._ws    = None
        self._on_value: Callable | None = None

    def start(self, on_value: Callable[[float], None]) -> None:
        self._on_value = on_value
        self._connect()

    def _connect(self) -> None:
        try:
            from PyQt6.QtWebSockets import QWebSocket
        except ImportError:
            return
        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_message)
        self._ws.disconnected.connect(lambda: QTimer.singleShot(5000, self._connect))
        self._ws.open(QUrl(self._url))

    def _on_message(self, text: str) -> None:
        if not self._on_value:
            return
        try:
            data = json.loads(text)
            if self._field and isinstance(data, dict):
                v = float(data.get(self._field, 0))
            else:
                v = float(data)
            self._on_value(v)
        except Exception:
            pass

    def stop(self) -> None:
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None


class _HttpSource:
    def __init__(self, url: str, json_path: str, interval_ms: int):
        self._url       = url
        self._json_path = json_path
        self._interval  = max(1000, interval_ms)
        self._timer: QTimer | None = None
        self._nam: QNetworkAccessManager | None = None
        self._on_value: Callable | None = None

    def start(self, on_value: Callable[[float], None]) -> None:
        self._on_value = on_value
        self._nam = QNetworkAccessManager()
        self._nam.finished.connect(self._on_reply)
        self._timer = QTimer()
        self._timer.setInterval(self._interval)
        self._timer.timeout.connect(self._fetch)
        self._fetch()
        self._timer.start()

    def _fetch(self) -> None:
        if self._url and self._nam:
            try:
                self._nam.get(QNetworkRequest(QUrl(self._url)))
            except Exception:
                pass

    def _on_reply(self, reply) -> None:
        if not self._on_value:
            return
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            v = data
            for key in self._json_path.split("."):
                if key and isinstance(v, dict):
                    v = v.get(key, 0)
            self._on_value(float(v))
        except Exception:
            pass

    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._nam = None


def _make_source(cfg: dict, context: WidgetContext):
    t = cfg.get("type", "event")
    if t == "file":
        return _FileSource(cfg.get("path", ""), cfg.get("column", 0), cfg.get("interval_ms", 5000))
    if t == "websocket":
        return _WsSource(cfg.get("url", ""), cfg.get("field", ""))
    if t == "http":
        return _HttpSource(cfg.get("url", ""), cfg.get("json_path", ""), cfg.get("interval_ms", 30000))
    return _EventSource(cfg.get("event", ""), cfg.get("field", ""), context)


# ---------------------------------------------------------------------------
# Chart renderers
# ---------------------------------------------------------------------------

def _render_line(painter: QPainter, vals: list, rect, cfg: dict) -> None:
    if len(vals) < 2:
        return
    pad = 6
    x0  = rect.x() + pad
    y0  = rect.y() + pad
    w   = rect.width()  - 2 * pad
    h   = rect.height() - 2 * pad
    mn, mx = min(vals), max(vals)
    span = mx - mn if mx != mn else 1.0

    def px(i): return x0 + (i / (len(vals) - 1)) * w
    def py(v): return y0 + h - ((v - mn) / span) * h

    line_color = QColor(cfg.get("line_color", "#00ff88"))
    fill_alpha = int(cfg.get("fill_alpha", 40))

    path = QPainterPath()
    path.moveTo(px(0), py(vals[0]))
    for i, v in enumerate(vals[1:], 1):
        path.lineTo(px(i), py(v))

    if fill_alpha > 0:
        fc = QColor(line_color)
        fc.setAlpha(fill_alpha)
        fill = QPainterPath(path)
        fill.lineTo(px(len(vals) - 1), y0 + h)
        fill.lineTo(px(0), y0 + h)
        fill.closeSubpath()
        painter.fillPath(fill, fc)

    painter.setPen(QPen(line_color, 1.5))
    painter.drawPath(path)

    painter.setPen(QPen(_AXIS, 1))
    painter.drawLine(int(x0), int(y0 + h), int(x0 + w), int(y0 + h))

    f = QFont()
    f.setPointSize(max(6, min(8, h // 10)))
    painter.setFont(f)
    painter.setPen(QPen(QColor(120, 120, 140), 1))
    painter.drawText(int(x0) + 2, int(y0) + 10, f"{mx:.2f}")
    painter.drawText(int(x0) + 2, int(y0 + h) - 2, f"{mn:.2f}")


def _render_bar_v(painter: QPainter, vals: list, rect, cfg: dict) -> None:
    if not vals:
        return
    pad = 6
    x0 = rect.x() + pad
    y0 = rect.y() + pad
    w  = rect.width()  - 2 * pad
    h  = rect.height() - 2 * pad
    mn   = min(0.0, min(vals))
    mx   = max(vals)
    span = mx - mn if mx != mn else 1.0
    bar_w = max(1.0, w / len(vals))
    line_color = QColor(cfg.get("line_color", "#00ff88"))
    neg_color  = QColor(cfg.get("negative_color", "#cc2244"))
    zero_y = y0 + h - (-mn / span) * h

    painter.setPen(Qt.PenStyle.NoPen)
    for i, v in enumerate(vals):
        bh = max(1, abs(v / span) * h)
        bx = x0 + i * bar_w + 1
        by = zero_y - (v / span) * h if v >= 0 else zero_y
        painter.setBrush(line_color if v >= 0 else neg_color)
        painter.drawRect(int(bx), int(by), max(1, int(bar_w - 2)), int(bh))

    painter.setPen(QPen(_AXIS, 1))
    painter.drawLine(int(x0), int(zero_y), int(x0 + w), int(zero_y))


def _render_bar_h(painter: QPainter, vals: list, rect, cfg: dict) -> None:
    if not vals:
        return
    pad = 6
    x0 = rect.x() + pad
    y0 = rect.y() + pad
    w  = rect.width()  - 2 * pad
    h  = rect.height() - 2 * pad
    mx = max(abs(v) for v in vals) or 1.0
    bar_h = max(1.0, h / len(vals))
    line_color = QColor(cfg.get("line_color", "#00ff88"))
    neg_color  = QColor(cfg.get("negative_color", "#cc2244"))

    painter.setPen(Qt.PenStyle.NoPen)
    for i, v in enumerate(vals):
        bw = (abs(v) / mx) * w
        bx = x0 if v >= 0 else x0 + w - bw
        by = y0 + i * bar_h + 1
        painter.setBrush(line_color if v >= 0 else neg_color)
        painter.drawRect(int(bx), int(by), max(1, int(bw)), max(1, int(bar_h - 2)))

    painter.setPen(QPen(_AXIS, 1))
    painter.drawLine(int(x0), int(y0), int(x0), int(y0 + h))


def _render_returns(painter: QPainter, vals: list, rect, cfg: dict) -> None:
    if not vals:
        return
    pad = 6
    x0 = rect.x() + pad
    y0 = rect.y() + pad
    w  = rect.width()  - 2 * pad
    h  = rect.height() - 2 * pad
    baseline  = float(cfg.get("baseline", 100.0))
    mn  = min(min(vals), baseline * 0.9)
    mx  = max(max(vals), baseline * 1.1)
    span = mx - mn if mx != mn else 1.0

    pos_color = QColor(cfg.get("positive_color", "#00cc44"))
    neg_color = QColor(cfg.get("negative_color", "#cc2244"))

    def py(v): return y0 + h - ((v - mn) / span) * h
    def px(i): return x0 + (i / max(len(vals) - 1, 1)) * w

    baseline_y = int(py(baseline))

    # Dashed baseline
    pen = QPen(QColor(160, 160, 160), 1, Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.drawLine(int(x0), baseline_y, int(x0 + w), baseline_y)

    if cfg.get("candle_mode", False):
        cw = max(2.0, w / len(vals))
        painter.setPen(Qt.PenStyle.NoPen)
        for i, v in enumerate(vals):
            top_y = int(min(py(v), baseline_y))
            bot_y = int(max(py(v), baseline_y))
            bh = max(1, bot_y - top_y)
            painter.setBrush(pos_color if v >= baseline else neg_color)
            painter.drawRect(int(x0 + i * cw + 1), top_y, max(1, int(cw - 2)), bh)
    else:
        if len(vals) < 2:
            return
        points = [(px(i), py(v), v) for i, v in enumerate(vals)]
        for i in range(len(points) - 1):
            x1, y1, v1 = points[i]
            x2, y2, v2 = points[i + 1]
            color = pos_color if (v1 + v2) / 2 >= baseline else neg_color
            painter.setPen(QPen(color, 1.5))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    painter.setPen(QPen(_AXIS, 1))
    painter.drawLine(int(x0), int(y0 + h), int(x0 + w), int(y0 + h))


def _render_pie(painter: QPainter, vals: list, rect, cfg: dict) -> None:
    pos_vals = [max(0.0, v) for v in vals]
    total = sum(pos_vals)
    if total <= 0:
        return
    pad  = 10
    size = min(rect.width(), rect.height()) - 2 * pad
    cx   = rect.x() + rect.width()  // 2
    cy   = rect.y() + rect.height() // 2
    r    = size // 2
    angle = 0.0
    painter.setPen(QPen(QColor(20, 20, 30), 1))
    for i, v in enumerate(pos_vals):
        if v <= 0:
            continue
        span_deg = 360 * (v / total)
        painter.setBrush(_PIE_COLORS[i % len(_PIE_COLORS)])
        painter.drawPie(cx - r, cy - r, 2 * r, 2 * r,
                        int(angle * 16), int(span_deg * 16))
        angle += span_deg


# ---------------------------------------------------------------------------
# Config dialog
# ---------------------------------------------------------------------------

_DIALOG_STYLE = """
    QDialog       { background: #1a1a2e; }
    QGroupBox     { color: #00ccff; border: 1px solid #333355; border-radius: 4px;
                    margin-top: 8px; padding-top: 6px; font-size: 11px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; top: 2px; }
    QLabel        { color: #cccccc; font-size: 11px; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                    background: #252535; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px;
                    padding: 3px 6px; font-size: 11px; }
    QCheckBox     { color: #cccccc; font-size: 11px; }
    QCheckBox::indicator { width: 14px; height: 14px; }
    QPushButton   { background: #333350; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px;
                    padding: 4px 14px; font-size: 11px; }
    QPushButton:hover   { background: #404060; }
    QPushButton:pressed { background: #252540; }
"""


class _GraphConfigDialog(QDialog):
    def __init__(
        self,
        cfg: dict,
        *,
        parent=None,
        event_bus=None,
        current_colspan: int = 6,
        current_rowspan: int = 4,
        max_cols: int = 50,
        max_rows: int = 50,
        widget_max_cols: int = 0,
        widget_max_rows: int = 0,
    ):
        super().__init__(parent)
        self._event_bus = event_bus
        self.setWindowTitle("Configure Graph")
        self.setMinimumWidth(380)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        eff_max_cols = min(max_cols, widget_max_cols) if widget_max_cols > 0 else max_cols
        eff_max_rows = min(max_rows, widget_max_rows) if widget_max_rows > 0 else max_rows
        src_cfg = cfg.get("data_source", {})

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Chart type ───────────────────────────────────────────────────────
        ct_group = QGroupBox("Chart Type")
        ct_form  = QFormLayout(ct_group)
        ct_form.setSpacing(6)
        self._chart_combo = QComboBox()
        self._chart_combo.addItems(_CHART_TYPES)
        self._chart_combo.setCurrentText(_CT_FROM_KEY.get(cfg.get("chart_type", "line"), "Line"))
        ct_form.addRow("Type:", self._chart_combo)
        root.addWidget(ct_group)

        # ── Data source ──────────────────────────────────────────────────────
        ds_group  = QGroupBox("Data Source")
        ds_layout = QVBoxLayout(ds_group)
        ds_layout.setSpacing(4)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source:"))
        self._src_combo = QComboBox()
        self._src_combo.addItems(_SOURCE_TYPES)
        self._src_combo.setCurrentText(_ST_FROM_KEY.get(src_cfg.get("type", "event"), "EventBus Event"))
        src_row.addWidget(self._src_combo)
        ds_layout.addLayout(src_row)

        self._src_stack = QStackedWidget()

        # Page 0: EventBus
        ev_page = QWidget()
        ev_form = QFormLayout(ev_page)
        ev_form.setContentsMargins(0, 0, 0, 0)

        ev_event_row = QHBoxLayout()
        self._ev_event = QLineEdit(src_cfg.get("event", ""))
        self._ev_event.setPlaceholderText("e.g. EVENT_LOOT_GROUP")
        ev_event_row.addWidget(self._ev_event)

        self._ev_field = QLineEdit(src_cfg.get("field", ""))
        self._ev_field.setPlaceholderText("dict key or attr — blank = raw value")

        if event_bus is not None:
            ev_browse_btn = QPushButton("Browse…")
            ev_browse_btn.setFixedWidth(70)
            ev_browse_btn.clicked.connect(self._browse_event)
            ev_event_row.addWidget(ev_browse_btn)

        ev_form.addRow("Event:", ev_event_row)
        ev_form.addRow("Field:", self._ev_field)
        self._src_stack.addWidget(ev_page)

        # Page 1: File
        file_page = QWidget()
        file_form = QFormLayout(file_page)
        file_form.setContentsMargins(0, 0, 0, 0)
        fp_row = QHBoxLayout()
        self._file_path = QLineEdit(src_cfg.get("path", ""))
        self._file_path.setPlaceholderText("Path to CSV or JSON lines file")
        fp_btn = QPushButton("…")
        fp_btn.setFixedWidth(28)
        fp_btn.clicked.connect(self._pick_file)
        fp_row.addWidget(self._file_path)
        fp_row.addWidget(fp_btn)
        self._file_col = QLineEdit(str(src_cfg.get("column", 0)))
        self._file_col.setPlaceholderText("Column index (CSV) or JSON key")
        self._file_interval = QSpinBox()
        self._file_interval.setRange(500, 3600000)
        self._file_interval.setSuffix(" ms")
        self._file_interval.setValue(src_cfg.get("interval_ms", 5000))
        file_form.addRow("File:", fp_row)
        file_form.addRow("Column/Key:", self._file_col)
        file_form.addRow("Poll interval:", self._file_interval)
        self._src_stack.addWidget(file_page)

        # Page 2: WebSocket
        ws_page = QWidget()
        ws_form = QFormLayout(ws_page)
        ws_form.setContentsMargins(0, 0, 0, 0)
        self._ws_url = QLineEdit(src_cfg.get("url", ""))
        self._ws_url.setPlaceholderText("ws://host:port/path")
        self._ws_field = QLineEdit(src_cfg.get("field", ""))
        self._ws_field.setPlaceholderText("JSON field name — blank = raw value")
        ws_form.addRow("URL:", self._ws_url)
        ws_form.addRow("Field:", self._ws_field)
        self._src_stack.addWidget(ws_page)

        # Page 3: HTTP
        http_page = QWidget()
        http_form = QFormLayout(http_page)
        http_form.setContentsMargins(0, 0, 0, 0)
        self._http_url = QLineEdit(src_cfg.get("url", ""))
        self._http_url.setPlaceholderText("https://api.example.com/endpoint")
        self._http_path = QLineEdit(src_cfg.get("json_path", ""))
        self._http_path.setPlaceholderText("dot.path.to.value  (e.g. data.price)")
        self._http_interval = QSpinBox()
        self._http_interval.setRange(1000, 3600000)
        self._http_interval.setSuffix(" ms")
        self._http_interval.setValue(src_cfg.get("interval_ms", 30000))
        http_form.addRow("URL:", self._http_url)
        http_form.addRow("JSON path:", self._http_path)
        http_form.addRow("Poll interval:", self._http_interval)
        self._src_stack.addWidget(http_page)

        ds_layout.addWidget(self._src_stack)
        root.addWidget(ds_group)

        _src_idx = {"EventBus Event": 0, "File": 1, "WebSocket": 2, "HTTP API": 3}
        self._src_stack.setCurrentIndex(_src_idx.get(self._src_combo.currentText(), 0))
        self._src_combo.currentTextChanged.connect(
            lambda t: self._src_stack.setCurrentIndex(_src_idx.get(t, 0))
        )

        # ── Display ──────────────────────────────────────────────────────────
        disp_group = QGroupBox("Display")
        disp_form  = QFormLayout(disp_group)
        disp_form.setSpacing(6)

        self._title_edit = QLineEdit(cfg.get("title", "Graph"))
        disp_form.addRow("Title:", self._title_edit)

        self._maxpts_spin = QSpinBox()
        self._maxpts_spin.setRange(5, 500)
        self._maxpts_spin.setValue(cfg.get("max_points", 60))
        disp_form.addRow("Max points:", self._maxpts_spin)

        lc_row = QHBoxLayout()
        self._line_color_edit = QLineEdit(cfg.get("line_color", "#00ff88"))
        self._line_color_edit.setFixedWidth(90)
        self._line_color_btn = QPushButton()
        self._line_color_btn.setFixedSize(26, 26)
        self._line_color_btn.setStyleSheet(
            f"background: {cfg.get('line_color', '#00ff88')}; border: 1px solid #666;"
        )
        self._line_color_btn.clicked.connect(
            lambda: self._pick_color(self._line_color_edit, self._line_color_btn)
        )
        self._line_color_edit.textChanged.connect(
            lambda t: self._sync_btn(t, self._line_color_btn)
        )
        lc_row.addWidget(self._line_color_edit)
        lc_row.addWidget(self._line_color_btn)
        lc_row.addStretch()
        disp_form.addRow("Line color:", lc_row)

        self._fill_alpha_spin = QSpinBox()
        self._fill_alpha_spin.setRange(0, 255)
        self._fill_alpha_spin.setToolTip("Opacity of fill area under line (0 = no fill)")
        self._fill_alpha_spin.setValue(cfg.get("fill_alpha", 40))
        disp_form.addRow("Fill alpha (0=none):", self._fill_alpha_spin)

        root.addWidget(disp_group)

        # ── Returns options ──────────────────────────────────────────────────
        self._returns_group = QGroupBox("Returns Options")
        ret_form = QFormLayout(self._returns_group)
        ret_form.setSpacing(6)

        self._baseline_spin = QDoubleSpinBox()
        self._baseline_spin.setRange(0.1, 9999.9)
        self._baseline_spin.setDecimals(1)
        self._baseline_spin.setSuffix("%")
        self._baseline_spin.setValue(cfg.get("baseline", 100.0))
        ret_form.addRow("Baseline:", self._baseline_spin)

        for attr, label, default in [
            ("_pos_color_edit", "Above baseline:", "#00cc44"),
            ("_neg_color_edit", "Below baseline:", "#cc2244"),
        ]:
            row = QHBoxLayout()
            edit = QLineEdit(cfg.get(
                "positive_color" if "pos" in attr else "negative_color", default
            ))
            edit.setFixedWidth(90)
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(f"background: {edit.text()}; border: 1px solid #666;")
            btn.clicked.connect(lambda _, e=edit, b=btn: self._pick_color(e, b))
            edit.textChanged.connect(lambda t, b=btn: self._sync_btn(t, b))
            setattr(self, attr, edit)
            setattr(self, attr.replace("_edit", "_btn"), btn)
            row.addWidget(edit)
            row.addWidget(btn)
            row.addStretch()
            ret_form.addRow(label, row)

        self._candle_check = QCheckBox("Candle mode (one bar per event)")
        self._candle_check.setChecked(cfg.get("candle_mode", False))
        ret_form.addRow("", self._candle_check)
        root.addWidget(self._returns_group)

        def _toggle_returns(ct: str):
            self._returns_group.setVisible(ct == "Returns")
            self.setMinimumHeight(0)
            self.adjustSize()
        _toggle_returns(self._chart_combo.currentText())
        self._chart_combo.currentTextChanged.connect(_toggle_returns)

        # ── Size ─────────────────────────────────────────────────────────────
        size_group = QGroupBox("Size (tiles)")
        size_form  = QFormLayout(size_group)
        size_form.setSpacing(6)

        self._cs_spin = QSpinBox()
        self._cs_spin.setRange(1, eff_max_cols)
        self._cs_spin.setValue(current_colspan)
        size_form.addRow("Width (colspan):", self._cs_spin)

        self._rs_spin = QSpinBox()
        self._rs_spin.setRange(1, eff_max_rows)
        self._rs_spin.setValue(current_rowspan)
        size_form.addRow("Height (rowspan):", self._rs_spin)

        root.addWidget(size_group)

        # ── Buttons ──────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setStyleSheet(
                "QPushButton { background: #305090; border-color: #4070b0; }"
                "QPushButton:hover { background: #3a60a8; }"
            )
        root.addWidget(btns)

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select file", "", "CSV/JSON (*.csv *.json);;All (*)"
        )
        if path:
            self._file_path.setText(path)

    def _browse_event(self) -> None:
        from ..event_explorer_dialog import EventExplorerDialog
        dlg = EventExplorerDialog(
            event_bus=self._event_bus,
            initial_event=self._ev_event.text().strip(),
            initial_field=self._ev_field.text().strip(),
            parent=self,
        )
        if dlg.exec():
            if dlg.selected_event:
                self._ev_event.setText(dlg.selected_event)
            if dlg.selected_field:
                self._ev_field.setText(dlg.selected_field)

    def _pick_color(self, edit: QLineEdit, btn: QPushButton) -> None:
        from PyQt6.QtWidgets import QColorDialog
        current = QColor(edit.text())
        if not current.isValid():
            current = QColor("#00ff88")
        color = QColorDialog.getColor(current, self, "Choose colour")
        if color.isValid():
            edit.setText(color.name())

    def _sync_btn(self, text: str, btn: QPushButton) -> None:
        c = QColor(text)
        if c.isValid():
            btn.setStyleSheet(f"background: {c.name()}; border: 1px solid #666;")

    def get_result(self) -> dict:
        src_type = _ST_TO_KEY.get(self._src_combo.currentText(), "event")
        src_cfg: dict = {"type": src_type}
        if src_type == "event":
            src_cfg.update(event=self._ev_event.text().strip(),
                           field=self._ev_field.text().strip())
        elif src_type == "file":
            col_str = self._file_col.text().strip()
            col = int(col_str) if col_str.isdigit() else col_str
            src_cfg.update(path=self._file_path.text().strip(),
                           column=col,
                           interval_ms=self._file_interval.value())
        elif src_type == "websocket":
            src_cfg.update(url=self._ws_url.text().strip(),
                           field=self._ws_field.text().strip())
        elif src_type == "http":
            src_cfg.update(url=self._http_url.text().strip(),
                           json_path=self._http_path.text().strip(),
                           interval_ms=self._http_interval.value())

        return {
            "chart_type":     _CT_TO_KEY.get(self._chart_combo.currentText(), "line"),
            "title":          self._title_edit.text() or "Graph",
            "max_points":     self._maxpts_spin.value(),
            "data_source":    src_cfg,
            "line_color":     self._line_color_edit.text() or "#00ff88",
            "fill_alpha":     self._fill_alpha_spin.value(),
            "positive_color": self._pos_color_edit.text() or "#00cc44",
            "negative_color": self._neg_color_edit.text() or "#cc2244",
            "candle_mode":    self._candle_check.isChecked(),
            "baseline":       self._baseline_spin.value(),
            "__slot__": {
                "colspan": self._cs_spin.value(),
                "rowspan": self._rs_spin.value(),
            },
        }


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

class _GraphCanvas(QWidget):
    """Dispatches to the correct renderer based on chart_type in cfg_fn()."""

    def __init__(self, values: deque, cfg_fn: Callable[[], dict], parent=None):
        super().__init__(parent)
        self._values = values
        self._cfg_fn = cfg_fn
        self.setMinimumSize(40, 30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), _BG)
        vals = list(self._values)
        if not vals:
            return
        cfg = self._cfg_fn()
        ct  = cfg.get("chart_type", "line")
        r   = self.rect()
        if ct == "bar_v":
            _render_bar_v(painter, vals, r, cfg)
        elif ct == "bar_h":
            _render_bar_h(painter, vals, r, cfg)
        elif ct == "returns":
            _render_returns(painter, vals, r, cfg)
        elif ct == "pie":
            _render_pie(painter, vals, r, cfg)
        else:
            _render_line(painter, vals, r, cfg)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class GraphWidget(GridWidget):
    """Configurable chart — line, bar, returns, or pie; any data source."""

    WIDGET_ID    = "com.entropianexus.graph"
    DISPLAY_NAME = "Graph"
    DESCRIPTION  = "Configurable chart (line/bar/returns/pie) from EventBus, file, WebSocket, or HTTP."
    DEFAULT_COLSPAN = 6
    DEFAULT_ROWSPAN = 4
    MIN_COLSPAN  = 3
    MIN_ROWSPAN  = 3

    def __init__(self, config: dict):
        super().__init__(config)
        max_pts = max(5, config.get("max_points", 60))
        self._values: deque[float] = deque(maxlen=max_pts)
        self._canvas: _GraphCanvas | None = None
        self._title_label: QLabel | None  = None
        self._source = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._start_source()

    def _start_source(self) -> None:
        if self._context is None:
            return
        src_cfg = self._widget_config.get("data_source", {"type": "event"})
        try:
            self._source = _make_source(src_cfg, self._context)
            self._source.start(self._on_value)
        except Exception as exc:
            import logging
            logging.getLogger("GraphWidget").error("Source start failed: %s", exc)
            self._source = None

    def _stop_source(self) -> None:
        if self._source is not None:
            try:
                self._source.stop()
            except Exception:
                pass
            self._source = None

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        self._title_label = QLabel(self._widget_config.get("title", "Graph"))
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self._title_label)

        self._canvas = _GraphCanvas(self._values, lambda: self._widget_config)
        layout.addWidget(self._canvas, 1)

        return w

    def _on_value(self, v: float) -> None:
        self._values.append(v)
        if self._canvas:
            self._canvas.update()

    def teardown(self) -> None:
        self._stop_source()
        super().teardown()

    def on_resize(self, width: int, height: int) -> None:
        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {font_title(height)}px;"
            )
        if self._canvas:
            self._canvas.update()

    def configure(self, parent: QWidget, **kwargs) -> dict | None:
        dlg = _GraphConfigDialog(
            self._widget_config,
            parent=parent,
            event_bus=self._context.event_bus if self._context else None,
            current_colspan=kwargs.get("current_colspan", self.DEFAULT_COLSPAN),
            current_rowspan=kwargs.get("current_rowspan", self.DEFAULT_ROWSPAN),
            max_cols=kwargs.get("max_cols", 50),
            max_rows=kwargs.get("max_rows", 50),
            widget_max_cols=self.MAX_COLSPAN,
            widget_max_rows=self.MAX_ROWSPAN,
        )
        return dlg.get_result() if dlg.exec() else None

    def on_config_changed(self, config: dict) -> None:
        self._stop_source()

        new_max = max(5, config.get("max_points", self._widget_config.get("max_points", 60)))
        if new_max != self._values.maxlen:
            new_dq = deque(self._values, maxlen=new_max)
            self._values = new_dq
            if self._canvas:
                self._canvas._values = self._values

        super().on_config_changed(config)

        if self._title_label:
            self._title_label.setText(self._widget_config.get("title", "Graph"))

        self._start_source()

        if self._canvas:
            self._canvas.update()

    def get_config(self) -> dict:
        return dict(self._widget_config)
