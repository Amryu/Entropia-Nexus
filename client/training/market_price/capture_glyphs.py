"""Interactive glyph capture from market price game screenshots.

Opens a Tkinter dialog that:
1. Loads a screenshot and locates the market price window
2. Extracts individual character blobs from name rows and digit cells
3. Shows each blob magnified alongside the best STPK guess
4. Lets the user confirm or correct each label
5. Saves confirmed glyphs to a JSON collection

Usage:
    python -m client.training.market_price.capture_glyphs [screenshot.png]
    python -m client.training.market_price.capture_glyphs --all
    python -m client.training.market_price.capture_glyphs --live
"""

from __future__ import annotations

import json
import math
import queue
import struct
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    import cv2
except ImportError:
    print("OpenCV required: pip install opencv-python")
    sys.exit(1)

from client.ocr.stpk import read_stpk
from client.ocr.skill_disambiguation import normalize_blob

EXAMPLES_DIR = ROOT / "client" / "market_price_examples"
STPK_DIR = ROOT / "client" / "assets" / "stpk"
TEMPLATE_PATH = ROOT / "client" / "assets" / "market_price_label.png"
GLYPHS_FILE = ROOT / "client" / "training" / "market_price" / "captured_glyphs.json"

TEXT_BRIGHTNESS_THRESHOLD = 80
GRID_4BIT_THRESHOLD = 5

# ROI config (matches market_price_detector.py)
ROI_NAME_R1 = {"dx": -80, "dy": 30, "w": 340, "h": 16}
ROI_NAME_R2 = {"dx": -80, "dy": 49, "w": 340, "h": 16}
ROI_FIRST_CELL = {"dx": 23, "dy": 112, "w": 100, "h": 14}
CELL_OFFSET = {"x": 107, "y": 25}
PERIODS = ["1d", "7d", "30d", "365d", "3650d"]

# Expected character sets for coverage tracking
# Text: uppercase letters (including umlauts) + digits + special chars in item names
EXPECTED_TEXT_CHARS = list(
    "AÄBCDEFGHIJKLMNOÖPQRSTUÜVWXYZ"
    "0123456789"
    ' -!"#$%&(),./:`\''
)
# Digit cells: 0-9, punctuation, and chars for N/A, %, PED, MPED, uPEC
EXPECTED_DIGIT_CHARS = list("0123456789.,%/ANMPEDku")
# Minimum samples to consider a character well-covered
MIN_GOOD_SAMPLES = 3


def find_template(image, tmpl_gray, tmpl_h, tmpl_w):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return max_loc, max_val


# Column-sum threshold for splitting merged blobs.  Character gaps
# show column sums of ~5-22; character interiors are 28+.
# Only applied to blobs wider than MAX_SINGLE_CHAR_W, so single
# characters with low-intensity edge columns are never split.
VALLEY_THRESHOLD = 23
# Blobs wider than this are candidates for valley splitting.
# Single characters are at most ~8px wide (digits) or ~10px wide (text).
# The % sign is 10px wide but has no interior valley below 23.
MAX_SINGLE_CHAR_W = 8
# Minimum sub-blob width after splitting.  If any fragment would be
# narrower than this, the split is rejected (prevents fragmenting
# characters like 'm' whose internal humps create false valleys).
MIN_SUB_BLOB_W = 3


def split_blobs_at_valleys(blobs, i4, text_top, text_h):
    """Split wide blobs at low-intensity column valleys.

    Returns a new blob list where each blob is (ideally) a single character.
    """
    result = []
    for x0, x1 in blobs:
        w = x1 - x0 + 1
        if w <= MAX_SINGLE_CHAR_W:
            result.append((x0, x1))
            continue

        # Compute column intensity profile within the text band
        profile = []
        for c in range(x0, x1 + 1):
            col_sum = int(np.sum(i4[text_top:text_top + text_h, c]))
            profile.append(col_sum)

        # Find split points: columns where intensity is below threshold
        # Group consecutive valley columns, split at the middle of each group
        sub_start = 0
        i = 0
        sub_blobs = []
        while i < len(profile):
            if profile[i] < VALLEY_THRESHOLD:
                # Found a valley — record the sub-blob before it
                if i > sub_start:
                    sub_blobs.append((x0 + sub_start, x0 + i - 1))
                # Skip through the valley
                while i < len(profile) and profile[i] < VALLEY_THRESHOLD:
                    i += 1
                sub_start = i
            else:
                i += 1

        # Last sub-blob
        if sub_start < len(profile):
            sub_blobs.append((x0 + sub_start, x1))

        if len(sub_blobs) > 1:
            # Count fragments narrower than the minimum.
            # One narrow fragment is OK (e.g. "." in ".26"),
            # but multiple narrow fragments indicate internal
            # character structure (e.g. "m" humps) — reject.
            narrow = sum(1 for sb in sub_blobs
                         if sb[1] - sb[0] + 1 < MIN_SUB_BLOB_W)
            if narrow > 1:
                result.append((x0, x1))
            else:
                result.extend(sub_blobs)
        else:
            result.append((x0, x1))

    return result


