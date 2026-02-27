"""Reusable interactive map canvas — pan/zoom planet maps with location markers.

Can be embedded in the Maps page, wiki detail views, or the hunt overlay.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimeLine
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QPen, QBrush, QPolygonF, QFont,
)

from ..theme import ACCENT, BORDER, MAIN_DARK, TEXT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Entropia coordinate units per server tile
_EU_PER_TILE = 8192

_MAX_ZOOM = 5.0
_ZOOM_FACTOR = 1.1            # 10% per scroll tick
_DRAG_THRESHOLD = 3            # px — below this a release counts as click
_HIT_BUFFER_TP = 14            # px hit radius for teleporters
_HIT_BUFFER_OTHER = 10         # px hit radius for other point locations
_TP_RADIUS = 4                 # draw radius for teleporters (normal state)
_TP_RADIUS_ACTIVE = 8          # draw radius for teleporters (hovered/selected)
_LOC_HALF = 7                  # half-size for other location squares (14x14)
_ANIM_DURATION_MS = 300        # pan/zoom animation duration
_ANIM_FPS = 60                 # animation frame rate

# Type → QColor
_TYPE_COLORS: dict[str, QColor] = {
    "Teleporter":     QColor(0, 255, 255),    # aqua
    "LandArea":       QColor(0, 255, 0),      # green
    "ZoneArea":       QColor(0, 0, 255),      # blue
    "PvpLootArea":    QColor(255, 0, 0),      # red
    "PvpArea":        QColor(255, 165, 0),    # orange
    "MobArea":        QColor(255, 255, 0),    # yellow
    "Creature":       QColor(255, 255, 0),    # yellow
    "EventArea":      QColor(255, 255, 255),  # white
    "WaveEventArea":  QColor(128, 0, 128),    # purple
}

_DEFAULT_COLOR = QColor(255, 255, 255)

# Area types that use shape rendering
_SHAPE_TYPES = {"Circle", "Rectangle", "Polygon"}


# ---------------------------------------------------------------------------
# MapCanvas
# ---------------------------------------------------------------------------

class MapCanvas(QWidget):
    """Interactive planet map with pan, zoom, location markers, and hit detection."""

    location_hovered = pyqtSignal(object)   # dict | None
    location_clicked = pyqtSignal(object)   # dict | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Planet + image state
        self._planet: dict | None = None
        self._pixmap: QPixmap | None = None
        self._locations: list[dict] = []

        # Coordinate transform constants (set in set_planet)
        self._img_tile_size: float = 1.0
        self._eu_ratio: float = 1.0
        self._eu_tile_size: float = 1.0

        # View state
        self._center_x: float = 0.0   # image coords
        self._center_y: float = 0.0
        self._zoom: float = 0.1
        self._min_zoom: float = 0.1

        # Interaction state
        self._dragging = False
        self._drag_start: QPointF | None = None
        self._drag_center_start: tuple[float, float] = (0, 0)
        self._drag_moved = False

        # Selection / hover
        self._hovered: dict | None = None
        self._selected: dict | None = None

        # Layers
        self._visible_types: set[str] = {"Teleporter", "LandArea"}

        # Search results (empty = no search active)
        self._search_ids: set[int] = set()

        # Animation
        self._anim: QTimeLine | None = None
        self._anim_start: tuple[float, float, float] = (0, 0, 0)  # cx, cy, zoom
        self._anim_end: tuple[float, float, float] = (0, 0, 0)

        # Tooltip
        self._tooltip = QLabel(self)
        self._tooltip.setStyleSheet(
            f"background-color: rgba(0, 0, 0, 0.85);"
            f" color: {TEXT}; font-size: 11px; padding: 4px 8px;"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
        )
        self._tooltip.hide()

    # --- Public API ---

    def set_planet(self, planet: dict, image: QPixmap, locations: list[dict]):
        """Load a planet map with its background image and merged locations."""
        self._planet = planet
        self._pixmap = image
        self._locations = locations
        self._hovered = None
        self._selected = None
        self._search_ids = set()

        pmap = planet.get("Properties", {}).get("Map", {})
        map_w = pmap.get("Width", 1)
        img_w = image.width() if image and image.width() > 0 else 1

        self._img_tile_size = img_w / map_w
        self._eu_ratio = _EU_PER_TILE / self._img_tile_size
        self._eu_tile_size = self._img_tile_size * self._eu_ratio

        # Initial view: fit entire image
        self._center_x = image.width() / 2
        self._center_y = image.height() / 2
        self._min_zoom = self._img_tile_size / max(image.width(), image.height())
        self._zoom = self._min_zoom

        self.update()

    def set_selected(self, location_id: int | None):
        loc = self._find_by_id(location_id) if location_id is not None else None
        self._selected = loc
        self.update()

    def set_hovered(self, location_id: int | None):
        loc = self._find_by_id(location_id) if location_id is not None else None
        self._hovered = loc
        self.update()

    def set_layers(self, visible_types: set[str]):
        self._visible_types = visible_types
        self.update()

    def set_search_results(self, ids: set[int]):
        self._search_ids = ids
        self.update()

    def center_on(self, location: dict, zoom: float | None = None):
        """Pan (and optionally zoom) to center on a location."""
        props = location.get("Properties", {})
        coords = props.get("Coordinates") or props.get("Data")
        if not coords:
            return
        if "Longitude" in coords:
            ix, iy = self._entropia_to_image(coords["Longitude"], coords["Latitude"])
        elif "x" in coords:
            ix, iy = self._entropia_to_image(coords["x"], coords["y"])
        else:
            return
        self._center_x = ix
        self._center_y = iy
        if zoom is not None:
            self._zoom = max(self._min_zoom, min(_MAX_ZOOM, zoom))
        self._clamp_center()
        self.update()

    def center_on_smart(self, location: dict):
        """Animate pan to location, zoom in if needed but never zoom out."""
        ix, iy = self._location_to_image(location)
        if ix is None:
            return
        target_zoom = max(self._zoom, min(1.0, _MAX_ZOOM))
        self._animate_to(ix, iy, target_zoom)

    def pan_to(self, location: dict):
        """Animate pan to location without changing zoom."""
        ix, iy = self._location_to_image(location)
        if ix is None:
            return
        self._animate_to(ix, iy, self._zoom)

    def _location_to_image(self, location: dict) -> tuple[float | None, float | None]:
        """Extract image coordinates from a location dict."""
        props = location.get("Properties", {})
        coords = props.get("Coordinates") or props.get("Data")
        if not coords:
            return (None, None)
        if "Longitude" in coords:
            return self._entropia_to_image(coords["Longitude"], coords["Latitude"])
        if "x" in coords:
            return self._entropia_to_image(coords["x"], coords["y"])
        return (None, None)

    def _animate_to(self, ix: float, iy: float, zoom: float):
        """Smoothly animate center and zoom to target values."""
        # Stop any running animation
        if self._anim is not None:
            self._anim.stop()

        self._anim_start = (self._center_x, self._center_y, self._zoom)
        self._anim_end = (ix, iy, zoom)

        anim = QTimeLine(_ANIM_DURATION_MS, self)
        anim.setUpdateInterval(1000 // _ANIM_FPS)
        anim.setFrameRange(0, 100)
        anim.valueChanged.connect(self._on_anim_tick)
        anim.finished.connect(self._on_anim_done)
        self._anim = anim
        anim.start()

    def _on_anim_tick(self, progress: float):
        """Called each animation frame with progress 0.0 → 1.0."""
        # Ease-out: decelerate near the end
        t = progress * (2.0 - progress)
        sx, sy, sz = self._anim_start
        ex, ey, ez = self._anim_end
        self._center_x = sx + (ex - sx) * t
        self._center_y = sy + (ey - sy) * t
        self._zoom = sz + (ez - sz) * t
        self._clamp_center()
        self.update()

    def _on_anim_done(self):
        """Snap to exact target on animation completion."""
        ex, ey, ez = self._anim_end
        self._center_x = ex
        self._center_y = ey
        self._zoom = ez
        self._clamp_center()
        self._anim = None
        self.update()

    # --- Coordinate transforms ---

    def _entropia_to_image(self, ex: float, ey: float) -> tuple[float, float]:
        pmap = self._planet["Properties"]["Map"]
        px = pmap["X"] * self._eu_tile_size
        py = pmap["Y"] * self._eu_tile_size
        ph = pmap["Height"] * self._eu_tile_size
        return ((ex - px) / self._eu_ratio, (ph - (ey - py)) / self._eu_ratio)

    def _image_to_widget(self, ix: float, iy: float) -> tuple[float, float]:
        w, h = self.width(), self.height()
        if h == 0:
            return (0.0, 0.0)
        vis_h = self._img_tile_size / self._zoom
        vis_w = (w / h) * vis_h
        sx = self._center_x - vis_w / 2
        sy = self._center_y - vis_h / 2
        return ((ix - sx) * w / vis_w, (iy - sy) * h / vis_h)

    def _widget_to_image(self, wx: float, wy: float) -> tuple[float, float]:
        w, h = self.width(), self.height()
        if h == 0:
            return (0.0, 0.0)
        vis_h = self._img_tile_size / self._zoom
        vis_w = (w / h) * vis_h
        sx = self._center_x - vis_w / 2
        sy = self._center_y - vis_h / 2
        return (sx + (wx / w) * vis_w, sy + (wy / h) * vis_h)

    def _entropia_to_widget(self, ex: float, ey: float) -> tuple[float, float]:
        ix, iy = self._entropia_to_image(ex, ey)
        return self._image_to_widget(ix, iy)

    # --- Visible rect helpers ---

    def _visible_source_rect(self) -> QRectF:
        """Source rect in image coords for the current view."""
        w, h = self.width(), self.height()
        if h == 0:
            return QRectF()
        vis_h = self._img_tile_size / self._zoom
        vis_w = (w / h) * vis_h
        return QRectF(
            self._center_x - vis_w / 2,
            self._center_y - vis_h / 2,
            vis_w, vis_h,
        )

    # --- Filtered locations ---

    def _filtered_locations(self) -> list[dict]:
        """Locations passing the current layer filter."""
        result = []
        for loc in self._locations:
            t = loc.get("Properties", {}).get("Type", "")
            shape = loc.get("Properties", {}).get("Shape")
            # Map area type categories
            if shape in _SHAPE_TYPES:
                # Area: check area-type visibility
                if t in self._visible_types:
                    result.append(loc)
                # Also show if PvpLootArea and PvpArea is enabled
                elif t == "PvpLootArea" and "PvpArea" in self._visible_types:
                    result.append(loc)
                # "OtherArea" catch-all
                elif "OtherArea" in self._visible_types and t not in {
                    "LandArea", "MobArea", "PvpArea", "PvpLootArea",
                }:
                    result.append(loc)
            else:
                # Point location
                if t in self._visible_types:
                    result.append(loc)
                elif "OtherLocation" in self._visible_types and t != "Teleporter":
                    result.append(loc)
        return result

    # --- Rendering ---

    def paintEvent(self, event):
        if not self._pixmap or not self._planet:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Black background
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        # Draw planet image
        src = self._visible_source_rect()
        dest = QRectF(0, 0, self.width(), self.height())
        painter.drawPixmap(dest, self._pixmap, src)

        # Draw locations
        filtered = self._filtered_locations()
        has_search = len(self._search_ids) > 0

        # First pass: areas (underneath)
        for loc in filtered:
            if loc.get("Properties", {}).get("Shape") not in _SHAPE_TYPES:
                continue
            self._draw_location(painter, loc, has_search)

        # Second pass: point locations (on top)
        for loc in filtered:
            if loc.get("Properties", {}).get("Shape") in _SHAPE_TYPES:
                continue
            self._draw_location(painter, loc, has_search)

        painter.end()

    def _draw_location(self, painter: QPainter, loc: dict, has_search: bool):
        props = loc.get("Properties", {})
        loc_type = props.get("Type", "")
        loc_id = loc.get("Id")
        shape = props.get("Shape")
        is_hovered = self._hovered is not None and self._hovered.get("Id") == loc_id
        is_selected = self._selected is not None and self._selected.get("Id") == loc_id
        is_area = shape in _SHAPE_TYPES
        is_tp = loc_type == "Teleporter"

        # Search filtering: dim non-results
        if has_search and loc_id not in self._search_ids and not is_hovered and not is_selected:
            painter.setOpacity(0.25)
            painter.setPen(QPen(QColor(0xAA, 0xAA, 0xAA), 1.5))
            painter.setBrush(QBrush(QColor(0x88, 0x88, 0x88)))
            self._draw_shape(painter, loc, props, shape, loc_type)
            painter.setOpacity(1.0)
            return

        if is_area:
            self._draw_area(painter, loc, props, shape, loc_type, is_hovered, is_selected)
        elif is_tp:
            self._draw_teleporter(painter, loc, props, is_hovered, is_selected)
        else:
            self._draw_point(painter, loc, props, is_hovered, is_selected)

    def _draw_area(self, painter: QPainter, loc: dict, props: dict,
                   shape: str, loc_type: str, is_hovered: bool, is_selected: bool):
        """Draw an area shape matching the website's MapCanvas.svelte drawShape()."""
        base_color = _TYPE_COLORS.get(loc_type, _DEFAULT_COLOR)

        # Glow halo for selected/hovered (simulates canvas shadowBlur)
        if is_selected or is_hovered:
            glow_color = QColor(255, 255, 0) if is_selected else QColor(255, 165, 0)
            glow_opacity = 0.45 if is_selected else 0.3
            glow_width = 14 if is_selected else 8
            painter.setOpacity(glow_opacity)
            painter.setPen(QPen(glow_color, glow_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            self._draw_shape(painter, loc, props, shape, loc_type, glow_extra=4)

        # Fill at area opacity
        if is_selected:
            fill_opacity = 0.85
            fill_brush = QBrush(self._lighten(base_color, 0.5))
        elif is_hovered:
            fill_opacity = 0.6
            fill_brush = QBrush(self._lighten(base_color, 0.2))
        else:
            fill_opacity = 0.3
            fill_brush = QBrush(base_color)

        painter.setOpacity(fill_opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_brush)
        self._draw_shape(painter, loc, props, shape, loc_type)

        # Stroke at full opacity
        if is_selected:
            pen = QPen(self._lighten(base_color, 0.7), 5)
        elif is_hovered:
            pen = QPen(self._lighten(base_color, 0.4), 3)
        else:
            pen = QPen(base_color, 1)

        painter.setOpacity(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        self._draw_shape(painter, loc, props, shape, loc_type)

    def _draw_teleporter(self, painter: QPainter, loc: dict, props: dict,
                         is_hovered: bool, is_selected: bool):
        """Draw a teleporter point matching the website's styling."""
        coords = props.get("Coordinates", {})
        lon, lat = coords.get("Longitude"), coords.get("Latitude")
        if lon is None or lat is None:
            return
        wx, wy = self._entropia_to_widget(lon, lat)
        active = is_hovered or is_selected
        r = _TP_RADIUS_ACTIVE if active else _TP_RADIUS

        if is_selected:
            fill_color = QColor(255, 255, 0)     # yellow
            stroke_color = QColor(255, 165, 0)   # orange
            opacity = 1.0
            line_w = 4
        elif is_hovered:
            fill_color = QColor(255, 165, 0)     # orange
            stroke_color = QColor(255, 255, 0)   # yellow
            opacity = 0.85
            line_w = 4
        else:
            fill_color = QColor(0, 255, 255)     # aqua
            stroke_color = QColor(255, 0, 0)     # red
            opacity = 0.85
            line_w = 2

        painter.setOpacity(opacity)
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(wx, wy), r, r)
        # Stroke at full opacity
        painter.setOpacity(1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(stroke_color, line_w))
        painter.drawEllipse(QPointF(wx, wy), r, r)

    def _draw_point(self, painter: QPainter, loc: dict, props: dict,
                    is_hovered: bool, is_selected: bool):
        """Draw a non-teleporter point location matching the website's styling."""
        coords = props.get("Coordinates", {})
        lon, lat = coords.get("Longitude"), coords.get("Latitude")
        if lon is None or lat is None:
            return
        wx, wy = self._entropia_to_widget(lon, lat)
        half = _LOC_HALF

        if is_selected:
            fill_color = QColor(255, 255, 0)     # yellow
            stroke_color = QColor(255, 165, 0)   # orange
            opacity = 1.0
            line_w = 4
        elif is_hovered:
            fill_color = QColor(255, 165, 0)     # orange
            stroke_color = QColor(255, 255, 0)   # yellow
            opacity = 0.8
            line_w = 2
        else:
            fill_color = QColor(255, 255, 255)   # white
            stroke_color = QColor(0, 0, 0)       # black
            opacity = 0.7
            line_w = 1

        rect = QRectF(wx - half, wy - half, half * 2, half * 2)
        painter.setOpacity(opacity)
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        # Stroke at full opacity
        painter.setOpacity(1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(stroke_color, line_w))
        painter.drawRect(rect)

    def _draw_shape(self, painter: QPainter, loc: dict, props: dict,
                    shape: str | None, loc_type: str, glow_extra: float = 0):
        """Draw the geometric shape for a location."""
        if shape == "Circle":
            data = props.get("Data", {})
            cx, cy = self._entropia_to_widget(data.get("x", 0), data.get("y", 0))
            ox, _ = self._entropia_to_widget(
                data.get("x", 0) + data.get("radius", 0), data.get("y", 0)
            )
            r = abs(ox - cx) + glow_extra
            painter.drawEllipse(QPointF(cx, cy), r, r)
        elif shape == "Rectangle":
            data = props.get("Data", {})
            sx, sy = self._entropia_to_widget(data.get("x", 0), data.get("y", 0))
            ex, ey = self._entropia_to_widget(
                data.get("x", 0) + data.get("width", 0),
                data.get("y", 0) + data.get("height", 0),
            )
            w = ex - sx
            h = sy - ey  # Y is inverted
            rect = QRectF(sx - glow_extra, sy - h - glow_extra,
                          w + glow_extra * 2, h + glow_extra * 2)
            painter.drawRect(rect)
        elif shape == "Polygon":
            data = props.get("Data", {})
            verts_raw = data.get("vertices", [])
            points = []
            for i in range(0, len(verts_raw) - 1, 2):
                wx, wy = self._entropia_to_widget(verts_raw[i], verts_raw[i + 1])
                points.append(QPointF(wx, wy))
            if points:
                painter.drawPolygon(QPolygonF(points))
        else:
            # Point location
            coords = props.get("Coordinates", {})
            lon = coords.get("Longitude")
            lat = coords.get("Latitude")
            if lon is None or lat is None:
                return
            wx, wy = self._entropia_to_widget(lon, lat)
            if loc_type == "Teleporter":
                r = _TP_RADIUS + glow_extra
                painter.drawEllipse(QPointF(wx, wy), r, r)
            else:
                half = _LOC_HALF + glow_extra
                painter.drawRect(QRectF(wx - half, wy - half, half * 2, half * 2))

    @staticmethod
    def _lighten(color: QColor, pct: float) -> QColor:
        r = min(255, int(color.red() + (255 - color.red()) * pct))
        g = min(255, int(color.green() + (255 - color.green()) * pct))
        b = min(255, int(color.blue() + (255 - color.blue()) * pct))
        return QColor(r, g, b)

    # --- Hit detection ---

    def _hit_test(self, wx: float, wy: float) -> dict | None:
        """Find the location under the widget position *wx, wy*."""
        filtered = self._filtered_locations()
        best: dict | None = None
        best_dist = float("inf")

        for loc in filtered:
            props = loc.get("Properties", {})
            shape = props.get("Shape")

            if shape == "Circle":
                data = props.get("Data", {})
                cx, cy = self._entropia_to_widget(data.get("x", 0), data.get("y", 0))
                ox, _ = self._entropia_to_widget(
                    data.get("x", 0) + data.get("radius", 0), data.get("y", 0)
                )
                r = abs(ox - cx)
                d = math.hypot(wx - cx, wy - cy)
                if d <= r and r < best_dist:
                    best, best_dist = loc, r

            elif shape == "Rectangle":
                data = props.get("Data", {})
                sx, sy = self._entropia_to_widget(data.get("x", 0), data.get("y", 0))
                ex, ey = self._entropia_to_widget(
                    data.get("x", 0) + data.get("width", 0),
                    data.get("y", 0) + data.get("height", 0),
                )
                w_r = ex - sx
                h_r = sy - ey
                if sx <= wx <= sx + w_r and sy - h_r <= wy <= sy:
                    area = abs(w_r * h_r)
                    if area < best_dist:
                        best, best_dist = loc, area

            elif shape == "Polygon":
                data = props.get("Data", {})
                verts_raw = data.get("vertices", [])
                points = []
                for i in range(0, len(verts_raw) - 1, 2):
                    px, py = self._entropia_to_widget(verts_raw[i], verts_raw[i + 1])
                    points.append((px, py))
                if self._point_in_polygon(wx, wy, points):
                    area = self._polygon_area(points)
                    if area < best_dist:
                        best, best_dist = loc, area

            else:
                # Point location
                coords = props.get("Coordinates", {})
                lon = coords.get("Longitude")
                lat = coords.get("Latitude")
                if lon is None or lat is None:
                    continue
                px, py = self._entropia_to_widget(lon, lat)
                buf = _HIT_BUFFER_TP if props.get("Type") == "Teleporter" else _HIT_BUFFER_OTHER
                d = math.hypot(wx - px, wy - py)
                if d <= buf:
                    # Point locations get priority over areas — use negative dist
                    priority = -(1000 - d)
                    if priority < best_dist:
                        best, best_dist = loc, priority

        return best

    @staticmethod
    def _point_in_polygon(x: float, y: float, verts: list[tuple[float, float]]) -> bool:
        """Ray-casting algorithm."""
        n = len(verts)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = verts[i]
            xj, yj = verts[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    @staticmethod
    def _polygon_area(verts: list[tuple[float, float]]) -> float:
        """Shoelace formula for polygon area (used for overlap priority)."""
        n = len(verts)
        if n < 3:
            return float("inf")
        area = 0.0
        j = n - 1
        for i in range(n):
            area += (verts[j][0] + verts[i][0]) * (verts[j][1] - verts[i][1])
            j = i
        return abs(area / 2)

    # --- Mouse events ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = event.position()
            self._drag_center_start = (self._center_x, self._center_y)
            self._drag_moved = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self._dragging and self._drag_start is not None:
            dx = pos.x() - self._drag_start.x()
            dy = pos.y() - self._drag_start.y()
            if abs(dx) > _DRAG_THRESHOLD or abs(dy) > _DRAG_THRESHOLD:
                self._drag_moved = True
            # Convert pixel delta to image-coord delta
            w, h = self.width(), self.height()
            if h > 0:
                vis_h = self._img_tile_size / self._zoom
                vis_w = (w / h) * vis_h
                self._center_x = self._drag_center_start[0] - dx * (vis_w / w)
                self._center_y = self._drag_center_start[1] - dy * (vis_h / h)
                self._clamp_center()
            self.update()
        else:
            # Hover hit-test
            hit = self._hit_test(pos.x(), pos.y())
            if hit != self._hovered:
                old_id = self._hovered.get("Id") if self._hovered else None
                new_id = hit.get("Id") if hit else None
                if old_id != new_id:
                    self._hovered = hit
                    self.location_hovered.emit(hit)
                    self.update()

            if hit:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self._show_tooltip(hit, pos)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self._tooltip.hide()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_drag = self._drag_moved
            self._dragging = False
            self._drag_start = None
            self._drag_moved = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

            if not was_drag:
                hit = self._hit_test(event.position().x(), event.position().y())
                self._selected = hit
                self.location_clicked.emit(hit)
                self.update()

    def mouseDoubleClickEvent(self, event):
        """Reset to full planet view."""
        if self._pixmap:
            self._center_x = self._pixmap.width() / 2
            self._center_y = self._pixmap.height() / 2
            self._zoom = self._min_zoom
            self.update()

    def wheelEvent(self, event):
        if not self._pixmap:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return

        pos = event.position()
        # Image coords under the cursor before zoom
        img_before = self._widget_to_image(pos.x(), pos.y())

        # Apply zoom
        if delta > 0:
            self._zoom = min(_MAX_ZOOM, self._zoom * _ZOOM_FACTOR)
        else:
            self._zoom = max(self._min_zoom, self._zoom / _ZOOM_FACTOR)

        # Image coords under the cursor after zoom (with old center)
        img_after = self._widget_to_image(pos.x(), pos.y())

        # Adjust center so the point under the cursor stays fixed
        self._center_x += img_before[0] - img_after[0]
        self._center_y += img_before[1] - img_after[1]
        self._clamp_center()

        self.update()

    # --- Tooltip ---

    def _show_tooltip(self, loc: dict, pos: QPointF):
        name = loc.get("Name", "")
        loc_type = loc.get("Properties", {}).get("Type", "")
        label = f"{name}" if name else loc_type
        if name and loc_type:
            label = f"{name}  ({loc_type})"
        self._tooltip.setText(label)
        self._tooltip.adjustSize()

        # Position offset from cursor
        tx = int(pos.x()) + 16
        ty = int(pos.y()) - self._tooltip.height() - 8
        # Keep within widget bounds
        if tx + self._tooltip.width() > self.width():
            tx = int(pos.x()) - self._tooltip.width() - 8
        if ty < 0:
            ty = int(pos.y()) + 20
        self._tooltip.move(tx, ty)
        self._tooltip.show()
        self._tooltip.raise_()

    # --- Pan clamping ---

    def _clamp_center(self):
        """Keep the view center within the planet image bounds."""
        if not self._pixmap:
            return
        self._center_x = max(0.0, min(float(self._pixmap.width()), self._center_x))
        self._center_y = max(0.0, min(float(self._pixmap.height()), self._center_y))

    # --- Helpers ---

    def _find_by_id(self, loc_id: int) -> dict | None:
        for loc in self._locations:
            if loc.get("Id") == loc_id:
                return loc
        return None
