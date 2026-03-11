"""
Port of Scaleform GFx font rasterization pipeline to Python.

Faithfully reimplements two key Scaleform components:
  1. GFxGlyphFitter  — vertex grid-fitting (Y-axis snapping)
  2. GRasterizer     — AGG-based scanline rasterizer with 256x subpixel precision

Combined with FreeType outline extraction (via freetype-py), this produces
glyph bitmaps that closely match Scaleform's actual rendering output.

Pipeline:
    FreeType outline (at FontHeight=1024)
      → Flatten Bezier curves to line segments
      → Scale to nominal coordinate space (nominalSize / 1024)
      → GlyphFitter: detect edge events, build lerp ramp, snap Y vertices
      → Rasterizer: MoveTo/LineTo → cell accumulation → scanline sweep → 8-bit AA
      → numpy array / PIL Image

Reference C++ sources:
    GFxGlyphFitter.h/cpp  — Scaleform/Src/GFxPlayer/
    GRasterizer.h/cpp      — Scaleform/Src/GRenderer/
    GFxGlyphCache.cpp      — rasterizeAndPack() integration
    GFxFontProviderFT2.cpp — FreeType outline loading
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import freetype
    HAS_FREETYPE = True
except ImportError:
    HAS_FREETYPE = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ---------------------------------------------------------------------------
# GlyphFitter — port of GFxGlyphFitter
# ---------------------------------------------------------------------------

DIR_CW = 1
DIR_CCW = 2
FIT_X = 1
FIT_Y = 2


class GlyphFitter:
    """
    Port of Scaleform's GFxGlyphFitter.

    Performs Y-axis vertex grid-fitting for "Anti-alias for readability" mode.
    Detects edge events (local min/max) in glyph contours, builds a piecewise-
    linear snapping ramp, then snaps vertices to pixel boundaries.
    """

    def __init__(self, nominal_font_height: int = 1024):
        self.nominal_font_height = nominal_font_height
        self.contours: list[list[tuple[int, int]]] = []  # list of vertex lists
        self.min_x = 32767
        self.min_y = 32767
        self.max_x = -32767
        self.max_y = -32767
        self.direction = DIR_CW
        self.units_per_pixel_x = 1
        self.units_per_pixel_y = 1
        self.snapped_height = 0
        self._events: bytearray = bytearray()
        self._lerp_pairs: list[tuple[int, int]] = []
        self._lerp_ramp_x: list[int] = []
        self._lerp_ramp_y: list[int] = []

    def clear(self):
        self.contours = []
        self._lerp_ramp_x = []
        self._lerp_ramp_y = []

    def move_to(self, x: int, y: int):
        """Start a new contour."""
        self.contours.append([(int(x), int(y))])

    def line_to(self, x: int, y: int):
        """Add a vertex to the current contour (skips duplicates)."""
        ix, iy = int(x), int(y)
        px, py = self.contours[-1][-1]
        if ix != px or iy != py:
            self.contours[-1].append((ix, iy))

    def _remove_duplicate_closures(self):
        for c in self.contours:
            if len(c) > 2:
                if c[0][0] == c[-1][0] and c[0][1] == c[-1][1]:
                    c.pop()

    def _compute_bounds(self):
        min_x = 32767
        min_y = 32767
        max_x = -32767
        max_y = -32767

        self.min_x = 32767
        self.min_y = 32767
        self.max_x = -32767
        self.max_y = -32767

        for c in self.contours:
            if len(c) > 2:
                v1x, v1y = c[-1]
                total = 0
                for v2x, v2y in c:
                    if v2x < min_x:
                        min_x = v2x
                    if v2y < min_y:
                        min_y = v2y
                    if v2x > max_x:
                        max_x = v2x
                    if v2y > max_y:
                        max_y = v2y
                    total += v1x * v2y - v1y * v2x
                    v1x, v1y = v2x, v2y

                if (min_x < self.min_x or min_y < self.min_y or
                        max_x > self.max_x or max_y > self.max_y):
                    self.min_x = min_x
                    self.min_y = min_y
                    self.max_x = max_x
                    self.max_y = max_y
                    self.direction = DIR_CCW if total > 0 else DIR_CW

    def _detect_events(self, fit_dir: int):
        min_coord = self.min_x if fit_dir == FIT_X else self.min_y
        size = (self.max_x - self.min_x + 1) if fit_dir == FIT_X else (self.max_y - self.min_y + 1)
        self._events = bytearray(size)

        for c in self.contours:
            n = len(c)
            if n <= 2:
                continue

            self._events[0] = DIR_CW | DIR_CCW

            for j in range(n):
                i1 = j
                i2 = (j + 1) % n
                i3 = (j + 2) % n
                v1x, v1y = c[i1]
                v2x, v2y = c[i2]
                v3x, v3y = c[i3]

                if fit_dir == FIT_X:
                    # Swap and negate (note: C++ has a copy-paste bug here, but
                    # FitX is never called so we skip it entirely in practice)
                    v1x, v1y = -v1y, v1x
                    v2x, v2y = -v2y, v2x
                    v3x, v3y = -v3y, v3x

                done = False
                if ((v1y >= v2y and v3y >= v2y) or
                        (v1y <= v2y and v3y <= v2y)):
                    # Local min or max
                    idx = v2y - min_coord
                    if 0 <= idx < size:
                        if v1x <= v2x <= v3x:
                            self._events[idx] |= DIR_CCW if self.direction == DIR_CW else DIR_CW
                            done = True
                        if v1x >= v2x >= v3x:
                            self._events[idx] |= DIR_CW if self.direction == DIR_CW else DIR_CCW
                            done = True

                if not done:
                    if v1y == v2y:
                        # Flat shoulder
                        idx = v2y - min_coord
                        if 0 <= idx < size:
                            if v1x < v2x:
                                self._events[idx] |= DIR_CCW if self.direction == DIR_CW else DIR_CW
                            if v1x > v2x:
                                self._events[idx] |= DIR_CW if self.direction == DIR_CW else DIR_CCW

    def _snap_to_pixel(self, x: int, units_per_pixel: int) -> int:
        # C++ integer division truncates toward zero; Python // floors.
        return _c_div(x + self.snapped_height, units_per_pixel) * units_per_pixel - self.snapped_height

    def _compute_lerp_ramp(self, fit_dir: int, units_per_pixel: int,
                           middle: int, lower_case_top: int, upper_case_top: int):
        lerp_pairs: list[tuple[int, int]] = []
        sentinel = -self.snapped_height * 4
        lerp_pairs.append((sentinel, sentinel))

        prev = -32767
        top1 = lower_case_top
        top2 = upper_case_top
        top1s = self._snap_to_pixel(top1 + units_per_pixel, units_per_pixel)
        top2s = self._snap_to_pixel(top2 + units_per_pixel, units_per_pixel)
        min_coord = self.min_x if fit_dir == FIT_X else self.min_y
        min_dist = units_per_pixel + 1

        for i in range(len(self._events)):
            y = i + min_coord
            event = self._events[i]

            if y <= middle or fit_dir == FIT_X:
                # Snap to bottom
                if event & DIR_CW:
                    if y > prev + min_dist:
                        snapped = self._snap_to_pixel(y + units_per_pixel // 2 + 1, units_per_pixel)
                        if lerp_pairs[-1][1] != snapped:
                            lerp_pairs.append((y, snapped))
                        prev = y
            else:
                # Snap to top
                if event & DIR_CCW:
                    done = False
                    if top2:
                        if top2 <= y < top2 + min_dist:
                            if (y <= prev + min_dist or
                                    lerp_pairs[-1][1] + units_per_pixel >= top2s):
                                lerp_pairs.pop()
                            lerp_pairs.append((y, top2s))
                            prev = y
                            done = True
                        elif top1 <= y < top1 + min_dist:
                            if (y <= prev + min_dist or
                                    lerp_pairs[-1][1] + units_per_pixel >= top1s):
                                lerp_pairs.pop()
                            lerp_pairs.append((y, top1s))
                            prev = y
                            done = True
                    if not done:
                        snapped = self._snap_to_pixel(y + units_per_pixel, units_per_pixel)
                        if (y <= prev + min_dist or
                                lerp_pairs[-1][1] + units_per_pixel >= snapped):
                            lerp_pairs.pop()
                        lerp_pairs.append((y, snapped))
                        prev = y

        sentinel_end = self.snapped_height * 4
        lerp_pairs.append((sentinel_end, sentinel_end))

        ramp = [0] * len(self._events)
        v1x, v1y = lerp_pairs[0]
        v2x, v2y = lerp_pairs[1]
        top_idx = 2

        for i in range(len(self._events)):
            y = i + min_coord
            if y >= v2x and top_idx < len(lerp_pairs):
                v1x, v1y = v2x, v2y
                v2x, v2y = lerp_pairs[top_idx]
                top_idx += 1
            denom = v2x - v1x
            if denom != 0:
                # Must use C-style integer division to match C++ behavior exactly:
                # C++: v1.y + (y - v1.x) * (v2.y - v1.y) / (v2.x - v1.x)
                # The multiplication and division are integer arithmetic.
                ramp[i] = v1y + _c_div((y - v1x) * (v2y - v1y), denom) - min_coord
            else:
                ramp[i] = v1y - min_coord

        if fit_dir == FIT_X:
            self._lerp_ramp_x = ramp
        else:
            self._lerp_ramp_y = ramp

    def snap_vertex(self, x: int, y: int) -> tuple[int, int]:
        """Apply lerp ramp snapping to a vertex."""
        i = y - self.min_y
        if 0 <= i < len(self._lerp_ramp_y):
            y = self._lerp_ramp_y[i] + self.min_y

        i = x - self.min_x
        if 0 <= i < len(self._lerp_ramp_x):
            x = self._lerp_ramp_x[i] + self.min_x

        return x, y

    def compute_top_y(self) -> int:
        self._compute_bounds()
        return self.max_y

    def fit_glyph(self, height_in_pixels: int, width_in_pixels: int,
                  lower_case_top: int, upper_case_top: int):
        """
        Main entry point. Fits glyph vertices to pixel grid.

        Args:
            height_in_pixels: Target glyph height in pixels (e.g. 9)
            width_in_pixels: Target width (0 for AutoFit text — Y-only fitting)
            lower_case_top: Top of lowercase 'x'/'z' in nominal coords
            upper_case_top: Top of uppercase 'H' in nominal coords
        """
        self.units_per_pixel_x = (self.nominal_font_height // width_in_pixels
                                  if width_in_pixels else 1)
        self.units_per_pixel_y = (self.nominal_font_height // height_in_pixels
                                  if height_in_pixels else 1)
        self.snapped_height = (self.nominal_font_height // self.units_per_pixel_y
                               * self.units_per_pixel_y)

        if height_in_pixels or width_in_pixels:
            self._remove_duplicate_closures()
            self._compute_bounds()
            if height_in_pixels and self.max_y > self.min_y:
                self._detect_events(FIT_Y)
                self._compute_lerp_ramp(
                    FIT_Y, self.units_per_pixel_y,
                    self.min_y + (self.max_y - self.min_y) // 3,
                    lower_case_top, upper_case_top)
            if width_in_pixels and self.max_y > self.min_y:
                self._detect_events(FIT_X)
                self._compute_lerp_ramp(
                    FIT_X, self.units_per_pixel_x,
                    self.min_x + (self.max_x - self.min_x) // 3,
                    0, 0)


# ---------------------------------------------------------------------------
# ScanlineRasterizer — port of GRasterizer
# ---------------------------------------------------------------------------

SUBPIXEL_SHIFT = 8
SUBPIXEL_SCALE = 1 << SUBPIXEL_SHIFT   # 256
SUBPIXEL_MASK = SUBPIXEL_SCALE - 1     # 255

AA_SHIFT = 8
AA_SCALE = 1 << AA_SHIFT               # 256
AA_MASK = AA_SCALE - 1                 # 255
AA_SCALE2 = AA_SCALE * 2
AA_MASK2 = AA_SCALE2 - 1


class ScanlineRasterizer:
    """
    Port of Scaleform's GRasterizer (derived from Anti-Grain Geometry).

    Uses 256x subpixel precision, cell-based coverage accumulation,
    and NonZero fill rule by default.
    """

    FILL_NON_ZERO = 0
    FILL_EVEN_ODD = 1

    def __init__(self):
        self.fill_rule = self.FILL_NON_ZERO
        self.gamma = 1.0
        self._gamma_lut: list[int] = []
        self._cells: list[list[int]] = []  # each: [x, y, cover, area]
        self._curr_cell = [0x7FFFFFFF, 0x7FFFFFFF, 0, 0]  # x, y, cover, area
        self._sorted_cells: list[list[int]] = []
        self._sorted_ys: list[tuple[int, int]] = []  # (start, count)
        self.min_x = 0x7FFFFFFF
        self.min_y = 0x7FFFFFFF
        self.max_x = -0x7FFFFFFF
        self.max_y = -0x7FFFFFFF
        self._start_x = 0
        self._start_y = 0
        self._last_x = 0
        self._last_y = 0

    def clear(self):
        self._cells = []
        self._sorted_cells = []
        self._sorted_ys = []
        self._curr_cell = [0x7FFFFFFF, 0x7FFFFFFF, 0, 0]
        self.min_x = 0x7FFFFFFF
        self.min_y = 0x7FFFFFFF
        self.max_x = -0x7FFFFFFF
        self.max_y = -0x7FFFFFFF
        self._start_x = 0
        self._start_y = 0
        self._last_x = 0
        self._last_y = 0

    def set_gamma(self, g: float):
        if g == 1.0:
            self._gamma_lut = []
        else:
            self._gamma_lut = [
                int(pow(i / AA_MASK, g) * AA_MASK + 0.5)
                for i in range(AA_SCALE)
            ]
        self.gamma = g

    def move_to(self, x: float, y: float):
        sx = int(x * SUBPIXEL_SCALE)
        sy = int(y * SUBPIXEL_SCALE)
        self._start_x = sx
        self._start_y = sy
        self._last_x = sx
        self._last_y = sy

    def line_to(self, x: float, y: float):
        xi = int(x * SUBPIXEL_SCALE)
        yi = int(y * SUBPIXEL_SCALE)
        self._line(self._last_x, self._last_y, xi, yi)
        self._last_x = xi
        self._last_y = yi

    def close_polygon(self):
        self._line(self._last_x, self._last_y, self._start_x, self._start_y)
        self._last_x = self._start_x
        self._last_y = self._start_y

    def _set_curr_cell(self, x: int, y: int):
        cc = self._curr_cell
        if cc[0] != x or cc[1] != y:
            if cc[2] or cc[3]:  # cover or area
                self._cells.append(list(cc))
            cc[0] = x
            cc[1] = y
            cc[2] = 0
            cc[3] = 0

    def _hor_line(self, ey: int, x1: int, y1: int, x2: int, y2: int):
        ex1 = x1 >> SUBPIXEL_SHIFT
        ex2 = x2 >> SUBPIXEL_SHIFT
        fx1 = x1 & SUBPIXEL_MASK
        fx2 = x2 & SUBPIXEL_MASK

        if y1 == y2:
            self._set_curr_cell(ex2, ey)
            return

        if ex1 == ex2:
            delta = y2 - y1
            self._curr_cell[2] += delta
            self._curr_cell[3] += (fx1 + fx2) * delta
            return

        p = (SUBPIXEL_SCALE - fx1) * (y2 - y1)
        first = SUBPIXEL_SCALE
        incr = 1
        dx = x2 - x1

        if dx < 0:
            p = fx1 * (y2 - y1)
            first = 0
            incr = -1
            dx = -dx

        delta = _c_div(p, dx)
        mod = _c_mod(p, dx)
        if mod < 0:
            delta -= 1
            mod += dx

        self._curr_cell[2] += delta
        self._curr_cell[3] += (fx1 + first) * delta

        ex1 += incr
        self._set_curr_cell(ex1, ey)
        y1 += delta

        if ex1 != ex2:
            p = SUBPIXEL_SCALE * (y2 - y1 + delta)
            lift = _c_div(p, dx)
            rem = _c_mod(p, dx)
            if rem < 0:
                lift -= 1
                rem += dx
            mod -= dx

            while ex1 != ex2:
                delta = lift
                mod += rem
                if mod >= 0:
                    mod -= dx
                    delta += 1
                self._curr_cell[2] += delta
                self._curr_cell[3] += SUBPIXEL_SCALE * delta
                y1 += delta
                ex1 += incr
                self._set_curr_cell(ex1, ey)

        delta = y2 - y1
        self._curr_cell[2] += delta
        self._curr_cell[3] += (fx2 + SUBPIXEL_SCALE - first) * delta

    def _line(self, x1: int, y1: int, x2: int, y2: int):
        dx = x2 - x1
        dy = y2 - y1
        ex1 = x1 >> SUBPIXEL_SHIFT
        ey1 = y1 >> SUBPIXEL_SHIFT
        ex2 = x2 >> SUBPIXEL_SHIFT
        ey2 = y2 >> SUBPIXEL_SHIFT
        fy1 = y1 & SUBPIXEL_MASK
        fy2 = y2 & SUBPIXEL_MASK

        if ex1 < self.min_x: self.min_x = ex1
        if ex1 > self.max_x: self.max_x = ex1
        if ey1 < self.min_y: self.min_y = ey1
        if ey1 > self.max_y: self.max_y = ey1
        if ex2 < self.min_x: self.min_x = ex2
        if ex2 > self.max_x: self.max_x = ex2
        if ey2 < self.min_y: self.min_y = ey2
        if ey2 > self.max_y: self.max_y = ey2

        self._set_curr_cell(ex1, ey1)

        # Single horizontal line
        if ey1 == ey2:
            self._hor_line(ey1, x1, fy1, x2, fy2)
            return

        # Vertical line
        incr = 1
        if dx == 0:
            ex = x1 >> SUBPIXEL_SHIFT
            two_fx = (x1 - (ex << SUBPIXEL_SHIFT)) << 1

            first = SUBPIXEL_SCALE
            if dy < 0:
                first = 0
                incr = -1

            delta = first - fy1
            self._curr_cell[2] += delta
            self._curr_cell[3] += two_fx * delta

            ey1 += incr
            self._set_curr_cell(ex, ey1)

            delta = first + first - SUBPIXEL_SCALE
            area = two_fx * delta
            while ey1 != ey2:
                self._curr_cell[2] = delta
                self._curr_cell[3] = area
                ey1 += incr
                self._set_curr_cell(ex, ey1)

            delta = fy2 - SUBPIXEL_SCALE + first
            self._curr_cell[2] += delta
            self._curr_cell[3] += two_fx * delta
            return

        # General case: multiple horizontal lines
        p = (SUBPIXEL_SCALE - fy1) * dx
        first = SUBPIXEL_SCALE

        if dy < 0:
            p = fy1 * dx
            first = 0
            incr = -1
            dy = -dy

        delta = _c_div(p, dy)
        mod = _c_mod(p, dy)
        if mod < 0:
            delta -= 1
            mod += dy

        x_from = x1 + delta
        self._hor_line(ey1, x1, fy1, x_from, first)

        ey1 += incr
        self._set_curr_cell(x_from >> SUBPIXEL_SHIFT, ey1)

        if ey1 != ey2:
            p = SUBPIXEL_SCALE * dx
            lift = _c_div(p, dy)
            rem = _c_mod(p, dy)
            if rem < 0:
                lift -= 1
                rem += dy
            mod -= dy

            while ey1 != ey2:
                delta = lift
                mod += rem
                if mod >= 0:
                    mod -= dy
                    delta += 1
                x_to = x_from + delta
                self._hor_line(ey1, x_from, SUBPIXEL_SCALE - first, x_to, first)
                x_from = x_to
                ey1 += incr
                self._set_curr_cell(x_from >> SUBPIXEL_SHIFT, ey1)

        self._hor_line(ey1, x_from, SUBPIXEL_SCALE - first, x2, fy2)

    def sort_cells(self) -> bool:
        """Sort accumulated cells by Y then X. Returns True if non-empty."""
        cc = self._curr_cell
        if cc[2] or cc[3]:
            self._cells.append(list(cc))
        cc[0] = 0x7FFFFFFF
        cc[1] = 0x7FFFFFFF
        cc[2] = 0
        cc[3] = 0

        if not self._cells:
            return False
        if self._sorted_ys:
            return True  # Already sorted

        num_ys = self.max_y - self.min_y + 1

        # Y-histogram
        y_counts = [0] * num_ys
        for cell in self._cells:
            y_counts[cell[1] - self.min_y] += 1

        # Convert to starting indices
        starts = [0] * num_ys
        s = 0
        for i in range(num_ys):
            starts[i] = s
            s += y_counts[i]

        # Build sorted cell index array
        sorted_cells = [None] * len(self._cells)
        counts = [0] * num_ys
        for cell in self._cells:
            yi = cell[1] - self.min_y
            sorted_cells[starts[yi] + counts[yi]] = cell
            counts[yi] += 1

        # Sort each Y-row by X
        for i in range(num_ys):
            start = starts[i]
            count = counts[i]
            if count > 1:
                sorted_cells[start:start + count] = sorted(
                    sorted_cells[start:start + count],
                    key=lambda c: c[0]
                )

        self._sorted_cells = sorted_cells
        self._sorted_ys = list(zip(starts, counts))
        return True

    def get_num_scanlines(self) -> int:
        return len(self._sorted_ys)

    def _calc_alpha(self, area: int) -> int:
        alpha = area >> (SUBPIXEL_SHIFT * 2 + 1 - AA_SHIFT)
        if alpha < 0:
            alpha = -alpha
        if self.fill_rule == self.FILL_EVEN_ODD:
            alpha &= AA_MASK2
            if alpha > AA_SCALE:
                alpha = AA_SCALE2 - alpha
        if alpha > AA_MASK:
            alpha = AA_MASK
        if self._gamma_lut:
            return self._gamma_lut[alpha]
        return alpha

    def sweep_scanline(self, scanline: int) -> Optional[list[int]]:
        """
        Sweep one scanline, returning a list of alpha values.

        The returned list covers pixels from min_x to max_x inclusive.
        Index 0 corresponds to pixel column min_x.
        """
        if scanline >= len(self._sorted_ys):
            return None

        start, count = self._sorted_ys[scanline]
        if count == 0:
            return None

        width = self.max_x - self.min_x + 1
        raster = [0] * width
        cells = self._sorted_cells
        cover = 0
        idx = start
        remaining = count

        while remaining > 0:
            cell = cells[idx]
            x = cell[0]
            area = cell[3]
            cover += cell[2]
            idx += 1
            remaining -= 1

            # Accumulate all cells with same X
            while remaining > 0:
                next_cell = cells[idx]
                if next_cell[0] != x:
                    break
                area += next_cell[3]
                cover += next_cell[2]
                idx += 1
                remaining -= 1

            if area:
                alpha = self._calc_alpha((cover << (SUBPIXEL_SHIFT + 1)) - area)
                px = x - self.min_x
                if 0 <= px < width:
                    raster[px] = alpha
                x += 1

            if remaining > 0 and cells[idx][0] > x:
                alpha = self._calc_alpha(cover << (SUBPIXEL_SHIFT + 1))
                if alpha:
                    fill_end = cells[idx][0]
                    for fx in range(x, fill_end):
                        px = fx - self.min_x
                        if 0 <= px < width:
                            raster[px] = alpha

        return raster


def _c_div(a: int, b: int) -> int:
    """C-style integer division (truncates toward zero)."""
    if b == 0:
        return 0
    return int(a / b)


def _c_mod(a: int, b: int) -> int:
    """C-style integer modulo (sign matches dividend)."""
    if b == 0:
        return 0
    return int(math.fmod(a, b))


# ---------------------------------------------------------------------------
# FreeType outline extraction
# ---------------------------------------------------------------------------

def _flatten_quadratic(p0: tuple[float, float], p1: tuple[float, float],
                       p2: tuple[float, float], tolerance: float = 0.5
                       ) -> list[tuple[float, float]]:
    """Recursively flatten a quadratic Bezier curve to line segments."""
    # Midpoint of control polygon
    mx = (p0[0] + 2 * p1[0] + p2[0]) / 4
    my = (p0[1] + 2 * p1[1] + p2[1]) / 4
    # Midpoint of chord
    cx = (p0[0] + p2[0]) / 2
    cy = (p0[1] + p2[1]) / 2
    # Distance
    dx = mx - cx
    dy = my - cy
    if dx * dx + dy * dy <= tolerance * tolerance:
        return [p2]

    # Subdivide
    q0 = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    q2 = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    qm = ((q0[0] + q2[0]) / 2, (q0[1] + q2[1]) / 2)

    result = _flatten_quadratic(p0, q0, qm, tolerance)
    result.extend(_flatten_quadratic(qm, q2, p2, tolerance))
    return result


def extract_outline(face, char_code: int) -> list[list[tuple[float, float]]]:
    """
    Extract glyph outline from FreeType face as flattened contours.

    Loads the glyph at FontHeight=1024 with NO_BITMAP | NO_HINTING,
    then flattens quadratic Beziers to line segments.

    Returns list of contours, each a list of (x, y) in 1024-unit EM space.
    Uses integer >> 6 to match C++'s FtToS1024() before Bezier flattening,
    matching the C++ pipeline where points are converted to ints before
    being stored in the path packer.

    Points are in FreeType's coordinate system (Y-up).
    """
    face.load_char(char_code,
                   freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_NO_HINTING)
    outline = face.glyph.outline
    points = outline.points
    tags = outline.tags
    contours_end = outline.contours

    all_contours = []
    first = 0

    for contour_end in contours_end:
        last = contour_end
        n = last - first + 1
        if n < 2:
            first = last + 1
            continue

        # Convert FT 26.6 fixed point to 1024-unit EM using >> 6
        # This matches C++'s FtToS1024(v) { return v >> 6; }
        # freetype-py returns raw 26.6 values as integers
        c_points = []
        c_tags = []
        for i in range(first, last + 1):
            px, py = points[i]
            # Integer >> 6 to match C++ FtToS1024
            c_points.append((int(px) >> 6, int(py) >> 6))
            c_tags.append(tags[i] & 3)

        # Flatten the contour — control points are already integers
        # matching C++'s path packer storage
        flat = _flatten_contour(c_points, c_tags)
        if len(flat) >= 3:
            all_contours.append(flat)

        first = last + 1

    return all_contours


def _flatten_contour(points: list[tuple[float, float]],
                     tags: list[int]) -> list[tuple[float, float]]:
    """
    Flatten a TrueType contour (on-curve + conic control points) to line segments.

    Follows the same logic as GFxFT2Helper::decomposeGlyphOutline.
    Tag values: 1=on-curve, 0=conic (quadratic Bezier control point).
    """
    n = len(points)
    if n < 2:
        return list(points)

    # Determine starting point (same logic as Scaleform's FT2 helper)
    v_start = points[0]
    v_last = points[-1]

    start_idx = 0
    if tags[0] == 0:  # First point is conic control
        if tags[-1] == 1:  # Last point is on-curve
            v_start = v_last
        else:
            # Both first and last are conic — start at midpoint
            v_start = ((points[0][0] + v_last[0]) / 2,
                       (points[0][1] + v_last[1]) / 2)
            v_last = v_start
        start_idx = -1  # Will be incremented to 0

    result = [v_start]
    current = v_start
    i = start_idx

    while i < n - 1:
        i += 1
        tag = tags[i]
        pt = points[i]

        if tag == 1:  # On-curve
            result.append(pt)
            current = pt
        elif tag == 0:  # Conic control
            # Look ahead for next on-curve or implicit on-curve
            control = pt
            while True:
                if i + 1 >= n:
                    # Close to start
                    flat = _flatten_quadratic(current, control, v_start)
                    result.extend(flat)
                    current = v_start
                    i = n  # Exit outer loop
                    break

                i += 1
                next_tag = tags[i]
                next_pt = points[i]

                if next_tag == 1:
                    # On-curve endpoint
                    flat = _flatten_quadratic(current, control, next_pt)
                    result.extend(flat)
                    current = next_pt
                    break
                else:
                    # Another conic — implicit on-curve at midpoint
                    mid = ((control[0] + next_pt[0]) / 2,
                           (control[1] + next_pt[1]) / 2)
                    flat = _flatten_quadratic(current, control, mid)
                    result.extend(flat)
                    current = mid
                    control = next_pt

    # Close contour back to start if needed
    if current != v_start:
        result.append(v_start)

    return result


def measure_top(face, char_code: int) -> int:
    """
    Measure the top extent of a glyph (Y-up, positive = above baseline).

    Used to compute lowerCaseTop and upperCaseTop for the fitter.
    Returns the value in 1024-unit EM space (matching Scaleform's FontHeight).

    Matches C++: return UInt16(-bounds.Top), where bounds.Top is the
    negated horiBearingY in 1024-unit space.
    """
    face.load_char(char_code,
                   freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_NO_HINTING)
    # horiBearingY is in 26.6 fixed point — use >> 6 to match C++
    return int(face.glyph.metrics.horiBearingY) >> 6


# ---------------------------------------------------------------------------
# Integration: render_glyph()
# ---------------------------------------------------------------------------

def render_glyph(face, char_code: int, font_size: int,
                 stretch: int = 1,
                 x_offset: float = 0.0,
                 y_offset: float = 0.0) -> Optional[np.ndarray]:
    """
    Render a single glyph using the Scaleform pipeline.

    Replicates the coordinate transforms from rasterizeAndPack():
      1. Load outline at FontHeight=1024
      2. Scale to nominal space (nominalSize = font_size * 64)
      3. Feed to GlyphFitter (Y-axis only, widthInPixels=0)
      4. Snap vertices and feed to rasterizer
      5. Sweep scanlines to produce 8-bit alpha bitmap

    Args:
        face: freetype Face object (already opened)
        char_code: Unicode code point
        font_size: Target pixel size (e.g. 9)
        stretch: Stretch factor (1 for normal, 3 for ClearType subpixel)
        x_offset: Subpixel x offset (0.0-1.0) simulating glyph screen position
        y_offset: Subpixel y offset (0.0-1.0) simulating glyph screen position

    Returns:
        numpy 2D array of uint8 alpha values, or None if glyph is empty
    """
    # Step 1: Extract outline
    contours = extract_outline(face, char_code)
    if not contours:
        return None

    # Step 2: Compute nominal size and scale factor
    # C++: subpixelSize = font_size * SubpixelSizeScale (16)
    # C++: nominalSize = subpixelSize * (64 / SubpixelSizeScale) = font_size * 64
    subpixel_size = font_size * 16
    nominal_size = subpixel_size * 4  # = font_size * 64
    if nominal_size > 2048:
        nominal_size = 2048

    k = nominal_size / 1024.0

    # Step 3: Measure lowerCaseTop and upperCaseTop
    lower_case_top = 0
    upper_case_top = 0
    for ch in "HEFTUVWXZ":
        try:
            top = measure_top(face, ord(ch))
            if top > 0:
                upper_case_top = int(top)
                break
        except Exception:
            continue

    if upper_case_top:
        for ch in "zxvwy":
            try:
                top = measure_top(face, ord(ch))
                if top > 0:
                    lower_case_top = int(top)
                    break
            except Exception:
                continue

    # Step 4: Feed contours to fitter
    fitter = GlyphFitter(nominal_size)

    for contour in contours:
        if len(contour) < 3:
            continue
        # Y is negated going from FreeType (Y-up) to fitter
        x0, y0 = contour[0]
        fitter.move_to(int(x0 * k), -int(y0 * k))
        for x, y in contour[1:]:
            fitter.line_to(int(x * k), -int(y * k))

    # Step 5: Fit (Y-axis only, widthInPixels=0)
    fitter.fit_glyph(font_size, 0,
                     int(lower_case_top * k), int(upper_case_top * k))

    # Step 6: Convert fitted vertices to pixel coords for rasterizer
    k_out = 1.0 / fitter.units_per_pixel_y
    rasterizer = ScanlineRasterizer()

    for contour in fitter.contours:
        if len(contour) < 3:
            continue
        vx, vy = fitter.snap_vertex(contour[0][0], contour[0][1])
        rasterizer.move_to(vx * k_out * stretch + x_offset, -vy * k_out + y_offset)
        for x, y in contour[1:]:
            sx, sy = fitter.snap_vertex(x, y)
            rasterizer.line_to(sx * k_out * stretch + x_offset, -sy * k_out + y_offset)
        rasterizer.close_polygon()

    # Step 7: Rasterize
    if not rasterizer.sort_cells():
        return None

    width = rasterizer.max_x - rasterizer.min_x + 1
    height = rasterizer.get_num_scanlines()

    bitmap = np.zeros((height, width), dtype=np.uint8)
    for i in range(height):
        row = rasterizer.sweep_scanline(i)
        if row:
            for j, val in enumerate(row):
                if val and j < width:
                    bitmap[i, j] = val

    # The rasterizer produces output in Scaleform's internal coordinate system
    # where the glyph top is at high Y (bottom of bitmap). Scaleform corrects
    # this during texture rendering. We flip here to match screen orientation.
    bitmap = np.flipud(bitmap)

    return bitmap


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

class ScaleformRenderer:
    """
    High-level Scaleform-faithful glyph renderer.

    Usage:
        renderer = ScaleformRenderer("arialuni.ttf", size=9)
        img = renderer.render_char("3")  # PIL Image
        grid = renderer.render_grid("3") # 7x9 binary grid
    """

    # Optimized subpixel offsets found by grid search against C++ game templates.
    # These simulate the glyph's fractional screen position in the game UI.
    DEFAULT_X_OFFSET = 0.14
    DEFAULT_Y_OFFSET = 0.08
    DEFAULT_THRESHOLD = 56

    def __init__(self, font_path: str | Path, size: int = 11,
                 x_offset: float | None = None, y_offset: float | None = None):
        if not HAS_FREETYPE:
            raise ImportError("freetype-py is required: pip install freetype-py")

        self.font_path = Path(font_path)
        self.size = size
        self.x_offset = x_offset if x_offset is not None else self.DEFAULT_X_OFFSET
        self.y_offset = y_offset if y_offset is not None else self.DEFAULT_Y_OFFSET

        if not self.font_path.exists():
            raise FileNotFoundError(f"Font not found: {self.font_path}")

        self._face = freetype.Face(str(self.font_path))
        # Set pixel size to FontHeight=1024 (Scaleform's internal EM size)
        self._face.set_char_size(1024 * 64, 0, 72, 72)

    def render_char(self, char: str) -> Optional[np.ndarray]:
        """Render a character, returning a 2D numpy array of uint8 alpha values."""
        return render_glyph(self._face, ord(char), self.size,
                           x_offset=self.x_offset, y_offset=self.y_offset)

    def render_char_image(self, char: str) -> Optional[Image.Image]:
        """Render a character as a PIL Image in 'L' mode."""
        if not HAS_PIL:
            raise ImportError("Pillow is required: pip install Pillow")
        bitmap = self.render_char(char)
        if bitmap is None:
            return None
        return Image.fromarray(bitmap, mode='L')

    def render_grid(self, char: str, grid_w: int = 7, grid_h: int = 9,
                    threshold: int | None = None) -> list[list[int]]:
        """
        Render a character and normalize to a right-aligned binary grid.

        Matches the C++ NormGrid normalization:
        1. Binarize at threshold
        2. Find content bounds
        3. Right-align (rightmost lit column → grid column grid_w-1)
        """
        if threshold is None:
            threshold = self.DEFAULT_THRESHOLD
        bitmap = self.render_char(char)
        if bitmap is None:
            return [[0] * grid_w for _ in range(grid_h)]

        binary = (bitmap > threshold).astype(np.uint8)

        # Find content bounds
        cols_with_content = np.any(binary > 0, axis=0)
        rows_with_content = np.any(binary > 0, axis=1)

        if not rows_with_content.any():
            return [[0] * grid_w for _ in range(grid_h)]

        top = int(np.argmax(rows_with_content))
        bottom = int(len(rows_with_content) - np.argmax(rows_with_content[::-1]))
        left = int(np.argmax(cols_with_content))
        right = int(len(cols_with_content) - np.argmax(cols_with_content[::-1]))

        content = binary[top:bottom, left:right]
        ch, cw = content.shape

        # Right-align into grid
        grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
        x_offset = grid_w - cw

        paste_h = min(ch, grid_h)
        paste_w = min(cw, grid_w)
        src_x = max(0, -x_offset)
        dst_x = max(0, x_offset)
        actual_w = paste_w - src_x

        if actual_w > 0 and paste_h > 0:
            grid[0:paste_h, dst_x:dst_x + actual_w] = content[0:paste_h, src_x:src_x + actual_w]

        return grid.tolist()

    def print_glyph(self, char: str, grid_w: int = 7, grid_h: int = 9,
                    threshold: int = 127):
        """Print visual representation of rendered glyph grid."""
        grid = self.render_grid(char, grid_w, grid_h, threshold)
        print(f"Glyph '{char}' (Scaleform pipeline, {grid_w}x{grid_h}):")
        for row in grid:
            print("  " + "".join("#" if c else "." for c in row))
        hex_vals = []
        for row in grid:
            val = 0
            for bit in row:
                val = (val << 1) | bit
            hex_vals.append(f"0x{val:02X}")
        print(f"  Hex: {{{', '.join(hex_vals)}}}")


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

def _find_font() -> Optional[Path]:
    """Find Arial Unicode MS Bold in project fonts directory."""
    project_root = Path(__file__).resolve().parent.parent
    local = project_root / "fonts" / "arial-unicode-bold.ttf"
    if local.exists():
        return local
    for p in [Path(r"C:\Windows\Fonts\ARIALUNI.TTF"),
              Path(r"C:\Windows\Fonts\arialuni.ttf")]:
        if p.exists():
            return p
    return None


def demo():
    """Demo: render digits 0-9 with the Scaleform pipeline."""
    font_path = _find_font()
    if font_path is None:
        print("ERROR: Could not find Arial Unicode MS font.")
        return

    print(f"Using font: {font_path}")
    print(f"Backend: Scaleform GFx pipeline (GlyphFitter + GRasterizer port)")
    print()

    for size in [10, 11, 12]:
        print(f"=== Size {size}px ===")
        renderer = ScaleformRenderer(font_path, size=size)
        for digit in "0123456789":
            renderer.print_glyph(digit)
            print()
        print()


if __name__ == "__main__":
    demo()