def merge_narrow_pairs(blobs):
    """Merge pairs of very narrow, closely-spaced blobs.

    Characters like '"' are rendered as two separate tick marks with a
    small gap.  This merges adjacent blobs where both are <= 2px wide
    and the gap between them is <= 2px.
    """
    if len(blobs) < 2:
        return blobs

    MAX_TICK_W = 2
    MAX_GAP = 2

    result = []
    i = 0
    while i < len(blobs):
        if i + 1 < len(blobs):
            x0a, x1a = blobs[i]
            x0b, x1b = blobs[i + 1]
            wa = x1a - x0a + 1
            wb = x1b - x0b + 1
            gap = x0b - x1a - 1
            if wa <= MAX_TICK_W and wb <= MAX_TICK_W and gap <= MAX_GAP:
                result.append((x0a, x1b))
                i += 2
                continue
        result.append(blobs[i])
        i += 1
    return result


def extract_text_info(region_bgr, threshold=TEXT_BRIGHTNESS_THRESHOLD):
    """Extract text intensity, blobs, and text bounds from a BGR region."""
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    intensity = gray.copy()
    intensity[intensity < threshold] = 0
    i4 = np.minimum(intensity.astype(np.float32) / 16, 15).astype(np.uint8)

    rows_with = np.any(i4 > 0, axis=1)
    if not rows_with.any():
        return None

    text_top = int(np.argmax(rows_with))
    text_bot = int(len(rows_with) - 1 - np.argmax(rows_with[::-1]))
    text_h = text_bot - text_top + 1

    col_has = np.any(i4[text_top:text_bot + 1, :] > 0, axis=0)
    blobs = []
    start = -1
    for c in range(len(col_has) + 1):
        has = c < len(col_has) and col_has[c]
        if has and start < 0:
            start = c
        elif not has and start >= 0:
            blobs.append((start, c - 1))
            start = -1

    # Merge narrow tick pairs (e.g. " rendered as two marks)
    blobs = merge_narrow_pairs(blobs)
    # Split wide blobs at column-intensity valleys
    blobs = split_blobs_at_valleys(blobs, i4, text_top, text_h)

    return {
        "intensity": intensity,
        "i4": i4,
        "text_top": text_top,
        "text_bot": text_bot,
        "text_h": text_h,
        "blobs": blobs,
    }


def score_grid_raw(candidate, template):
    if candidate.shape != template.shape:
        return -1.0
    c = candidate.astype(np.int32)
    t = template.astype(np.int32)
    overlap = int(np.sum(np.minimum(c, t)))
    t_sum = int(np.sum(t))
    c_sum = int(np.sum(c))
    if t_sum == 0:
        return 0.0
    raw = 6 * overlap - 2 * t_sum - c_sum
    max_possible = 3 * t_sum
    return float(raw) / float(max_possible) if max_possible > 0 else 0.0


def score_grid(candidate, template):
    """Shift-tolerant scoring: try -1, 0, +1 horizontal shifts."""
    best = score_grid_raw(candidate, template)
    h, w = candidate.shape
    for shift in (-1, 1):
        shifted = np.zeros_like(candidate)
        if shift > 0:
            shifted[:, shift:] = candidate[:, :-shift]
        else:
            shifted[:, :w + shift] = candidate[:, -shift:]
        s = score_grid_raw(shifted, template)
        if s > best:
            best = s
    return best


def extract_blobs_from_region(region_bgr, grid_w, grid_h, right_align,
                              source_label=""):
    """Extract normalized blobs from a BGR region.

    Returns list of dicts with: grid, raw_pixels, x0, x1, blob_w, source.
    """
    info = extract_text_info(region_bgr)
    if info is None:
        return []

    blobs = info["blobs"]
    i4 = info["i4"]
    text_top = info["text_top"]
    text_h = info["text_h"]

    results = []
    for x0, x1 in blobs:
        blob_w = x1 - x0 + 1
        norm = normalize_blob(i4, x0, x1, text_top, text_h,
                              grid_w, grid_h, right_align=right_align)

        # Also extract raw pixel region for display
        rows = min(text_h, i4.shape[0] - text_top)
        cols = min(x1 + 1, i4.shape[1])
        raw_region = region_bgr[text_top:text_top + rows, x0:cols].copy()

        results.append({
            "grid": norm,
            "raw_pixels": raw_region,
            "x0": x0,
            "x1": x1,
            "blob_w": blob_w,
            "source": source_label,
            "text_h": text_h,
        })

    return results


def best_match(blob_grid, entries):
    """Find best matching STPK entry. Returns (text, score, top3)."""
    best_score = -999.0
    best_text = "?"
    all_scores = []
    for entry in entries:
        eg = entry.get("grid")
        if eg is None:
            continue
        s = score_grid(blob_grid, eg)
        all_scores.append((s, entry["text"]))
        if s > best_score:
            best_score = s
            best_text = entry["text"]

    all_scores.sort(reverse=True)
    return best_text, best_score, all_scores[:5]


