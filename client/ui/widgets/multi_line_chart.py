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


class MultiLineChart(QWidget):
    """Multi-line chart with legend, hover crosshair, and optional cumulative mode."""

    PADDING_LEFT = 70
    PADDING_RIGHT = 16
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
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ── Public API ────────────────────────────────────────────────────────

    def set_data(self, series: list[ChartSeries]) -> None:
        self._series = series or []
        self._hover_x = -1
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

    def _legend_height(self) -> int:
        visible = self._visible_series()
        if len(visible) <= 1:
            return 0
        # Estimate how many rows the legend needs
        avail_w = self.width() - self.PADDING_LEFT - self.PADDING_RIGHT
        if avail_w <= 0:
            return self.LEGEND_ROW_HEIGHT
        fm = QFontMetrics(QFont())
        x = 0
        rows = 1
        for s in visible:
            item_w = 14 + 4 + fm.horizontalAdvance(s.name) + 16
            if x + item_w > avail_w and x > 0:
                rows += 1
                x = 0
            x += item_w
        return rows * self.LEGEND_ROW_HEIGHT

    def _chart_rect(self) -> QRectF:
        legend_h = self._legend_height()
        return QRectF(
            self.PADDING_LEFT, self.PADDING_TOP,
            self.width() - self.PADDING_LEFT - self.PADDING_RIGHT,
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
        v_min, v_max = self._global_value_range()
        v_range = v_max - v_min or 1

        label_font = QFont()
        label_font.setPixelSize(10)
        painter.setFont(label_font)

        # Grid lines + Y-axis labels
        grid_pen = QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine)
        num_ticks = 5
        for i in range(num_ticks):
            frac = i / (num_ticks - 1)
            y = rect.bottom() - frac * rect.height()
            v = v_min + frac * v_range
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QPen(QColor(TEXT_MUTED)))
            label = self._format_value(v)
            painter.drawText(
                QRectF(0, y - 8, self.PADDING_LEFT - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        # X-axis date labels
        self._draw_x_labels(painter, rect, ts_min, ts_max, ts_range)

        # Draw series lines
        single = len(visible) == 1
        for s in visible:
            pts = self._prepared_data(s)
            if len(pts) < 2:
                continue

            points = [
                QPointF(
                    self._ts_to_x(ts, rect, ts_min, ts_range),
                    self._val_to_y(v, rect, v_min, v_range),
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

            # Area fill for single series
            if single:
                area = QPainterPath()
                area.moveTo(QPointF(points[0].x(), rect.bottom()))
                area.lineTo(points[0])
                area.connectPath(line_path)
                area.lineTo(QPointF(points[-1].x(), rect.bottom()))
                area.closeSubpath()
                fill_color = QColor(s.color)
                fill_color.setAlpha(30)
                painter.fillPath(area, QBrush(fill_color))
            painter.setPen(QPen(QColor(s.color), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line_path)

        # Hover crosshair + tooltip
        if 0 <= self._hover_x <= self.width():
            self._draw_hover(painter, visible, rect, ts_min, ts_range, v_min, v_range, label_font)

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
                    v_min: float, v_range: float, label_font: QFont):
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
            lines.append((s.name, s.color, nearest[1]))

            # Draw dot at nearest point
            px = self._ts_to_x(nearest[0], rect, ts_min, ts_range)
            py = self._val_to_y(nearest[1], rect, v_min, v_range)
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
            *(fm.horizontalAdvance(f"{name}: {self._format_value(val)}") + 28
              for name, _, val in lines),
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
        for name, color, val in lines:
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
        """Draw legend below the chart area."""
        visible = self._visible_series()
        if len(visible) <= 1:
            return

        legend_font = QFont()
        legend_font.setPixelSize(10)
        painter.setFont(legend_font)
        fm = QFontMetrics(legend_font)

        legend_top = chart_rect.bottom() + self.PADDING_BOTTOM
        avail_w = self.width() - self.PADDING_LEFT - self.PADDING_RIGHT
        x = self.PADDING_LEFT
        y = legend_top
        row_h = self.LEGEND_ROW_HEIGHT

        for s in visible:
            item_w = 14 + 4 + fm.horizontalAdvance(s.name) + 16
            if x - self.PADDING_LEFT + item_w > avail_w and x > self.PADDING_LEFT:
                x = self.PADDING_LEFT
                y += row_h

            # Color swatch
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(s.color)))
            swatch_y = y + (row_h - 10) / 2
            painter.drawRoundedRect(QRectF(x, swatch_y, 10, 10), 2, 2)

            # Name
            painter.setPen(QPen(QColor(TEXT_MUTED)))
            painter.drawText(
                QRectF(x + 14, y, item_w - 14, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                s.name,
            )
            x += item_w

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

    def mouseMoveEvent(self, event):
        new_x = event.position().x()
        if new_x != self._hover_x:
            self._hover_x = new_x
            self.update()

    def leaveEvent(self, event):
        if self._hover_x >= 0:
            self._hover_x = -1
            self.update()
