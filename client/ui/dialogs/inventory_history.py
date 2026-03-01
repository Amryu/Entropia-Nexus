"""Inventory history dialog — paginated import list with expandable deltas and value chart."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPainterPath, QFont, QFontMetrics,
)

from ..theme import (
    PRIMARY, SECONDARY, HOVER, BORDER, ACCENT,
    TEXT, TEXT_MUTED, ERROR, TABLE_ROW_ALT,
)
from ...core.inventory_utils import format_ped
from ...core.logger import get_logger

log = get_logger("InventoryHistory")

PAGE_SIZE = 20

# Badge colors
_CLR_ADDED = "#48b868"
_CLR_CHANGED = "#d4a030"
_CLR_REMOVED = "#e06060"

# Time span filters: (label, timedelta or None for "all time")
_TIME_FILTERS: list[tuple[str, timedelta | None]] = [
    ("24h", timedelta(hours=24)),
    ("7d", timedelta(days=7)),
    ("30d", timedelta(days=30)),
    ("90d", timedelta(days=90)),
    ("1y", timedelta(days=365)),
    ("5y", timedelta(days=5 * 365)),
    ("10y", timedelta(days=10 * 365)),
    ("All", None),
]


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class _HistoryLoader(QThread):
    """Load import history and value history in parallel."""
    finished = pyqtSignal(object, object, str)  # imports, value_history, error

    def __init__(self, nexus_client, limit: int, offset: int,
                 load_value: bool = True, since: str | None = None):
        super().__init__()
        self._nc = nexus_client
        self._limit = limit
        self._offset = offset
        self._load_value = load_value
        self._since = since

    def run(self):
        try:
            imports = self._nc.get_import_history(
                self._limit, self._offset, since=self._since)
            value_history = None
            if self._load_value:
                value_history = self._nc.get_value_history(since=self._since)
            if imports is None:
                self.finished.emit(None, None, "Failed to load history.")
            else:
                self.finished.emit(imports, value_history, "")
        except Exception as e:
            log.error("HistoryLoader error: %s", e)
            self.finished.emit(None, None, str(e))


class _DeltaLoader(QThread):
    """Load deltas for a specific import."""
    finished = pyqtSignal(int, object, str)  # import_id, deltas, error

    def __init__(self, nexus_client, import_id: int):
        super().__init__()
        self._nc = nexus_client
        self._import_id = import_id

    def run(self):
        try:
            deltas = self._nc.get_import_deltas(self._import_id)
            if deltas is None:
                self.finished.emit(self._import_id, None, "Failed to load details.")
            else:
                self.finished.emit(self._import_id, deltas, "")
        except Exception as e:
            log.error("DeltaLoader error: %s", e)
            self.finished.emit(self._import_id, None, str(e))


# ---------------------------------------------------------------------------
# Value chart widget
# ---------------------------------------------------------------------------

class _ValueChart(QWidget):
    """Simple line chart showing portfolio value over time."""

    PADDING_LEFT = 65
    PADDING_RIGHT = 16
    PADDING_TOP = 20
    PADDING_BOTTOM = 30
    MIN_HEIGHT = 160
    POINT_RADIUS = 4
    HOVER_RADIUS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self._hover_idx: int = -1
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setMaximumHeight(200)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: list[dict]):
        self._data = data or []
        self._hover_idx = -1
        self.update()

    def _get_display_total(self, d: dict) -> float:
        est = d.get('estimated_value')
        tt = d.get('total_value') or 0
        unknown = d.get('unknown_value') or 0
        if est is not None:
            return float(est) + float(unknown)
        return float(tt) + float(unknown)

    def _chart_rect(self) -> QRectF:
        return QRectF(
            self.PADDING_LEFT, self.PADDING_TOP,
            self.width() - self.PADDING_LEFT - self.PADDING_RIGHT,
            self.height() - self.PADDING_TOP - self.PADDING_BOTTOM,
        )

    def _data_points(self) -> list[QPointF]:
        if len(self._data) < 2:
            return []
        rect = self._chart_rect()
        values = [self._get_display_total(d) for d in self._data]
        min_v = min(values)
        max_v = max(values)
        v_range = max_v - min_v or 1
        n = len(values)
        points = []
        for i, v in enumerate(values):
            x = rect.left() + (i / (n - 1)) * rect.width()
            y = rect.bottom() - ((v - min_v) / v_range) * rect.height()
            points.append(QPointF(x, y))
        return points

    def paintEvent(self, event):
        if len(self._data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._chart_rect()
        values = [self._get_display_total(d) for d in self._data]
        min_v = min(values)
        max_v = max(values)
        v_range = max_v - min_v or 1
        points = self._data_points()

        # Grid lines + Y-axis labels
        grid_pen = QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine)
        label_font = QFont()
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        num_ticks = 5
        for i in range(num_ticks):
            y = rect.bottom() - (i / (num_ticks - 1)) * rect.height()
            v = min_v + (i / (num_ticks - 1)) * v_range
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QPen(QColor(TEXT_MUTED)))
            label = _format_chart_value(v)
            painter.drawText(QRectF(0, y - 8, self.PADDING_LEFT - 6, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             label)

        # X-axis date labels (first, middle, last)
        if self._data:
            for idx in (0, len(self._data) // 2, len(self._data) - 1):
                if idx < len(points):
                    dt = _parse_date(self._data[idx].get('imported_at', ''))
                    label = dt.strftime('%b %d') if dt else ''
                    x = points[idx].x()
                    painter.setPen(QPen(QColor(TEXT_MUTED)))
                    painter.drawText(
                        QRectF(x - 30, rect.bottom() + 4, 60, 20),
                        Qt.AlignmentFlag.AlignCenter, label,
                    )

        # Area fill
        if len(points) >= 2:
            area = QPainterPath()
            area.moveTo(QPointF(points[0].x(), rect.bottom()))
            for p in points:
                area.lineTo(p)
            area.lineTo(QPointF(points[-1].x(), rect.bottom()))
            area.closeSubpath()
            fill_color = QColor(ACCENT)
            fill_color.setAlpha(30)
            painter.fillPath(area, QBrush(fill_color))

            # Line
            line_path = QPainterPath()
            line_path.moveTo(points[0])
            for p in points[1:]:
                line_path.lineTo(p)
            painter.setPen(QPen(QColor(ACCENT), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line_path)

        # Points
        for i, p in enumerate(points):
            r = self.HOVER_RADIUS if i == self._hover_idx else self.POINT_RADIUS
            painter.setPen(QPen(QColor(ACCENT), 1))
            painter.setBrush(QBrush(QColor(ACCENT)))
            painter.drawEllipse(p, r, r)

        # Hover tooltip
        if 0 <= self._hover_idx < len(self._data):
            d = self._data[self._hover_idx]
            p = points[self._hover_idx]
            val = self._get_display_total(d)
            dt = _parse_date(d.get('imported_at', ''))
            count = d.get('item_count', 0)
            lines = [f"{format_ped(val)} PED"]
            if dt:
                lines.append(dt.strftime('%Y-%m-%d %H:%M'))
            lines.append(f"{count:,} items")
            unknown = d.get('unknown_value')
            if unknown and float(unknown) > 0:
                lines.append(f"Unknown: {format_ped(float(unknown))} PED")

            tooltip_text = '\n'.join(lines)
            fm = QFontMetrics(label_font)
            tw = max(fm.horizontalAdvance(l) for l in lines) + 16
            th = fm.height() * len(lines) + 12

            tx = p.x() + 10
            ty = p.y() - th - 5
            if tx + tw > self.width():
                tx = p.x() - tw - 10
            if ty < 0:
                ty = p.y() + 10

            tooltip_rect = QRectF(tx, ty, tw, th)
            painter.setPen(QPen(QColor(BORDER)))
            painter.setBrush(QBrush(QColor(PRIMARY)))
            painter.drawRoundedRect(tooltip_rect, 4, 4)

            painter.setPen(QPen(QColor(TEXT)))
            painter.drawText(tooltip_rect.adjusted(8, 6, -8, -6),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             tooltip_text)

            # Vertical line
            painter.setPen(QPen(QColor(TEXT_MUTED), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(p.x(), rect.top()), QPointF(p.x(), rect.bottom()))

        painter.end()

    def mouseMoveEvent(self, event):
        points = self._data_points()
        if not points:
            if self._hover_idx >= 0:
                self._hover_idx = -1
                self.update()
            return
        mx = event.position().x()
        closest = min(range(len(points)), key=lambda i: abs(points[i].x() - mx))
        if closest != self._hover_idx:
            self._hover_idx = closest
            self.update()

    def leaveEvent(self, event):
        if self._hover_idx >= 0:
            self._hover_idx = -1
            self.update()


# ---------------------------------------------------------------------------
# Import row widget
# ---------------------------------------------------------------------------

class _ImportRow(QWidget):
    """A single import entry — collapsible with delta details."""

    def __init__(self, import_data: dict, nexus_client, parent=None):
        super().__init__(parent)
        self._data = import_data
        self._nc = nexus_client
        self._expanded = False
        self._deltas_loaded = False
        self._delta_loader: _DeltaLoader | None = None

        self._build_ui()

    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # Header (clickable)
        header = QWidget()
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 8px 12px;
            }}
            QWidget:hover {{
                background-color: {HOVER};
            }}
        """)
        header.mousePressEvent = lambda e: self._toggle_expand()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # Expand indicator
        self._expand_icon = QLabel("\u25b6")  # ▶
        self._expand_icon.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")
        self._expand_icon.setFixedWidth(14)
        h_layout.addWidget(self._expand_icon)

        # Date
        dt = _parse_date(self._data.get('imported_at', ''))
        date_text = dt.strftime('%Y-%m-%d %H:%M') if dt else self._data.get('imported_at', '?')
        date_lbl = QLabel(date_text)
        date_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 500; background: transparent; border: none;")
        h_layout.addWidget(date_lbl)

        # Item count
        count = self._data.get('item_count', 0)
        count_lbl = QLabel(f"{count:,} items")
        count_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent; border: none;")
        h_layout.addWidget(count_lbl)

        # Value
        est = self._data.get('estimated_value')
        tt = self._data.get('total_value')
        unknown = self._data.get('unknown_value')
        val = float(est) if est is not None else (float(tt) if tt is not None else None)
        if val is not None:
            val_lbl = QLabel(f"{format_ped(val)} PED")
            val_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; background: transparent; border: none;")
            h_layout.addWidget(val_lbl)
        if unknown is not None and float(unknown) > 0:
            unk_lbl = QLabel(f"(+{format_ped(float(unknown))} unknown)")
            unk_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
            h_layout.addWidget(unk_lbl)

        h_layout.addStretch()

        # Summary badges
        summary = self._data.get('summary') or {}
        added = summary.get('added', 0)
        updated = summary.get('updated', 0)
        removed = summary.get('removed', 0)
        if added > 0:
            h_layout.addWidget(_mini_badge(f"+{added}", _CLR_ADDED))
        if updated > 0:
            h_layout.addWidget(_mini_badge(f"~{updated}", _CLR_CHANGED))
        if removed > 0:
            h_layout.addWidget(_mini_badge(f"-{removed}", _CLR_REMOVED))

        self._outer.addWidget(header)

        # Delta area (hidden)
        self._delta_widget = QWidget()
        self._delta_widget.hide()
        delta_layout = QVBoxLayout(self._delta_widget)
        delta_layout.setContentsMargins(20, 4, 0, 8)

        self._delta_status = QLabel("Loading...")
        self._delta_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        delta_layout.addWidget(self._delta_status)

        self._delta_tree = QTreeWidget()
        self._delta_tree.setHeaderLabels(["Status", "Item", "Old Qty", "New Qty", "Container"])
        self._delta_tree.setRootIsDecorated(False)
        self._delta_tree.setAlternatingRowColors(True)
        self._delta_tree.setMinimumHeight(120)
        self._delta_tree.setMaximumHeight(250)
        self._delta_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {PRIMARY};
                alternate-background-color: {TABLE_ROW_ALT};
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            QTreeWidget::item {{
                padding: 1px 4px;
                min-height: 20px;
            }}
        """)
        hdr = self._delta_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._delta_tree.hide()
        delta_layout.addWidget(self._delta_tree)

        self._outer.addWidget(self._delta_widget)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._expand_icon.setText("\u25bc" if self._expanded else "\u25b6")  # ▼ or ▶
        self._delta_widget.setVisible(self._expanded)

        if self._expanded and not self._deltas_loaded:
            self._load_deltas()

    def _load_deltas(self):
        import_id = self._data.get('id')
        if not import_id:
            self._delta_status.setText("No import ID.")
            return

        self._delta_status.setText("Loading...")
        self._delta_status.show()
        self._delta_tree.hide()

        self._delta_loader = _DeltaLoader(self._nc, import_id)
        self._delta_loader.finished.connect(self._on_deltas_loaded)
        self._delta_loader.start()

    def _on_deltas_loaded(self, import_id: int, deltas: list[dict] | None, error: str):
        self._delta_loader = None
        self._deltas_loaded = True

        if error or deltas is None:
            self._delta_status.setText(error or "Failed to load.")
            return

        if not deltas:
            self._delta_status.setText("No changes recorded.")
            return

        self._delta_status.hide()
        self._delta_tree.show()
        self._delta_tree.clear()

        type_colors = {
            'added': QColor(_CLR_ADDED),
            'changed': QColor(_CLR_CHANGED),
            'removed': QColor(_CLR_REMOVED),
        }
        type_labels = {
            'added': 'Added',
            'changed': 'Changed',
            'removed': 'Removed',
        }

        for d in sorted(deltas, key=lambda x: x.get('item_name', '')):
            row = QTreeWidgetItem()
            delta_type = d.get('delta_type', '')
            row.setText(0, type_labels.get(delta_type, delta_type))
            row.setForeground(0, type_colors.get(delta_type, QColor(TEXT)))
            row.setText(1, d.get('item_name', ''))
            old_q = d.get('old_quantity')
            new_q = d.get('new_quantity')
            row.setText(2, str(old_q) if old_q is not None else '-')
            row.setText(3, str(new_q) if new_q is not None else '-')
            row.setText(4, d.get('container') or '')
            self._delta_tree.addTopLevelItem(row)

    def cleanup(self):
        if self._delta_loader and self._delta_loader.isRunning():
            self._delta_loader.quit()
            self._delta_loader.wait(1000)


# ---------------------------------------------------------------------------
# History dialog
# ---------------------------------------------------------------------------

class InventoryHistoryDialog(QDialog):
    """Modal dialog showing import history with expandable deltas and value chart."""

    def __init__(self, *, nexus_client, parent=None):
        super().__init__(parent)
        self._nc = nexus_client
        self._loader: _HistoryLoader | None = None
        self._imports: list[dict] = []
        self._import_rows: list[_ImportRow] = []
        self._has_more = False
        self._active_filter: int = len(_TIME_FILTERS) - 1  # default "All"
        self._filter_btns: list[QPushButton] = []

        self.setWindowTitle("Import History")
        self.setMinimumSize(600, 450)
        self.resize(700, 560)
        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        self._build_ui()
        self._load_initial()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("Import History")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        title_row.addWidget(title)
        title_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        title_row.addWidget(close_btn)
        outer.addLayout(title_row)

        # Value chart (hidden initially)
        self._chart = _ValueChart()
        self._chart.hide()
        outer.addWidget(self._chart)

        # Time filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        filter_row.setContentsMargins(0, 0, 0, 0)
        for idx, (label, _td) in enumerate(_TIME_FILTERS):
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self._on_filter_clicked(i))
            self._filter_btns.append(btn)
            filter_row.addWidget(btn)
        filter_row.addStretch()
        self._update_filter_styles()
        outer.addLayout(filter_row)

        # Scroll area for imports
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(6)

        # Status
        self._status = QLabel("Loading...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 20px;")
        self._scroll_layout.addWidget(self._status)

        # Stretch
        self._scroll_layout.addStretch()

        scroll.setWidget(self._scroll_content)
        outer.addWidget(scroll, 1)

        # Load more button
        self._load_more_btn = QPushButton("Load More")
        self._load_more_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY}; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; padding: 6px 16px;
                font-size: 12px; border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {HOVER}; color: {TEXT};
            }}
        """)
        self._load_more_btn.clicked.connect(self._load_more)
        self._load_more_btn.hide()
        outer.addWidget(self._load_more_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def _get_since_iso(self) -> str | None:
        """Return ISO date string for the active filter, or None for all time."""
        _label, td = _TIME_FILTERS[self._active_filter]
        if td is None:
            return None
        return (datetime.now(timezone.utc) - td).isoformat()

    def _load_initial(self):
        self._status.setText("Loading...")
        self._status.show()
        self._loader = _HistoryLoader(
            self._nc, PAGE_SIZE, 0, load_value=True,
            since=self._get_since_iso())
        self._loader.finished.connect(self._on_initial_loaded)
        self._loader.start()

    def _on_initial_loaded(self, imports, value_history, error):
        self._loader = None

        if error or imports is None:
            self._status.setText(error or "Failed to load history.")
            return

        self._status.hide()

        # Value chart
        if value_history and len(value_history) >= 2:
            self._chart.set_data(value_history)
            self._chart.show()

        if not imports:
            self._status.setText("No imports yet.")
            self._status.show()
            return

        self._imports = imports
        self._has_more = len(imports) >= PAGE_SIZE
        self._populate_imports(imports)

        if self._has_more:
            self._load_more_btn.show()

    def _populate_imports(self, imports: list[dict]):
        # Insert before the stretch
        stretch_idx = self._scroll_layout.count() - 1

        for imp in imports:
            row = _ImportRow(imp, self._nc)
            self._import_rows.append(row)
            self._scroll_layout.insertWidget(stretch_idx, row)
            stretch_idx += 1

    def _load_more(self):
        self._load_more_btn.setEnabled(False)
        self._load_more_btn.setText("Loading...")
        offset = len(self._imports)
        self._loader = _HistoryLoader(
            self._nc, PAGE_SIZE, offset, load_value=False,
            since=self._get_since_iso())
        self._loader.finished.connect(self._on_more_loaded)
        self._loader.start()

    def _on_more_loaded(self, imports, _value_history, error):
        self._loader = None
        self._load_more_btn.setEnabled(True)
        self._load_more_btn.setText("Load More")

        if error or imports is None:
            return

        if not imports:
            self._has_more = False
            self._load_more_btn.hide()
            return

        self._imports.extend(imports)
        self._has_more = len(imports) >= PAGE_SIZE
        self._populate_imports(imports)

        if not self._has_more:
            self._load_more_btn.hide()

    def _on_filter_clicked(self, idx: int):
        if idx == self._active_filter:
            return
        self._active_filter = idx
        self._update_filter_styles()
        self._clear_imports()
        self._load_initial()

    def _update_filter_styles(self):
        for i, btn in enumerate(self._filter_btns):
            if i == self._active_filter:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT}; color: white;
                        border: none; border-radius: 4px;
                        padding: 2px 10px; font-size: 12px; font-weight: 600;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent; color: {TEXT_MUTED};
                        border: 1px solid {BORDER}; border-radius: 4px;
                        padding: 2px 10px; font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {HOVER}; color: {TEXT};
                    }}
                """)

    def _clear_imports(self):
        """Remove all current import rows from the scroll area."""
        for row in self._import_rows:
            row.cleanup()
            row.setParent(None)
            row.deleteLater()
        self._import_rows.clear()
        self._imports.clear()
        self._has_more = False
        self._load_more_btn.hide()
        self._chart.hide()

    def closeEvent(self, event):
        if self._loader and self._loader.isRunning():
            self._loader.quit()
            self._loader.wait(1000)
        for row in self._import_rows:
            row.cleanup()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # ISO format: 2025-01-15T12:30:00.000Z
        s = s.replace('Z', '+00:00')
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _format_chart_value(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}k"
    return f"{v:.0f}"


def _mini_badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-size: 11px; font-weight: 600;"
        f" background: transparent; border: none; padding: 0 3px;"
    )
    return lbl