class GlyphCaptureDialog:
    """Tkinter dialog for reviewing and labeling extracted glyphs."""

    CELL_SIZE = 8  # pixels per grid cell in display

    def __init__(self, blobs, stpk_entries, source_name="", parent=None):
        self.blobs = blobs
        self.entries = stpk_entries
        self.source_name = source_name
        self.current = 0
        self.labels = []  # user-confirmed labels
        self.confirmed = []  # list of confirmed (label, grid) pairs

        # Pre-compute best guesses
        self.guesses = []
        for b in blobs:
            text, score, top5 = best_match(b["grid"], self.entries)
            self.guesses.append({
                "text": text, "score": score, "top5": top5
            })
            self.labels.append(text)  # default to best guess

        self._is_toplevel = parent is not None
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()
        self.root.title(f"Glyph Capture — {source_name}")
        self.root.configure(bg="#1e1e1e")
        self._build_ui()
        self._show_blob(0)

    def _build_ui(self):
        # Top: progress
        top = tk.Frame(self.root, bg="#1e1e1e")
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.progress_label = tk.Label(
            top, text="", fg="#aaa", bg="#1e1e1e",
            font=("Consolas", 11))
        self.progress_label.pack(side=tk.LEFT)
        self.source_label = tk.Label(
            top, text=self.source_name, fg="#666", bg="#1e1e1e",
            font=("Consolas", 9))
        self.source_label.pack(side=tk.RIGHT)

        # Middle: glyph display
        mid = tk.Frame(self.root, bg="#1e1e1e")
        mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left: raw pixels
        left = tk.Frame(mid, bg="#2a2a2a", relief=tk.SUNKEN, bd=1)
        left.pack(side=tk.LEFT, padx=(0, 10), fill=tk.BOTH)
        tk.Label(left, text="Game pixels", fg="#888", bg="#2a2a2a",
                 font=("Consolas", 9)).pack(pady=(5, 2))
        self.raw_canvas = tk.Canvas(left, width=200, height=200,
                                     bg="#000", highlightthickness=0)
        self.raw_canvas.pack(padx=5, pady=5)

        # Center: normalized grid
        center = tk.Frame(mid, bg="#2a2a2a", relief=tk.SUNKEN, bd=1)
        center.pack(side=tk.LEFT, padx=(0, 10), fill=tk.BOTH)
        tk.Label(center, text="Normalized blob", fg="#888", bg="#2a2a2a",
                 font=("Consolas", 9)).pack(pady=(5, 2))
        self.blob_canvas = tk.Canvas(center, width=200, height=200,
                                      bg="#000", highlightthickness=0)
        self.blob_canvas.pack(padx=5, pady=5)

        # Right: best match template
        right = tk.Frame(mid, bg="#2a2a2a", relief=tk.SUNKEN, bd=1)
        right.pack(side=tk.LEFT, fill=tk.BOTH)
        tk.Label(right, text="Best STPK match", fg="#888", bg="#2a2a2a",
                 font=("Consolas", 9)).pack(pady=(5, 2))
        self.tmpl_canvas = tk.Canvas(right, width=200, height=200,
                                      bg="#000", highlightthickness=0)
        self.tmpl_canvas.pack(padx=5, pady=5)

        # Info panel
        info = tk.Frame(self.root, bg="#1e1e1e")
        info.pack(fill=tk.X, padx=10, pady=5)
        self.info_label = tk.Label(
            info, text="", fg="#ccc", bg="#1e1e1e",
            font=("Consolas", 10), justify=tk.LEFT, anchor=tk.W)
        self.info_label.pack(fill=tk.X)

        # Top 5 matches
        self.top5_label = tk.Label(
            info, text="", fg="#888", bg="#1e1e1e",
            font=("Consolas", 9), justify=tk.LEFT, anchor=tk.W)
        self.top5_label.pack(fill=tk.X)

        # Bottom: input
        bot = tk.Frame(self.root, bg="#1e1e1e")
        bot.pack(fill=tk.X, padx=10, pady=(5, 10))

        tk.Label(bot, text="Label:", fg="#aaa", bg="#1e1e1e",
                 font=("Consolas", 11)).pack(side=tk.LEFT)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            bot, textvariable=self.entry_var, width=15,
            font=("Consolas", 14), bg="#333", fg="#fff",
            insertbackground="#fff")
        self.entry.pack(side=tk.LEFT, padx=(5, 10))
        self.entry.bind("<Return>", self._on_confirm)
        self.entry.bind("<Tab>", self._on_skip)

        self.confirm_btn = tk.Button(
            bot, text="Confirm (Enter)", command=self._on_confirm,
            bg="#2a5a2a", fg="#fff", font=("Consolas", 10))
        self.confirm_btn.pack(side=tk.LEFT, padx=2)

        self.skip_btn = tk.Button(
            bot, text="Skip (Tab)", command=self._on_skip,
            bg="#5a5a2a", fg="#fff", font=("Consolas", 10))
        self.skip_btn.pack(side=tk.LEFT, padx=2)

        self.back_btn = tk.Button(
            bot, text="Back (Backspace)", command=self._on_back,
            bg="#4a4a4a", fg="#fff", font=("Consolas", 10))
        self.back_btn.pack(side=tk.LEFT, padx=2)

        self.done_btn = tk.Button(
            bot, text="Done (Esc)", command=self._on_done,
            bg="#5a2a2a", fg="#fff", font=("Consolas", 10))
        self.done_btn.pack(side=tk.RIGHT, padx=2)

        self.root.bind("<BackSpace>", self._on_back)
        self.root.bind("<Escape>", self._on_done)

    def _draw_grid(self, canvas, grid, color="green"):
        """Draw a 4-bit grid onto a canvas."""
        canvas.delete("all")
        cs = self.CELL_SIZE
        gh, gw = grid.shape
        canvas.config(width=gw * cs + 1, height=gh * cs + 1)

        for r in range(gh):
            for c in range(gw):
                val = int(grid[r, c])
                x1, y1 = c * cs, r * cs
                x2, y2 = x1 + cs, y1 + cs
                if val > 0:
                    brightness = min(255, val * 17)
                    if color == "green":
                        fill = f"#{0:02x}{brightness:02x}{0:02x}"
                    elif color == "blue":
                        fill = f"#{brightness:02x}{0:02x}{0:02x}"
                    else:
                        fill = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
                    canvas.create_rectangle(x1, y1, x2, y2,
                                            fill=fill, outline="#222")
                else:
                    canvas.create_rectangle(x1, y1, x2, y2,
                                            fill="#000", outline="#1a1a1a")

    def _draw_raw(self, canvas, raw_pixels):
        """Draw raw BGR pixels magnified onto canvas."""
        canvas.delete("all")
        if raw_pixels is None or raw_pixels.size == 0:
            return
        h, w = raw_pixels.shape[:2]
        scale = max(1, min(200 // max(w, 1), 200 // max(h, 1), 16))
        canvas.config(width=w * scale + 1, height=h * scale + 1)

        for r in range(h):
            for c in range(w):
                px = raw_pixels[r, c]
                if len(px) >= 3:
                    b, g, rv = int(px[0]), int(px[1]), int(px[2])
                else:
                    b = g = rv = int(px[0])
                fill = f"#{rv:02x}{g:02x}{b:02x}"
                x1, y1 = c * scale, r * scale
                x2, y2 = x1 + scale, y1 + scale
                canvas.create_rectangle(x1, y1, x2, y2,
                                        fill=fill, outline="")

    def _show_blob(self, idx):
        if idx < 0 or idx >= len(self.blobs):
            return

        self.current = idx
        blob = self.blobs[idx]
        guess = self.guesses[idx]

        # Progress
        self.progress_label.config(
            text=f"Glyph {idx + 1} / {len(self.blobs)}")

        # Draw raw pixels
        self._draw_raw(self.raw_canvas, blob["raw_pixels"])

        # Draw normalized blob grid
        self._draw_grid(self.blob_canvas, blob["grid"], color="green")

        # Draw best template match
        tmpl_grid = None
        for entry in self.entries:
            if entry["text"] == guess["text"]:
                tmpl_grid = entry.get("grid")
                break
        if tmpl_grid is not None:
            self._draw_grid(self.tmpl_canvas, tmpl_grid, color="blue")
        else:
            self.tmpl_canvas.delete("all")

        # Info
        bw = blob["blob_w"]
        src = blob["source"]
        self.info_label.config(
            text=f"Best: '{guess['text']}'  score={guess['score']:.3f}  "
                 f"blob_w={bw}  source={src}")

        # Top 5
        top5_str = "  ".join(
            f"'{t}'={s:.3f}" for s, t in guess["top5"])
        self.top5_label.config(text=f"Top 5: {top5_str}")

        # Pre-fill entry with current label
        self.entry_var.set(self.labels[idx])
        self.entry.focus_set()
        self.entry.select_range(0, tk.END)

    def _on_confirm(self, event=None):
        label = self.entry_var.get().strip()
        if not label:
            return
        self.labels[self.current] = label
        if self.current + 1 < len(self.blobs):
            self._show_blob(self.current + 1)
        else:
            self._on_done()
        return "break"  # prevent Tab from moving focus

    def _on_skip(self, event=None):
        # Mark as skipped (empty label)
        self.labels[self.current] = ""
        if self.current + 1 < len(self.blobs):
            self._show_blob(self.current + 1)
        else:
            self._on_done()
        return "break"

    def _on_back(self, event=None):
        # Only go back if the entry field is empty (avoid eating real backspaces)
        if event and self.entry_var.get():
            return  # let the Entry handle the backspace
        if self.current > 0:
            self._show_blob(self.current - 1)
        return "break"

    def _on_done(self, event=None):
        self.confirmed = []
        for i, blob in enumerate(self.blobs):
            label = self.labels[i]
            if label:  # skip empty/skipped
                self.confirmed.append({
                    "text": label,
                    "grid": blob["grid"].tolist(),
                    "blob_w": blob["blob_w"],
                    "text_h": blob["text_h"],
                    "source": blob["source"],
                })
        self.root.destroy()

    def run(self):
        if self._is_toplevel:
            self.root.grab_set()
            self.root.wait_window()
        else:
            self.root.mainloop()
        return self.confirmed


def load_glyphs_db() -> dict:
    """Load existing captured glyphs database."""
    if GLYPHS_FILE.exists():
        return json.loads(GLYPHS_FILE.read_text(encoding="utf-8"))
    return {"text_glyphs": [], "digit_glyphs": []}


def save_glyphs_db(db: dict):
    """Save captured glyphs database."""
    GLYPHS_FILE.write_text(
        json.dumps(db, indent=2, ensure_ascii=False),
        encoding="utf-8")


class CoverageWindow:
    """Persistent window showing character coverage during live capture."""

    COLS = 15  # characters per row in the grid

    def __init__(self, db, tmpl_gray, tmpl_h, tmpl_w):
        self.db = db
        self.tmpl_gray = tmpl_gray
        self.tmpl_h = tmpl_h
        self.tmpl_w = tmpl_w
        self.capturing = False
        self.capture_count = 0

        self.root = tk.Tk()
        self.root.title("Glyph Coverage — Ctrl+F12 to capture")
        self.root.configure(bg="#1e1e1e")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self.update_coverage()

    def _build_ui(self):
        # Text section
        tf = tk.LabelFrame(
            self.root, text="TEXT (item names)",
            fg="#aaa", bg="#1e1e1e", font=("Consolas", 10))
        tf.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.text_frame = tk.Frame(tf, bg="#1e1e1e")
        self.text_frame.pack(padx=4, pady=4)

        # Digit section
        df = tk.LabelFrame(
            self.root, text="DIGITS (price cells)",
            fg="#aaa", bg="#1e1e1e", font=("Consolas", 10))
        df.pack(fill=tk.X, padx=8, pady=(4, 4))
        self.digit_frame = tk.Frame(df, bg="#1e1e1e")
        self.digit_frame.pack(padx=4, pady=4)

        # Status bar
        self.status_label = tk.Label(
            self.root, text="", fg="#888", bg="#1e1e1e",
            font=("Consolas", 9))
        self.status_label.pack(fill=tk.X, padx=8, pady=(0, 8))

    def update_coverage(self):
        """Rebuild the coverage grid display from current glyph DB."""
        text_counts: dict[str, int] = {}
        for g in self.db["text_glyphs"]:
            ch = g["text"]
            text_counts[ch] = text_counts.get(ch, 0) + 1

        digit_counts: dict[str, int] = {}
        for g in self.db["digit_glyphs"]:
            ch = g["text"]
            digit_counts[ch] = digit_counts.get(ch, 0) + 1

        self._fill_grid(self.text_frame, EXPECTED_TEXT_CHARS, text_counts)
        self._fill_grid(self.digit_frame, EXPECTED_DIGIT_CHARS, digit_counts)

        text_missing = sum(
            1 for c in EXPECTED_TEXT_CHARS if text_counts.get(c, 0) == 0)
        digit_missing = sum(
            1 for c in EXPECTED_DIGIT_CHARS if digit_counts.get(c, 0) == 0)
        self.status_label.config(
            text=f"Text: {len(self.db['text_glyphs'])} glyphs, "
                 f"{text_missing} missing  |  "
                 f"Digits: {len(self.db['digit_glyphs'])} glyphs, "
                 f"{digit_missing} missing  |  "
                 f"Captures: {self.capture_count}")

    def _fill_grid(self, frame, expected, counts):
        for w in frame.winfo_children():
            w.destroy()

        for i, ch in enumerate(expected):
            row, col = divmod(i, self.COLS)
            count = counts.get(ch, 0)

            if count == 0:
                bg, fg = "#5a1a1a", "#ff6666"
            elif count < MIN_GOOD_SAMPLES:
                bg, fg = "#5a5a1a", "#ffff66"
            else:
                bg, fg = "#1a5a1a", "#66ff66"

            display = {" ": "SPC", "'": "APO", '"': 'QUO',
                       "`": "BT"}.get(ch, ch)
            text = f"{display}\n{count}"

            lbl = tk.Label(
                frame, text=text, bg=bg, fg=fg,
                font=("Consolas", 9), width=4, height=2,
                relief=tk.RAISED, bd=1)
            lbl.grid(row=row, column=col, padx=1, pady=1)

    def _hotkey_thread(self):
        """Separate thread with its own Win32 message loop for hotkeys."""
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        MOD_CONTROL = 0x0002
        VK_F10 = 0x79
        VK_F11 = 0x7A
        VK_F12 = 0x7B
        # Hotkey IDs → capture modes
        HOTKEY_BOTH = 1    # Ctrl+F12: text + digits
        HOTKEY_TEXT = 2    # Ctrl+F11: text only
        HOTKEY_DIGITS = 3  # Ctrl+F10: digits only

        hotkey_modes = {
            HOTKEY_BOTH: "both",
            HOTKEY_TEXT: "text",
            HOTKEY_DIGITS: "digits",
        }
        registered = []

        for hk_id, vk in [(HOTKEY_BOTH, VK_F12),
                           (HOTKEY_TEXT, VK_F11),
                           (HOTKEY_DIGITS, VK_F10)]:
            if user32.RegisterHotKey(None, hk_id, MOD_CONTROL, vk):
                registered.append(hk_id)
            else:
                print(f"WARNING: Failed to register hotkey ID {hk_id}")

        if not registered:
            print("ERROR: No hotkeys registered")
            return

        try:
            msg = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:  # WM_HOTKEY
                    hk_id = int(msg.wParam)
                    mode = hotkey_modes.get(hk_id, "both")
                    self._hotkey_queue.put(mode)
        finally:
            for hk_id in registered:
                user32.UnregisterHotKey(None, hk_id)

    def _check_hotkey(self):
        """Poll the hotkey queue from the Tkinter thread."""
        if self.capturing:
            self.root.after(200, self._check_hotkey)
            return

        try:
            mode = self._hotkey_queue.get_nowait()
            self._on_capture(mode)
        except queue.Empty:
            pass

        self.root.after(100, self._check_hotkey)

    def _on_capture(self, mode="both"):
        import time

        self.capturing = True
        self.capture_count += 1
        mode_label = {"both": "text+digits", "text": "text only",
                      "digits": "digits only"}[mode]
        print(f"\n--- Capture #{self.capture_count} ({mode_label}) ---")

        image = capture_game_window()
        if image is None:
            self.capturing = False
            return

        ts = time.strftime("%Y%m%d_%H%M%S")
        save_path = EXAMPLES_DIR / f"live_{ts}.png"
        cv2.imwrite(str(save_path), image)
        print(f"  Saved screenshot: {save_path.name}")

        text_glyphs, digit_glyphs = process_live_image(
            image, self.tmpl_gray, self.tmpl_h, self.tmpl_w,
            self.capture_count, parent=self.root, mode=mode)

        merge_glyphs(self.db["text_glyphs"], text_glyphs, "text")
        merge_glyphs(self.db["digit_glyphs"], digit_glyphs, "digits")
        save_glyphs_db(self.db)

        self.update_coverage()
        total = len(self.db["text_glyphs"]) + len(self.db["digit_glyphs"])
        print(f"  Total glyphs: {total}")
        self.capturing = False

    def _on_close(self):
        self.root.destroy()

    def run(self):
        """Start the coverage window with hotkey polling."""
        self._hotkey_queue = queue.Queue()

        t = threading.Thread(target=self._hotkey_thread, daemon=True)
        t.start()

        print("Live capture mode active.")
        print("  Ctrl+F12 = text + digits")
        print("  Ctrl+F11 = text only (item name)")
        print("  Ctrl+F10 = digits only (markup/sales)")
        print("  Close the window to quit")
        print()

        self.root.after(100, self._check_hotkey)
        self.root.mainloop()

        total = len(self.db["text_glyphs"]) + len(self.db["digit_glyphs"])
        print(f"\nFinal: {total} glyphs in {GLYPHS_FILE}")


def merge_glyphs(db_list: list, new_glyphs: list, mode: str):
    """Merge new glyphs into existing list, deduplicating by text+grid."""
    existing_keys = set()
    for g in db_list:
        key = (g["text"], tuple(tuple(r) for r in g["grid"]))
        existing_keys.add(key)

    added = 0
    for g in new_glyphs:
        key = (g["text"], tuple(tuple(r) for r in g["grid"]))
        if key not in existing_keys:
            db_list.append(g)
            existing_keys.add(key)
            added += 1
    print(f"  {mode}: added {added} new glyphs ({len(db_list)} total)")


def process_screenshot(image_path, tmpl_gray, tmpl_h, tmpl_w):
    """Process one screenshot: extract blobs, run dialog, return confirmed glyphs."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        print(f"ERROR: Failed to load {image_path}")
        return [], []

    (tx, ty), conf = find_template(image, tmpl_gray, tmpl_h, tmpl_w)
    print(f"  Template at ({tx},{ty}) conf={conf:.4f}")

    # Load STPK
    text_header, text_entries = read_stpk(STPK_DIR / "market_text.stpk")
    digit_header, digit_entries = read_stpk(STPK_DIR / "market_digits.stpk")

    # Apply threshold
    for e in text_entries + digit_entries:
        g = e.get("grid")
        if g is not None:
            e["grid"] = np.where(g >= GRID_4BIT_THRESHOLD, g, 0).astype(np.uint8)

    text_gw = text_header["grid_w"]
    text_gh = text_header["grid_h"]
    digit_gw = digit_header["grid_w"]
    digit_gh = digit_header["grid_h"]

    stem = Path(image_path).stem
    all_text_blobs = []
    all_digit_blobs = []

    # Text rows
    for roi, label in [(ROI_NAME_R1, "name_r1"), (ROI_NAME_R2, "name_r2")]:
        rx, ry = tx + roi["dx"], ty + roi["dy"]
        rw, rh = roi["w"], roi["h"]
        if ry < 0 or ry + rh > image.shape[0] or rx < 0 or rx + rw > image.shape[1]:
            continue
        region = image[ry:ry + rh, rx:rx + rw]
        blobs = extract_blobs_from_region(
            region, text_gw, text_gh, right_align=False,
            source_label=f"{stem}/{label}")
        all_text_blobs.extend(blobs)

    # Digit cells
    for row_idx, period in enumerate(PERIODS):
        for col_idx, metric in enumerate(["markup", "sales"]):
            cell_dx = ROI_FIRST_CELL["dx"] + col_idx * CELL_OFFSET["x"]
            cell_dy = ROI_FIRST_CELL["dy"] + row_idx * CELL_OFFSET["y"]
            cx, cy = tx + cell_dx, ty + cell_dy
            cw, ch = ROI_FIRST_CELL["w"], ROI_FIRST_CELL["h"]
            if (cy < 0 or cy + ch > image.shape[0] or
                    cx < 0 or cx + cw > image.shape[1]):
                continue
            cell_bgr = image[cy:cy + ch, cx:cx + cw]
            blobs = extract_blobs_from_region(
                cell_bgr, digit_gw, digit_gh, right_align=True,
                source_label=f"{stem}/{metric}_{period}")
            all_digit_blobs.extend(blobs)

    confirmed_text = []
    confirmed_digits = []

    if all_text_blobs:
        print(f"  Text: {len(all_text_blobs)} blobs")
        dialog = GlyphCaptureDialog(
            all_text_blobs, text_entries,
            source_name=f"{stem} — Text ({len(all_text_blobs)} glyphs)")
        confirmed_text = dialog.run()
        print(f"  Confirmed {len(confirmed_text)} text glyphs")

    if all_digit_blobs:
        print(f"  Digits: {len(all_digit_blobs)} blobs")
        dialog = GlyphCaptureDialog(
            all_digit_blobs, digit_entries,
            source_name=f"{stem} — Digits ({len(all_digit_blobs)} glyphs)")
        confirmed_digits = dialog.run()
        print(f"  Confirmed {len(confirmed_digits)} digit glyphs")

    return confirmed_text, confirmed_digits




def capture_game_window():
    """Capture a screenshot from the Entropia Universe game window.

    Uses Win32 PrintWindow to capture the game client area directly,
    the same method the live OCR detector uses.
    Returns a BGR numpy array, or None if the game window is not found.
    """
    if sys.platform != "win32":
        print("Live capture only supported on Windows")
        return None

    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    PW_RENDERFULLCONTENT = 0x00000002
    DIB_RGB_COLORS = 0

    GAME_TITLE_PREFIX = "Entropia Universe Client"

    # Find game window
    found_hwnd = None
    def _enum_cb(hwnd, _):
        nonlocal found_hwnd
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value.startswith(GAME_TITLE_PREFIX):
            found_hwnd = hwnd
            return False
        return True

    enum_func_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(enum_func_type(_enum_cb), 0)

    if not found_hwnd:
        print("Game window not found!")
        return None

    # Get client area dimensions
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(found_hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        print("Game window has zero size")
        return None

    # Capture via PrintWindow
    hwnd_dc = user32.GetDC(found_hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)
    user32.PrintWindow(found_hwnd, mem_dc, PW_RENDERFULLCONTENT)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, height,
                    buffer, ctypes.byref(bmi), DIB_RGB_COLORS)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(found_hwnd, hwnd_dc)

    image = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
    return image[:, :, :3].copy()


def process_live_image(image, tmpl_gray, tmpl_h, tmpl_w, capture_id,
                       parent=None, mode="both"):
    """Process a live-captured image through the glyph capture dialog.

    Args:
        mode: "both", "text", or "digits"
    """
    (tx, ty), conf = find_template(image, tmpl_gray, tmpl_h, tmpl_w)
    if conf < 0.85:
        print(f"  Market price window not found (conf={conf:.3f})")
        return [], []

    print(f"  Template at ({tx},{ty}) conf={conf:.4f}")

    # Load STPK for best-guess matching
    try:
        text_header, text_entries = read_stpk(STPK_DIR / "market_text.stpk")
        digit_header, digit_entries = read_stpk(STPK_DIR / "market_digits.stpk")
        for e in text_entries + digit_entries:
            g = e.get("grid")
            if g is not None:
                e["grid"] = np.where(g >= GRID_4BIT_THRESHOLD, g, 0).astype(np.uint8)
    except Exception:
        text_header = {"grid_w": 14, "grid_h": 15}
        text_entries = []
        digit_header = {"grid_w": 32, "grid_h": 12}
        digit_entries = []

    text_gw = text_header["grid_w"]
    text_gh = text_header["grid_h"]
    digit_gw = digit_header["grid_w"]
    digit_gh = digit_header["grid_h"]

    label = f"live_{capture_id}"
    all_text_blobs = []
    all_digit_blobs = []

    if mode in ("both", "text"):
        for roi, rl in [(ROI_NAME_R1, "name_r1"), (ROI_NAME_R2, "name_r2")]:
            rx, ry = tx + roi["dx"], ty + roi["dy"]
            rw, rh = roi["w"], roi["h"]
            if ry < 0 or ry + rh > image.shape[0] or rx < 0 or rx + rw > image.shape[1]:
                continue
            region = image[ry:ry + rh, rx:rx + rw]
            blobs = extract_blobs_from_region(
                region, text_gw, text_gh, right_align=False,
                source_label=f"{label}/{rl}")
            all_text_blobs.extend(blobs)

    if mode in ("both", "digits"):
        for row_idx, period in enumerate(PERIODS):
            for col_idx, metric in enumerate(["markup", "sales"]):
                cell_dx = ROI_FIRST_CELL["dx"] + col_idx * CELL_OFFSET["x"]
                cell_dy = ROI_FIRST_CELL["dy"] + row_idx * CELL_OFFSET["y"]
                cx, cy = tx + cell_dx, ty + cell_dy
                cw, ch = ROI_FIRST_CELL["w"], ROI_FIRST_CELL["h"]
                if (cy < 0 or cy + ch > image.shape[0] or
                        cx < 0 or cx + cw > image.shape[1]):
                    continue
                cell_bgr = image[cy:cy + ch, cx:cx + cw]
                blobs = extract_blobs_from_region(
                    cell_bgr, digit_gw, digit_gh, right_align=True,
                    source_label=f"{label}/{metric}_{period}")
                all_digit_blobs.extend(blobs)

    confirmed_text = []
    confirmed_digits = []

    if all_text_blobs:
        print(f"  Text: {len(all_text_blobs)} blobs")
        dialog = GlyphCaptureDialog(
            all_text_blobs, text_entries,
            source_name=f"Live #{capture_id} — Text ({len(all_text_blobs)} glyphs)",
            parent=parent)
        confirmed_text = dialog.run()
        print(f"  Confirmed {len(confirmed_text)} text glyphs")

    if all_digit_blobs:
        print(f"  Digits: {len(all_digit_blobs)} blobs")
        dialog = GlyphCaptureDialog(
            all_digit_blobs, digit_entries,
            source_name=f"Live #{capture_id} — Digits ({len(all_digit_blobs)} glyphs)",
            parent=parent)
        confirmed_digits = dialog.run()
        print(f"  Confirmed {len(confirmed_digits)} digit glyphs")

    return confirmed_text, confirmed_digits


def run_live_mode(tmpl_gray, tmpl_h, tmpl_w):
    """Run in live mode with coverage window and Ctrl+F12 hotkey."""
    if sys.platform != "win32":
        print("Live mode only supported on Windows")
        sys.exit(1)

    db = load_glyphs_db()
    cov = CoverageWindow(db, tmpl_gray, tmpl_h, tmpl_w)
    cov.run()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Capture market price glyphs from game screenshots.")
    parser.add_argument("screenshots", nargs="*",
                        help="Screenshot files or --all")
    parser.add_argument("--all", action="store_true",
                        help="Process all screenshots in examples dir")
    parser.add_argument("--live", action="store_true",
                        help="Live mode: Ctrl+F12 captures from game")
    args = parser.parse_args()

    template_raw = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_UNCHANGED)
    if template_raw is None:
        print("ERROR: template image not found")
        sys.exit(1)
    tmpl_gray = template_raw[:, :, 3].copy()
    tmpl_h, tmpl_w = template_raw.shape[:2]

    if args.live:
        run_live_mode(tmpl_gray, tmpl_h, tmpl_w)
        return

    if args.all:
        samples = (sorted(EXAMPLES_DIR.glob("*.PNG")) +
                   sorted(EXAMPLES_DIR.glob("*.png")))
    elif args.screenshots:
        samples = [Path(s) for s in args.screenshots]
    else:
        samples = (sorted(EXAMPLES_DIR.glob("*.PNG")) +
                   sorted(EXAMPLES_DIR.glob("*.png")))

    if not samples:
        print("No screenshots found!")
        sys.exit(1)

    db = load_glyphs_db()

    for sample_path in samples:
        if sample_path.is_dir():
            continue
        print(f"\n{'=' * 50}")
        print(f"Processing: {sample_path.name}")
        print(f"{'=' * 50}")
        text_glyphs, digit_glyphs = process_screenshot(
            sample_path, tmpl_gray, tmpl_h, tmpl_w)

        merge_glyphs(db["text_glyphs"], text_glyphs, "text")
        merge_glyphs(db["digit_glyphs"], digit_glyphs, "digits")

    save_glyphs_db(db)
    total = len(db["text_glyphs"]) + len(db["digit_glyphs"])
    print(f"\nSaved {total} glyphs to {GLYPHS_FILE}")


if __name__ == "__main__":
    main()
