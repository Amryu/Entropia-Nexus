import subprocess
import sys
import threading
import tkinter as tk
from typing import Optional

import numpy as np

try:
    from PIL import Image as PILImage
    from PIL import ImageTk
except ImportError:
    PILImage = None
    ImageTk = None

from ..core.event_bus import EventBus
from ..core.logger import get_logger
from ..core.constants import (
    EVENT_DEBUG_ROW, EVENT_DEBUG_REGIONS, EVENT_OCR_PAGE_CHANGED,
    GAME_TITLE_PREFIX,
)

if sys.platform == "win32":
    import ctypes
    # Win32 extended window styles for click-through
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    user32 = ctypes.windll.user32

# Focus check interval (ms)
FOCUS_POLL_INTERVAL = 500

log = get_logger("ScanOverlay")

# Checkmark appearance
CHECKMARK = "\u2713"
CHECK_COLOR = "#00dd66"
CHECK_FONT = ("Consolas", 10, "bold")

# Debug region box colors
COLOR_WINDOW = "#ff3333"      # Red — skills window bounds
COLOR_SIDEBAR = "#33ff33"     # Green — sidebar
COLOR_TABLE = "#ffff33"       # Yellow — table area
COLOR_PAGINATION = "#ff33ff"  # Magenta — pagination
COLOR_COL_NAME = "#3399ff"    # Blue — name column
COLOR_COL_RANK = "#ff9933"    # Orange — rank column
COLOR_COL_POINTS = "#33dddd"  # Teal — points column

# Template match box color
COLOR_TEMPLATE = "#ffffff"    # White — template match outlines

# Row highlight colors
COLOR_ROW_MATCHED = "#00dd66"
COLOR_ROW_UNMATCHED = "#ff4444"
COLOR_ROW_SKIP = "#666666"

# Row text label appearance
LABEL_FONT = ("Consolas", 8)
LABEL_COLOR_NAME = "#00dd66"
LABEL_COLOR_RANK = "#ffcc00"
LABEL_COLOR_POINTS = "#33dddd"
LABEL_COLOR_RAW = "#ff6666"

# The transparent background color (must not match any checkmark pixel)
TRANSPARENT_COLOR = "#010101"

BOX_WIDTH = 2  # pixel width for debug rectangles

# Font attempt overlay (renders attempted template match text in magenta)
COLOR_FONT_ATTEMPT = "#ff00ff"    # Magenta — font template attempt text
FONT_ATTEMPT_SCORE = ("Consolas", 7)


