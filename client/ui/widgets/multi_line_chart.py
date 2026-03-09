"""Reusable QPainter-based multi-line chart with legend and hover tooltips."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPainterPath, QFont, QFontMetrics,
)

from ..theme import BORDER, ACCENT, TEXT, TEXT_MUTED, PRIMARY, DAMAGE_COLORS

# 12-color palette for chart series
CHART_COLORS: list[str] = list(DAMAGE_COLORS.values()) + [
    "#a078e8",  # purple
    "#e078a0",  # pink
    "#78d8a0",  # mint
]


@dataclasses.dataclass
class ChartSeries:
    """One data series for the chart."""
    name: str
    color: str
    data: list[tuple[int, float]]  # (unix_timestamp, value)
    visible: bool = True
    y_axis: str = 'left'                     # 'left' or 'right'
    dash_pattern: list[int] | None = None    # e.g. [6, 3] for dashed lines


class MultiLineChart(QWidget):
    """Multi-line chart with legend, hover crosshair, and optional cumulative mode."""

    PADDING_LEFT = 70
    PADDING_RIGHT = 16
    PADDING_RIGHT_DUAL = 70   # when a right Y-axis is active
    PADDING_TOP = 20
    PADDING_BOTTOM = 34
    LEGEND_ROW_HEIGHT = 22
    MIN_HEIGHT = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series: list[ChartSeries] = []
        self._cumulative = False
        self._smooth = False
        self._hover_x: float = -1
        self._legend_rects: list[tuple[QRectF, int]] = []  # (rect, series_index)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ── Public API ────────────────────────────────────────────────────────

    def set_data(self, series: list[ChartSeries]) -> None:
        self._series = series or []
        for s in self._series:
            s.visible = True
        self._hover_x = -1
        self._legend_rects = []
        self.update()

    def set_cumulative(self, cumulative: bool) -> None:
        if self._cumulative != cumulative:
            self._cumulative = cumulative
            self.update()

    def set_smooth(self, smooth: bool) -> None:
        """Enable smooth (monotone cubic) interpolation instead of step."""
        if self._smooth != smooth:
            self._smooth = smooth
            self.update()

    def clear(self) -> None:
        self._series = []
        self._hover_x = -1
        self.update()

    # ── Internals ─────────────────────────────────────────────────────────

    def _visible_series(self) -> list[ChartSeries]:
        return [s for s in self._series if s.visible and s.data]

    def _legend_series(self) -> list[ChartSeries]:
        """All series with data (shown in legend regardless of visibility)."""
        return [s for s in self._series if s.data]

    def _has_right_axis(self) -> bool:
        return any(s.y_axis == 'right' for s in self._visible_series())

    def _right_padding(self) -> int:
        return self.PADDING_RIGHT_DUAL if self._has_right_axis() else self.PADDING_RIGHT

    def _legend_height(self) -> int:
        legend = self._legend_series()
        if len(legend) <= 1:
            return 0
        # Estimate how many rows the legend needs
        avail_w = self.width() - self.PADDING_LEFT - self._right_padding()
        if avail_w <= 0:
            return self.LEGEND_ROW_HEIGHT
        fm = QFontMetrics(QFont())
        x = 0
        rows = 1
        for s in legend:
            item_w = 14 + 4 + fm.horizontalAdvance(s.name) + 16
            if x + item_w > avail_w and x > 0:
                rows += 1
                x = 0
            x += item_w
        return rows * self.LEGEND_ROW_HEIGHT

    def _chart_rect(self) -> QRectF:
        legend_h = self._legend_height()
        right_pad = self._right_padding()
        return QRectF(
            self.PADDING_LEFT, self.PADDING_TOP,
            self.width() - self.PADDING_LEFT - right_pad,
            self.height() - self.PADDING_TOP - self.PADDING_BOTTOM - legend_h,
        )

    def _prepared_data(self, series: ChartSeries) -> list[tuple[int, float]]:
        """Return (ts, value) pairs, optionally as cumulative sums."""
        pts = sorted(series.data, key=lambda p: p[0])
        if not self._cumulative:
            return pts
        cum = []
        total = 0.0
        for ts, v in pts:
            total += v
            cum.append((ts, total))
        return cum

    def _global_ts_range(self) -> tuple[int, int]:
        """Get the overall timestamp range across all visible series."""
        all_ts = []
        for s in self._visible_series():
            for ts, _ in s.data:
                all_ts.append(ts)
        if not all_ts:
            return (0, 1)
        mn, mx = min(all_ts), max(all_ts)
        if mn == mx:
            return (mn - 1, mx + 1)
        return (mn, mx)

    def _value_range_for_axis(self, axis: str) -> tuple[float, float]:
        """Get the value range for series on the given axis."""
        all_vals = []
        for s in self._visible_series():
            if s.y_axis != axis:
                continue
            for _, v in self._prepared_data(s):
                all_vals.append(v)
        if not all_vals:
            return (0.0, 1.0)
        mn, mx = min(all_vals), max(all_vals)
        if mn == mx:
            margin = max(abs(mn) * 0.1, 0.5)
            return (mn - margin, mx + margin)
        return (mn, mx)

    def _global_value_range(self) -> tuple[float, float]:
        """Get the overall value range across all visible series (after cumulative transform)."""
        all_vals = []
        for s in self._visible_series():
            for _, v in self._prepared_data(s):
                all_vals.append(v)
        if not all_vals:
            return (0.0, 1.0)
        mn, mx = min(all_vals), max(all_vals)
        if mn == mx:
            margin = max(abs(mn) * 0.1, 0.5)
            return (mn - margin, mx + margin)
        return (mn, mx)

    def _ts_to_x(self, ts: int, rect: QRectF, ts_min: int, ts_range: int) -> float:
        return rect.left() + ((ts - ts_min) / ts_range) * rect.width()

    def _val_to_y(self, val: float, rect: QRectF, v_min: float, v_range: float) -> float:
        return rect.bottom() - ((val - v_min) / v_range) * rect.height()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        visible = self._visible_series()
        if not visible:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(TEXT_MUTED)))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._chart_rect()
        ts_min, ts_max = self._global_ts_range()
        ts_range = ts_max - ts_min or 1

        has_right = self._has_right_axis()
        if has_right:
            v_min_l, v_max_l = self._value_range_for_axis('left')
            v_min_r, v_max_r = self._value_range_for_axis('right')
        else:
            v_min_l, v_max_l = self._global_value_range()
            v_min_r, v_max_r = v_min_l, v_max_l
        v_range_l = v_max_l - v_min_l or 1
        v_range_r = v_max_r - v_min_r or 1

        label_font = QFont()
        label_font.setPixelSize(10)
        painter.setFont(label_font)

        # Grid lines + left Y-axis labels
        grid_pen = QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine)
        num_ticks = 5
        for i in range(num_ticks):
            frac = i / (num_ticks - 1)
            y = rect.bottom() - frac * rect.height()
            v = v_min_l + frac * v_range_l
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QPen(QColor(TEXT_MUTED)))
            label = self._format_value(v)
            painter.drawText(
                QRectF(0, y - 8, self.PADDING_LEFT - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        # Right Y-axis labels
        if has_right:
            for i in range(num_ticks):
                frac = i / (num_ticks - 1)
                y = rect.bottom() - frac * rect.height()
                v = v_min_r + frac * v_range_r
                painter.setPen(QPen(QColor(TEXT_MUTED)))
                label = self._format_value(v)
                painter.drawText(
                    QRectF(rect.right() + 6, y - 8, self.PADDING_RIGHT_DUAL - 12, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    label,
                )

        # X-axis date labels
        self._draw_x_labels(painter, rect, ts_min, ts_max, ts_range)

        # Draw series lines
        left_series = [s for s in visible if s.y_axis == 'left']
        fill_single_left = len(left_series) == 1 and not has_right
        for s in visible:
            pts = self._prepared_data(s)
            if len(pts) < 2:
                continue

            # Pick the correct axis scale
            if s.y_axis == 'right':
                s_vmin, s_vrange = v_min_r, v_range_r
            else:
                s_vmin, s_vrange = v_min_l, v_range_l

            points = [
                QPointF(
                    self._ts_to_x(ts, rect, ts_min, ts_range),
                    self._val_to_y(v, rect, s_vmin, s_vrange),
                )
                for ts, v in pts
            ]

            # Build line path (step or smooth)
            line_path = QPainterPath()
            line_path.moveTo(points[0])
            if self._smooth and len(points) > 2:
                self._build_smooth_path(line_path, points)
            else:
                for p in points[1:]:
                    # Step: horizontal to new x, then vertical to new y
                    line_path.lineTo(QPointF(p.x(), line_path.currentPosition().y()))
                    line_path.lineTo(p)

            # Area fill for the left-axis series when it's the only left series
            if fill_single_left and s.y_axis == 'left':
                area = QPainterPath()
                area.moveTo(QPointF(points[0].x(), rect.bottom()))
                area.lineTo(points[0])
                area.connectPath(line_path)
                area.lineTo(QPointF(points[-1].x(), rect.bottom()))
                area.closeSubpath()
                fill_color = QColor(s.color)
                fill_color.setAlpha(30)
                painter.fillPath(area, QBrush(fill_color))

            # Line pen with optional dash pattern
            pen = QPen(QColor(s.color), 2)
            if s.dash_pattern:
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern(s.dash_pattern)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line_path)

        # Hover crosshair + tooltip
        if 0 <= self._hover_x <= self.width():
            self._draw_hover(
                painter, visible, rect, ts_min, ts_range,
                v_min_l, v_range_l, v_min_r, v_range_r,
                has_right, label_font,
            )

        # Legend
        self._draw_legend(painter, rect)

        painter.end()

    def _draw_x_labels(self, painter: QPainter, rect: QRectF,
                       ts_min: int, ts_max: int, ts_range: int):
        """Draw adaptive X-axis date labels."""
        avail_w = rect.width()
        label_w = 60
        num_labels = max(2, min(7, int(avail_w / label_w)))

        painter.setPen(QPen(QColor(TEXT_MUTED)))
        for i in range(num_labels):
            frac = i / (num_labels - 1)
            ts = int(ts_min + frac * ts_range)
            x = rect.left() + frac * rect.width()
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            # Choose format based on time span
            if ts_range < 2 * 86400:
                label = dt.strftime("%H:%M")
            elif ts_range < 90 * 86400:
                label = dt.strftime("%b %d")
            else:
                label = dt.strftime("%b '%y")
            painter.drawText(
                QRectF(x - 30, rect.bottom() + 4, 60, 20),
                Qt.AlignmentFlag.AlignCenter, label,
            )

    def _draw_hover(self, painter: QPainter, visible: list[ChartSeries],
                    rect: QRectF, ts_min: int, ts_range: int,
                    v_min_l: float, v_range_l: float,
                    v_min_r: float, v_range_r: float,
                    has_right: bool, label_font: QFont):
        """Draw vertical crosshair and tooltip at hover position."""
        mx = self._hover_x
        if mx < rect.left() or mx > rect.right():
            return

        # Vertical line
        painter.setPen(QPen(QColor(TEXT_MUTED), 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(mx, rect.top()), QPointF(mx, rect.bottom()))

        # Find hovered timestamp
        hover_ts = ts_min + ((mx - rect.left()) / rect.width()) * ts_range

        # Collect nearest values for each series
        lines = []
        for s in visible:
            pts = self._prepared_data(s)
            if not pts:
                continue
            # Find nearest point by timestamp
            nearest = min(pts, key=lambda p: abs(p[0] - hover_ts))
            lines.append((s.name, s.color, nearest[1], s.y_axis))

            # Draw dot at nearest point (using correct axis scale)
            if s.y_axis == 'right':
                s_vmin, s_vrange = v_min_r, v_range_r
            else:
                s_vmin, s_vrange = v_min_l, v_range_l
            px = self._ts_to_x(nearest[0], rect, ts_min, ts_range)
            py = self._val_to_y(nearest[1], rect, s_vmin, s_vrange)
            painter.setPen(QPen(QColor(s.color), 1))
            painter.setBrush(QBrush(QColor(s.color)))
            painter.drawEllipse(QPointF(px, py), 4, 4)

        if not lines:
            return

        # Draw timestamp label
        hover_dt = datetime.fromtimestamp(int(hover_ts), tz=timezone.utc)
        if ts_range < 2 * 86400:
            ts_label = hover_dt.strftime("%b %d %H:%M")
        else:
            ts_label = hover_dt.strftime("%b %d, %Y")

        # Build tooltip
        fm = QFontMetrics(label_font)
        row_h = fm.height() + 2
        header_h = row_h + 4
        tw = max(
            fm.horizontalAdvance(ts_label) + 16,
            *(fm.horizontalAdvance(f"{name}: {self._format_value(val)}") + 30
              for name, _, val, _ in lines),
        )
        th = header_h + row_h * len(lines) + 8

        tx = mx + 12
        ty = rect.top() + 10
        if tx + tw > self.width() - 4:
            tx = mx - tw - 12
        if ty + th > rect.bottom():
            ty = rect.bottom() - th

        tooltip_rect = QRectF(tx, ty, tw, th)
        painter.setPen(QPen(QColor(BORDER)))
        painter.setBrush(QBrush(QColor(PRIMARY)))
        painter.drawRoundedRect(tooltip_rect, 4, 4)

        # Timestamp header
        painter.setPen(QPen(QColor(TEXT_MUTED)))
        painter.drawText(
            QRectF(tx + 8, ty + 4, tw - 16, row_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            ts_label,
        )

        # Series values
        y_off = ty + header_h
        for name, color, val, _ in lines:
            # Color swatch
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawRect(QRectF(tx + 8, y_off + (row_h - 8) / 2, 8, 8))
            # Text
            painter.setPen(QPen(QColor(TEXT)))
            painter.drawText(
                QRectF(tx + 22, y_off, tw - 30, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{name}: {self._format_value(val)}",
            )
            y_off += row_h

    def _draw_legend(self, painter: QPainter, chart_rect: QRectF):
        """Draw legend below the chart area. All series shown; hidden ones dimmed."""
        legend = self._legend_series()
        if len(legend) <= 1:
            self._legend_rects = []
            return

        legend_font = QFont()
        legend_font.setPixelSize(10)
        painter.setFont(legend_font)
        fm = QFontMetrics(legend_font)

        legend_top = chart_rect.bottom() + self.PADDING_BOTTOM
        right_pad = self._right_padding()
        avail_w = self.width() - self.PADDING_LEFT - right_pad
        x = self.PADDING_LEFT
        y = legend_top
        row_h = self.LEGEND_ROW_HEIGHT

        rects: list[tuple[QRectF, int]] = []

        for idx, s in enumerate(legend):
            series_idx = self._series.index(s)
            item_w = 14 + 4 + fm.horizontalAdvance(s.name) + 16
            if x - self.PADDING_LEFT + item_w > avail_w and x > self.PADDING_LEFT:
                x = self.PADDING_LEFT
                y += row_h

            hit_rect = QRectF(x, y, item_w, row_h)
            rects.append((hit_rect, series_idx))

            # Color swatch (dimmed if hidden)
            swatch_color = QColor(s.color)
            if not s.visible:
                swatch_color.setAlpha(60)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(swatch_color))
            swatch_y = y + (row_h - 10) / 2
            painter.drawRoundedRect(QRectF(x, swatch_y, 10, 10), 2, 2)

            # Name (dimmed + strikethrough if hidden)
            name_color = QColor(TEXT_MUTED)
            if not s.visible:
                name_color.setAlpha(100)
            painter.setPen(QPen(name_color))
            if not s.visible:
                strike_font = QFont(legend_font)
                strike_font.setStrikeOut(True)
                painter.setFont(strike_font)
            painter.drawText(
                QRectF(x + 14, y, item_w - 14, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                s.name,
            )
            if not s.visible:
                painter.setFont(legend_font)
            x += item_w

        self._legend_rects = rects

    @staticmethod
    def _format_value(v: float) -> str:
        if abs(v) >= 1000:
            return f"{v:,.1f}"
        if abs(v) >= 1:
            return f"{v:.2f}"
        return f"{v:.4f}"

    @staticmethod
    def _build_smooth_path(path: QPainterPath, points: list[QPointF]) -> None:
        """Build a monotone cubic spline through *points* (Fritsch-Carlson).

        Guarantees monotonicity on each axis segment — no overshoot.
        Tension is fixed at ~0.5 (Catmull-Rom feel).
        """
        n = len(points)
        if n < 2:
            return

        # Compute tangent slopes (monotone piecewise cubic Hermite)
        dx = [points[i + 1].x() - points[i].x() for i in range(n - 1)]
        dy = [points[i + 1].y() - points[i].y() for i in range(n - 1)]
        slopes = [dy[i] / dx[i] if dx[i] != 0 else 0.0 for i in range(n - 1)]

        # Tangent at each point (Fritsch-Carlson)
        m = [0.0] * n
        m[0] = slopes[0]
        m[-1] = slopes[-1]
        for i in range(1, n - 1):
            if slopes[i - 1] * slopes[i] <= 0:
                m[i] = 0.0
            else:
                m[i] = (slopes[i - 1] + slopes[i]) / 2

        # Ensure monotonicity
        for i in range(n - 1):
            if slopes[i] == 0:
                m[i] = 0.0
                m[i + 1] = 0.0
            else:
                alpha = m[i] / slopes[i]
                beta = m[i + 1] / slopes[i]
                mag = (alpha ** 2 + beta ** 2) ** 0.5
                if mag > 3:
                    tau = 3 / mag
                    m[i] = tau * alpha * slopes[i]
                    m[i + 1] = tau * beta * slopes[i]

        # Build cubic bezier segments
        for i in range(n - 1):
            d = dx[i] / 3
            cp1 = QPointF(points[i].x() + d, points[i].y() + m[i] * d)
            cp2 = QPointF(points[i + 1].x() - d, points[i + 1].y() - m[i + 1] * d)
            path.cubicTo(cp1, cp2, points[i + 1])

    # ── Mouse ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._legend_rects:
            pos = event.position()
            for rect, series_idx in self._legend_rects:
                if rect.contains(pos):
                    # Don't allow hiding the last visible series
                    visible_count = sum(1 for s in self._series if s.visible and s.data)
                    s = self._series[series_idx]
                    if s.visible and visible_count <= 1:
                        break
                    s.visible = not s.visible
                    self.update()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        # Change cursor when hovering over legend items
        over_legend = any(r.contains(pos) for r, _ in self._legend_rects)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if over_legend
            else Qt.CursorShape.ArrowCursor
        )
        new_x = pos.x()
        if new_x != self._hover_x:
            self._hover_x = new_x
            self.update()

    def leaveEvent(self, event):
        if self._hover_x >= 0:
            self._hover_x = -1
            self.update()
