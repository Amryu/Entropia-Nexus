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
    "WaveEventArea":      QColor(218, 112, 214),  # orchid
}

_DEFAULT_COLOR = QColor(255, 255, 255)


def precompute_image_coords(locations: list[dict], pmap: dict, eu_ratio: float,
                            eu_tile_size: float):
    """Pre-compute image-space coords for all locations (pure math, thread-safe)."""
    px = pmap.get("X", 0) * eu_tile_size
    py = pmap.get("Y", 0) * eu_tile_size
    ph = pmap.get("Height", 0) * eu_tile_size

    for loc in locations:
        props = loc.get("Properties", {})
        shape = props.get("Shape")
        coords = props.get("Coordinates", {})
        data = props.get("Data", {})

        if shape == "Polygon":
            verts_raw = data.get("vertices", [])
            img_pts = []
            for j in range(0, len(verts_raw) - 1, 2):
                vx, vy = verts_raw[j], verts_raw[j + 1]
                if vx is None or vy is None:
                    continue
                ix = (vx - px) / eu_ratio
                iy = (ph - (vy - py)) / eu_ratio
                img_pts.append((ix, iy))
            loc["_img_polygon"] = img_pts
            if img_pts:
                xs = [p[0] for p in img_pts]
                ys = [p[1] for p in img_pts]
                loc["_img_bbox"] = (min(xs), min(ys), max(xs), max(ys))
            else:
                loc["_img_bbox"] = None
        elif shape == "Circle":
            dx = data.get("x") or 0
            dy = data.get("y") or 0
            dr = data.get("radius") or 0
            cx = (dx - px) / eu_ratio
            cy = (ph - (dy - py)) / eu_ratio
            rx = dr / eu_ratio
            loc["_img_center"] = (cx, cy)
            loc["_img_radius"] = rx
            loc["_img_bbox"] = (cx - rx, cy - rx, cx + rx, cy + rx)
        elif shape == "Rectangle":
            dx = data.get("x") or 0
            dy = data.get("y") or 0
            dw = data.get("width") or 0
            dh = data.get("height") or 0
            sx = (dx - px) / eu_ratio
            sy = (ph - (dy - py)) / eu_ratio
            ex = (dx + dw - px) / eu_ratio
            ey = (ph - (dy + dh - py)) / eu_ratio
            loc["_img_bbox"] = (min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
            loc["_img_rect"] = (sx, ey, ex - sx, sy - ey)
        else:
            lon = coords.get("Longitude")
            lat = coords.get("Latitude")
            if lon is not None and lat is not None:
                ix = (lon - px) / eu_ratio
                iy = (ph - (lat - py)) / eu_ratio
                loc["_img_pt"] = (ix, iy)
                loc["_img_bbox"] = (ix - 10, iy - 10, ix + 10, iy + 10)

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

        # Cached view transform params (sx, sy, xscale, yscale)
        self._vt: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)

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

        # Image coords are pre-computed by the background loader thread.
        # Only recompute if not already present (fallback for direct callers).
        if locations and "_img_bbox" not in locations[0] and "_img_pt" not in locations[0]:
            precompute_image_coords(locations, pmap, self._eu_ratio, self._eu_tile_size)

        # Initial view: fit entire image
        self._center_x = image.width() / 2
        self._center_y = image.height() / 2
        self._min_zoom = self._img_tile_size / max(image.width(), image.height())
        self._zoom = self._min_zoom

        self.update()

    def _precompute_image_coords(self, pmap: dict):
        """Pre-compute image-space coordinates and bounding boxes for all locations."""
        precompute_image_coords(self._locations, pmap, self._eu_ratio, self._eu_tile_size)

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
        if "Longitude" in coords and coords["Longitude"] is not None and coords["Latitude"] is not None:
            return self._entropia_to_image(coords["Longitude"], coords["Latitude"])
        if "x" in coords and coords["x"] is not None and coords["y"] is not None:
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
        """Locations passing the current layer filter or matching search/selection."""
        result = []
        selected_id = self._selected.get("Id") if self._selected else None
        for loc in self._locations:
            loc_id = loc.get("Id")
            # Always show selected location regardless of layer filter
            if selected_id is not None and loc_id == selected_id:
                result.append(loc)
                continue
            # Always show search results regardless of layer filter
            if self._search_ids and loc_id in self._search_ids:
                result.append(loc)
                continue
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

        # Pre-compute view transform for this frame (avoids recalc per location)
        w, h = self.width(), self.height()
        if h == 0:
            painter.end()
            return
        vis_h = self._img_tile_size / self._zoom
        vis_w = (w / h) * vis_h
        vt_sx = self._center_x - vis_w / 2
        vt_sy = self._center_y - vis_h / 2
        vt_xscale = w / vis_w
        vt_yscale = h / vis_h
        self._vt = (vt_sx, vt_sy, vt_xscale, vt_yscale)

        # Viewport bbox in image coords (for culling) with margin
        margin_img = 20 / vt_xscale  # ~20 widget pixels of margin
        vp_x0 = vt_sx - margin_img
        vp_y0 = vt_sy - margin_img
        vp_x1 = vt_sx + vis_w + margin_img
        vp_y1 = vt_sy + vis_h + margin_img

        # Clear cached widget polygons (stale after pan/zoom)
        for loc in self._locations:
            loc.pop("_wgt_polygon", None)

        # Draw locations
        filtered = self._filtered_locations()
        has_search = len(self._search_ids) > 0

        # First pass: areas (underneath)
        for loc in filtered:
            if loc.get("Properties", {}).get("Shape") not in _SHAPE_TYPES:
                continue
            # Viewport culling
            bbox = loc.get("_img_bbox")
            if bbox and (bbox[2] < vp_x0 or bbox[0] > vp_x1 or bbox[3] < vp_y0 or bbox[1] > vp_y1):
                continue
            self._draw_location(painter, loc, has_search)

        # Second pass: point locations (on top)
        for loc in filtered:
            if loc.get("Properties", {}).get("Shape") in _SHAPE_TYPES:
                continue
            bbox = loc.get("_img_bbox")
            if bbox and (bbox[2] < vp_x0 or bbox[0] > vp_x1 or bbox[3] < vp_y0 or bbox[1] > vp_y1):
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

        # Search filtering: dim non-results (except teleporters)
        if has_search and loc_id not in self._search_ids and not is_hovered and not is_selected and not is_tp:
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
        # Use pre-computed difficulty color for MobAreas, fallback to type color
        mob_rgb = loc.get("_mob_color")
        if mob_rgb and loc_type == "MobArea":
            base_color = QColor(mob_rgb[0], mob_rgb[1], mob_rgb[2])
        else:
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
        cached = loc.get("_img_pt")
        if not cached:
            return
        wx, wy = self._img_to_wgt(cached[0], cached[1])
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
        cached = loc.get("_img_pt")
        if not cached:
            return
        wx, wy = self._img_to_wgt(cached[0], cached[1])
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

    def _img_to_wgt(self, ix: float, iy: float) -> tuple[float, float]:
        """Fast image-to-widget transform using cached view params."""
        sx, sy, xs, ys = self._vt
        return ((ix - sx) * xs, (iy - sy) * ys)

    def _draw_shape(self, painter: QPainter, loc: dict, props: dict,
                    shape: str | None, loc_type: str, glow_extra: float = 0):
        """Draw the geometric shape for a location using pre-computed image coords."""
        if shape == "Circle":
            cached = loc.get("_img_center")
            if cached:
                cx, cy = self._img_to_wgt(cached[0], cached[1])
                r_img = loc.get("_img_radius", 0)
                # Convert radius from image to widget scale
                r = r_img * self._vt[2] + glow_extra
                painter.drawEllipse(QPointF(cx, cy), r, r)
        elif shape == "Rectangle":
            cached = loc.get("_img_rect")
            if cached:
                rx, ry, rw, rh = cached
                sx, sy = self._img_to_wgt(rx, ry)
                ex, ey = self._img_to_wgt(rx + rw, ry + rh)
                w = ex - sx
                h = ey - sy
                rect = QRectF(sx - glow_extra, sy - glow_extra,
                              w + glow_extra * 2, h + glow_extra * 2)
                painter.drawRect(rect)
        elif shape == "Polygon":
            # Use cached widget polygon if available (built once per frame)
            cached_poly = loc.get("_wgt_polygon")
            if cached_poly is None:
                img_pts = loc.get("_img_polygon", [])
                if not img_pts:
                    return
                points = []
                i2w = self._img_to_wgt
                for ix, iy in img_pts:
                    wx, wy = i2w(ix, iy)
                    points.append(QPointF(wx, wy))
                cached_poly = QPolygonF(points)
                loc["_wgt_polygon"] = cached_poly
            if cached_poly:
                painter.drawPolygon(cached_poly)
        else:
            # Point location
            cached = loc.get("_img_pt")
            if not cached:
                return
            wx, wy = self._img_to_wgt(cached[0], cached[1])
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
        # Ensure view transform is fresh for _img_to_wgt
        w, h = self.width(), self.height()
        if h == 0:
            return None
        vis_h = self._img_tile_size / self._zoom
        vis_w = (w / h) * vis_h
        vt_sx = self._center_x - vis_w / 2
        vt_sy = self._center_y - vis_h / 2
        self._vt = (vt_sx, vt_sy, w / vis_w, h / vis_h)

        filtered = self._filtered_locations()
        best: dict | None = None
        best_dist = float("inf")
        i2w = self._img_to_wgt

        for loc in filtered:
            props = loc.get("Properties", {})
            shape = props.get("Shape")

            if shape == "Circle":
                cached = loc.get("_img_center")
                if not cached:
                    continue
                cx, cy = i2w(cached[0], cached[1])
                r = loc.get("_img_radius", 0) * self._vt[2]
                d = math.hypot(wx - cx, wy - cy)
                if d <= r and r < best_dist:
                    best, best_dist = loc, r

            elif shape == "Rectangle":
                cached = loc.get("_img_rect")
                if not cached:
                    continue
                rx, ry, rw, rh = cached
                sx, sy = i2w(rx, ry)
                ex, ey = i2w(rx + rw, ry + rh)
                if min(sx, ex) <= wx <= max(sx, ex) and min(sy, ey) <= wy <= max(sy, ey):
                    area = abs((ex - sx) * (ey - sy))
                    if area < best_dist:
                        best, best_dist = loc, area

            elif shape == "Polygon":
                img_pts = loc.get("_img_polygon", [])
                if not img_pts:
                    continue
                points = [(i2w(ix, iy)) for ix, iy in img_pts]
                if self._point_in_polygon(wx, wy, points):
                    area = self._polygon_area(points)
                    if area < best_dist:
                        best, best_dist = loc, area

            else:
                cached = loc.get("_img_pt")
                if not cached:
                    continue
                px, py = i2w(cached[0], cached[1])
                buf = _HIT_BUFFER_TP if props.get("Type") == "Teleporter" else _HIT_BUFFER_OTHER
                d = math.hypot(wx - px, wy - py)
                if d <= buf:
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
        name = loc.get("_mob_display_name") or loc.get("Name", "")
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