class ScanOverlay:
    """Transparent click-through overlay showing checkmarks on detected skills.

    Draws a small green checkmark at the left edge of each successfully
    OCR-matched skill row, directly over the game window. The overlay is
    fully transparent and click-through so it doesn't interfere with
    the game or user input.

    In debug mode, also draws colored rectangles around all regions the
    OCR engine is scanning (window, sidebar, table, columns, pagination),
    template match boxes, and per-row highlights with OCR'd values.
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._check_items: list[int] = []
        self._region_items: list[int] = []
        self._row_items: list[int] = []
        self._visible = False
        self._game_focused = False  # Whether the game window is in foreground
        self._has_content = False   # Whether we have anything to show
        self._table_x = 0      # Screen X of table left edge
        self._table_w = 0      # Table width in pixels
        self._window_right = 0  # Screen X of window right edge
        # Column screen-absolute X ranges: {"name": (x1, x2), ...}
        self._col_screen: dict[str, tuple[int, int]] = {}
        self._row_photos: list = []  # Keep PhotoImage refs (prevent GC)

    def start(self) -> None:
        """Initialize and run the scan overlay. Blocks on mainloop."""
        self._event_bus.subscribe(EVENT_DEBUG_ROW, self._on_row)
        self._event_bus.subscribe(EVENT_DEBUG_REGIONS, self._on_regions)
        self._event_bus.subscribe(EVENT_OCR_PAGE_CHANGED, self._on_page_changed)
        self._build_window()
        self._root.mainloop()

    def start_background(self) -> threading.Thread:
        """Start in a background thread."""
        thread = threading.Thread(target=self.start, daemon=True, name="scan-overlay")
        thread.start()
        return thread

    def stop(self) -> None:
        self._event_bus.unsubscribe(EVENT_DEBUG_ROW, self._on_row)
        self._event_bus.unsubscribe(EVENT_DEBUG_REGIONS, self._on_regions)
        self._event_bus.unsubscribe(EVENT_OCR_PAGE_CHANGED, self._on_page_changed)
        root = self._root
        if root:
            try:
                root.after(0, root.quit)
                root.after(10, root.destroy)
            except tk.TclError:
                pass
            self._root = None

    def _build_window(self) -> None:
        self._root = tk.Tk()
        self._root.title("")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.9)
        self._root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self._root.configure(bg=TRANSPARENT_COLOR)

        # Cover the full screen so checkmarks can appear anywhere
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        self._root.geometry(f"{screen_w}x{screen_h}+0+0")

        self._canvas = tk.Canvas(
            self._root, bg=TRANSPARENT_COLOR,
            highlightthickness=0, width=screen_w, height=screen_h,
        )
        self._canvas.pack()

        # Make click-through on Windows
        self._root.update_idletasks()
        self._make_click_through()

        # Start hidden until first detection
        self._root.withdraw()

        # Start periodic focus check
        self._root.after(FOCUS_POLL_INTERVAL, self._check_focus)

    def _make_click_through(self) -> None:
        """Make the overlay window click-through (pass clicks to windows below)."""
        if sys.platform != "win32":
            return  # Tkinter -alpha transparency is sufficient on Linux/X11
        try:
            # Get the HWND from tkinter's frame
            hwnd = int(self._root.frame(), 16)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception as e:
            log.warning("Failed to set click-through: %s", e)

    def _check_focus(self) -> None:
        """Hide overlay when the game window is not in the foreground."""
        if not self._root:
            return

        try:
            title = self._get_foreground_title()
            game_focused = title.startswith(GAME_TITLE_PREFIX)

            if game_focused and not self._game_focused:
                # Game regained focus — show overlay if we have content
                self._game_focused = True
                if self._has_content:
                    self._root.deiconify()
                    self._visible = True
            elif not game_focused and self._game_focused:
                # Game lost focus — hide overlay
                self._game_focused = False
                if self._visible:
                    self._root.withdraw()
                    self._visible = False
        except Exception:
            pass

        self._root.after(FOCUS_POLL_INTERVAL, self._check_focus)

    @staticmethod
    def _get_foreground_title() -> str:
        """Get the title of the currently focused window."""
        if sys.platform == "win32":
            fg_hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(fg_hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(fg_hwnd, buf, length + 1)
                return buf.value
            return ""
        # Linux: use xdotool
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    # --- Event handlers ---

    def _on_regions(self, data: dict) -> None:
        """Draw debug region boxes from detected layout regions."""
        table = data.get("table")
        if table:
            self._table_x = table[0]  # Screen X of table left edge
            self._table_w = table[2]  # Table width

        window = data.get("window")
        if window:
            self._window_right = window[0] + window[2]  # wx + ww

        self._col_screen = data.get("col_screen", {})

        if self._root:
            self._root.after(0, self._draw_regions, data)

    def _on_row(self, data: dict) -> None:
        """Draw checkmark, row highlight, and OCR'd values for each scanned row."""
        row_type = data.get("type")
        screen_y = data.get("y", 0)
        row_h = data.get("h", 25)

        if row_type == "matched":
            # Position checkmark just to the left of the name column
            screen_x = self._table_x - 16 if self._table_x else 0
            if self._root:
                self._root.after(0, self._draw_check, screen_x, screen_y, row_h)

        # Draw row highlight for all row types that have position data
        if screen_y and row_h and self._root:
            color = {
                "matched": COLOR_ROW_MATCHED,
                "unmatched": COLOR_ROW_UNMATCHED,
                "skip": COLOR_ROW_SKIP,
            }.get(row_type)
            if color:
                self._root.after(0, self._draw_row_highlight,
                                 screen_y, row_h, color)

        # Draw OCR'd value labels for rows with text data
        if self._root and screen_y and row_h:
            self._root.after(0, self._draw_row_labels, data, screen_y, row_h)

        # Draw font template attempt over the name column
        font_attempt = data.get("font_attempt")
        if font_attempt and self._root and screen_y and row_h:
            self._root.after(0, self._draw_font_attempt,
                             font_attempt, screen_y, row_h)

    # --- Drawing methods ---

    def _show_if_focused(self) -> None:
        """Show the overlay if the game is focused and we have content."""
        self._has_content = True
        if self._game_focused and not self._visible:
            self._root.deiconify()
            self._visible = True

    def _draw_regions(self, data: dict) -> None:
        """Draw colored debug rectangles around all OCR scan regions."""
        if not self._canvas:
            return

        self._show_if_focused()

        # Clear previous region boxes (keep checkmarks and row highlights)
        for item in self._region_items:
            self._canvas.delete(item)
        self._region_items.clear()

        # Draw each region as a colored rectangle
        region_colors = [
            ("window", COLOR_WINDOW),
            ("sidebar", COLOR_SIDEBAR),
            ("table", COLOR_TABLE),
            ("pagination", COLOR_PAGINATION),
        ]
        for key, color in region_colors:
            region = data.get(key)
            if region:
                self._draw_rect(region[0], region[1],
                                region[2], region[3], color)

        # Draw column regions
        columns = data.get("columns", {})
        col_colors = {
            "name": COLOR_COL_NAME,
            "rank": COLOR_COL_RANK,
            "points": COLOR_COL_POINTS,
        }
        for col_name, color in col_colors.items():
            col = columns.get(col_name)
            if col:
                self._draw_rect(col[0], col[1], col[2], col[3], color)

        # Draw template match boxes with labels
        templates = data.get("templates", {})
        self._draw_template_matches(templates)

    def _draw_template_matches(self, templates: dict) -> None:
        """Draw outlines and labels around template-matched positions."""
        if not self._canvas or not templates:
            return

        for name, (x, y, w, h) in templates.items():
            # Draw box
            item = self._canvas.create_rectangle(
                x, y, x + w, y + h,
                outline=COLOR_TEMPLATE, width=1, dash=(3, 3),
            )
            self._region_items.append(item)

            # Draw label above the box
            label = name.upper()
            item = self._canvas.create_text(
                x + w // 2, y - 2,
                text=label, fill=COLOR_TEMPLATE,
                font=("Consolas", 7), anchor="s",
            )
            self._region_items.append(item)

    def _draw_rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        """Draw a debug rectangle outline on the canvas."""
        item = self._canvas.create_rectangle(
            x, y, x + w, y + h,
            outline=color, width=BOX_WIDTH,
        )
        self._region_items.append(item)

    def _draw_row_highlight(self, y: int, h: int, color: str) -> None:
        """Draw a thin horizontal highlight around a scanned row."""
        if not self._canvas or not self._table_x:
            return

        self._show_if_focused()

        w = self._table_w if self._table_w else 500
        item = self._canvas.create_rectangle(
            self._table_x, y, self._table_x + w, y + h,
            outline=color, width=1,
        )
        self._row_items.append(item)

    def _draw_row_labels(self, data: dict, y: int, h: int) -> None:
        """Draw OCR'd text values to the right of the skills window."""
        if not self._canvas or not self._window_right:
            return

        self._show_if_focused()

        row_type = data.get("type")
        cy = y + h // 2  # vertical center of row
        rx = self._window_right + 8  # base X: right of skills window

        if row_type == "matched":
            name = data.get("matched_name", "")
            rank = data.get("rank", "")
            points = data.get("points", "")
            rank_ok = data.get("rank_verified", True)

            if name:
                item = self._canvas.create_text(
                    rx, cy, text=name, fill=LABEL_COLOR_NAME,
                    font=LABEL_FONT, anchor="w",
                )
                self._row_items.append(item)

            if rank:
                rank_color = LABEL_COLOR_RANK if rank_ok else LABEL_COLOR_RAW
                item = self._canvas.create_text(
                    rx + 180, cy, text=rank, fill=rank_color,
                    font=LABEL_FONT, anchor="w",
                )
                self._row_items.append(item)

            if points:
                item = self._canvas.create_text(
                    rx + 340, cy, text=points, fill=LABEL_COLOR_POINTS,
                    font=LABEL_FONT, anchor="w",
                )
                self._row_items.append(item)

        elif row_type == "unmatched":
            raw = data.get("raw_text", "")
            if raw:
                item = self._canvas.create_text(
                    rx, cy, text=f"? {raw}", fill=LABEL_COLOR_RAW,
                    font=LABEL_FONT, anchor="w",
                )
                self._row_items.append(item)

        elif row_type == "skip":
            raw = data.get("raw_text", "")
            reason = data.get("reason", "")
            text = f"[{reason}] {raw}" if raw else f"[{reason}]"
            item = self._canvas.create_text(
                rx, cy, text=text, fill=COLOR_ROW_SKIP,
                font=LABEL_FONT, anchor="w",
            )
            self._row_items.append(item)

    def _draw_font_attempt(self, attempt: dict, y: int, h: int) -> None:
        """Draw the font-matched attempt text over the name column in magenta.

        Uses the pre-rendered template image from FontMatcher (with tight
        kerning) converted to a colored PhotoImage, so the overlay shows
        the exact same rendering that template matching compares against.
        """
        if not self._canvas or PILImage is None or ImageTk is None:
            return
        if not self._col_screen.get("name"):
            return

        self._show_if_focused()

        name = attempt.get("name", "")
        score = attempt.get("score", 0)
        template = attempt.get("template")
        if not name:
            return

        name_x = self._col_screen["name"][0]
        # Align with text zone (top ~70% of row)
        text_cy = y + int(h * 0.35)

        # Draw the pre-rendered template as a colored PhotoImage
        if template is not None:
            photo = self._template_to_photo(template, self._root)
            if photo:
                self._row_photos.append(photo)
                item = self._canvas.create_image(
                    name_x + 2, text_cy, image=photo, anchor="w",
                )
                self._row_items.append(item)

        # Draw confidence score to the left of the table
        score_x = self._table_x - 4 if self._table_x else name_x - 40
        item = self._canvas.create_text(
            score_x, text_cy, text=f"{score:.2f}",
            fill=COLOR_FONT_ATTEMPT, font=FONT_ATTEMPT_SCORE, anchor="e",
        )
        self._row_items.append(item)

    @staticmethod
    def _template_to_photo(template: np.ndarray, master):
        """Convert a grayscale template array to a magenta PhotoImage.

        Background pixels become the transparent color (#010101) so they
        disappear on the overlay. Text pixels get colored magenta scaled
        by their grayscale intensity.
        """
        if template is None or PILImage is None or ImageTk is None:
            return None

        th, tw = template.shape[:2]
        # RGB image: background = transparent color (1,1,1)
        rgb = np.full((th, tw, 3), 1, dtype=np.uint8)

        # Magenta (255, 0, 255) scaled by grayscale intensity
        mask = template > 30
        intensity = template.astype(np.float32) / 255.0
        rgb[:, :, 0] = np.where(mask, (intensity * 255).astype(np.uint8), 1)  # R
        # G stays 1 (transparent bg)
        rgb[:, :, 2] = np.where(mask, (intensity * 255).astype(np.uint8), 1)  # B

        pil_img = PILImage.fromarray(rgb, "RGB")
        return ImageTk.PhotoImage(pil_img, master=master)

    def _draw_check(self, x: int, y: int, row_h: int) -> None:
        if not self._canvas:
            return
        self._show_if_focused()
        cy = y + row_h // 2
        item = self._canvas.create_text(
            x, cy, text=CHECKMARK,
            fill=CHECK_COLOR, font=CHECK_FONT, anchor="c",
        )
        self._check_items.append(item)

    def _on_page_changed(self, _data) -> None:
        """Clear checkmarks and row highlights when page changes."""
        if self._root:
            self._root.after(0, self._clear_page_items)

    def _clear_page_items(self) -> None:
        if self._canvas:
            for item in self._check_items:
                self._canvas.delete(item)
            self._check_items.clear()
            for item in self._row_items:
                self._canvas.delete(item)
            self._row_items.clear()
            self._row_photos.clear()
