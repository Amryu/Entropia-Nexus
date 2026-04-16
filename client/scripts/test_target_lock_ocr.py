"""Test script: capture live frames and evaluate target lock OCR.

Reads the three target-lock components:
- Green "shared loot" icon
- Mob HP bar (red bar fading to dark gray, glow at the transition)
- Mob danger level + maturity name (e.g. "L123 Atrox Old Alpha")

The mob name is rendered without a darker backdrop, so OCR misreads are
expected.  This script tries several preprocessing strategies and a
tolerant maturity-name matcher (handles reorder, extra/missing words,
fuzzy fallback).

Re-read logic: the name is OCR'd only when we suspect a target change —
target lock template moved noticeably, HP went UP (downward HP changes
do not trigger re-reads), or we don't yet have a confirmed name.

Usage (from repo root):
    python -m client.scripts.test_target_lock_ocr            # 1 capture
    python -m client.scripts.test_target_lock_ocr --loop 10  # 10 captures, 1s apart

Output goes to client/scripts/_target_lock_output/ (gitignored).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CLIENT_DIR = os.path.dirname(_SCRIPT_DIR)
_REPO_ROOT = os.path.dirname(_CLIENT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from client.platform import backend as _platform
from client.core.constants import GAME_TITLE_PREFIX
from client.core.config import AppConfig
from client.api.data_client import DataClient
from client.ocr.capturer import ScreenCapturer
from client.ocr import onnxtr_recognizer

# ---------------------------------------------------------------------------
# Constants — defaults match client/core/config.py
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "_target_lock_output")
TEMPLATE_PATH = os.path.join(_CLIENT_DIR, "assets", "target_lock.png")

# Template match
MATCH_THRESHOLD = 0.90       # raised: 0.85 produces false positives
MIN_INSIDE_BRIGHTNESS = 200
MIN_CONTRAST = 10

# Heart exclusion: reject target lock matches near the player heart icon
HEART_TEMPLATE_PATH = os.path.join(_CLIENT_DIR, "assets", "player_heart.png")
HEART_EXCLUSION_MARGIN = 30  # px around the heart icon

# ROI offsets relative to target_lock template top-left
ROI_HP = {"dx": -89, "dy": -17, "w": 193, "h": 6}
ROI_SHARED = {"dx": -125, "dy": -22, "w": 16, "h": 16}
ROI_NAME = {"dx": -190, "dy": -40, "w": 394, "h": 14}

# OCR
NAME_MIN_CONFIDENCE = 0.20  # noisy background — be permissive

# Re-read trigger
HP_UP_THRESHOLD = 0.05  # 5% increase counts as "new target"
NAME_RECHECK_INTERVAL = 5  # frames between full re-reads when uncertain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_heart(image: np.ndarray, heart_template) -> tuple[int, int, int, int] | None:
    """Locate the player heart icon. Returns (x, y, w, h) or None."""
    if heart_template is None:
        return None
    th, tw = heart_template.shape[:2]
    template_gray = heart_template[:, :, 3]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < 0.90:
        return None
    return (max_loc[0], max_loc[1], tw, th)


def _in_exclusion_zone(x: int, y: int,
                       zone: tuple[int, int, int, int] | None) -> bool:
    if zone is None:
        return False
    zx, zy, zw, zh = zone
    m = HEART_EXCLUSION_MARGIN
    return (zx - m <= x <= zx + zw + m) and (zy - m <= y <= zy + zh + m)


def find_template(image: np.ndarray, template_raw, mask_bool, inv_bool,
                  exclusion: tuple[int, int, int, int] | None = None):
    """Locate the target lock chevron via alpha-template matching.

    Searches for multiple candidate matches so we can skip ones inside the
    heart exclusion zone (the player status bar's chevron-like glyphs are
    a common false positive).
    """
    template_gray = template_raw[:, :, 3]
    th, tw = template_gray.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(gray, template_gray, cv2.TM_CCOEFF_NORMED)

    # Iterate over the top N candidate matches; first one outside exclusion wins
    flat = result.flatten()
    if flat.size == 0:
        return None, 0.0
    top_n = min(20, flat.size)
    top_indices = np.argpartition(flat, -top_n)[-top_n:]
    top_indices = top_indices[np.argsort(-flat[top_indices])]

    h_res, w_res = result.shape
    for idx in top_indices:
        score = float(flat[idx])
        if score < MATCH_THRESHOLD:
            break
        y = idx // w_res
        x = idx % w_res
        if _in_exclusion_zone(x, y, exclusion):
            continue
        # Validate brightness/contrast
        region = image[y:y + th, x:x + tw]
        if region.shape[:2] != (th, tw):
            continue
        rg = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        inside = float(np.mean(rg[mask_bool])) if mask_bool.any() else 0.0
        outside_arr = rg[inv_bool]
        outside = float(np.mean(outside_arr)) if outside_arr.size else inside
        if inside < MIN_INSIDE_BRIGHTNESS:
            continue
        if inside - outside < MIN_CONTRAST:
            continue
        return (x, y), score
    return None, float(flat.max()) if flat.size else 0.0


def extract_roi(image: np.ndarray, tx: int, ty: int, roi: dict) -> np.ndarray | None:
    """Extract a ROI region (clamps to image bounds)."""
    ih, iw = image.shape[:2]
    x = tx + roi["dx"]
    y = ty + roi["dy"]
    w = roi["w"]
    h = roi["h"]
    x0 = max(0, x); y0 = max(0, y)
    x1 = min(iw, x + w); y1 = min(ih, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    return image[y0:y1, x0:x1].copy()


# ---------------------------------------------------------------------------
# HP bar reading
# ---------------------------------------------------------------------------
# The bar is normally RED with a glow at the right edge of the filled portion;
# as HP drops, the right side becomes very dark gray. The transition has a
# noticeable bright pixel ("glow") that marks the current HP.
#
# A GREEN bar means the mob is unreachable / not lockable (anti-abuse). The
# nameplate may still be visible but it's not actually our target.
#
# Returns one of:
#   ("red",   pct,   debug)  -> normal lockable target with HP=pct
#   ("green", 1.0,   debug)  -> unreachable target (no real lock)
#   ("none",  0.0,   debug)  -> no recognizable bar (likely false template hit)

def read_hp_pct(region_bgr: np.ndarray) -> tuple[str, float, str]:
    if region_bgr is None or region_bgr.size == 0:
        return "none", 0.0, "empty"

    h, w = region_bgr.shape[:2]
    if w == 0:
        return "none", 0.0, "zero-width"

    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, np.array([0, 60, 80]), np.array([12, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([168, 60, 80]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red1, red2)
    green_mask = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))

    red_px = int(cv2.countNonZero(red_mask))
    green_px = int(cv2.countNonZero(green_mask))

    # Need a minimum number of bar-colored pixels to count as "a bar"
    min_bar_px = max(3, w // 8)
    if red_px + green_px < min_bar_px:
        return "none", 0.0, f"insufficient bar pixels (r={red_px} g={green_px})"

    if green_px > red_px * 2:
        # Predominantly green = unreachable target
        return "green", 1.0, f"green={green_px} red={red_px}"

    # Find the rightmost column with a red pixel
    col_red = np.any(red_mask > 0, axis=0)
    if not np.any(col_red):
        return "none", 0.0, "no-red-cols"
    rightmost = int(np.where(col_red)[0][-1])
    pct = (rightmost + 1) / w
    return "red", min(1.0, pct), f"rightmost={rightmost}/{w}"


# ---------------------------------------------------------------------------
# Shared loot icon
# ---------------------------------------------------------------------------
# Shared loot icon is bright green. The simple brightness check (mean > 80)
# from the existing detector also catches yellow/white icons. Use a green
# hue check for better specificity.

def detect_shared(region_bgr: np.ndarray) -> tuple[bool, str]:
    """Detect the green shared-loot icon.

    Returns (is_shared, debug_info).
    """
    if region_bgr is None or region_bgr.size == 0:
        return False, "empty"

    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
    green_ratio = float(np.count_nonzero(green)) / green.size
    return green_ratio > 0.05, f"green_ratio={green_ratio:.3f}"


# ---------------------------------------------------------------------------
# Name preprocessing strategies
# ---------------------------------------------------------------------------

def preprocess_raw(crop_bgr: np.ndarray) -> np.ndarray:
    return crop_bgr


def preprocess_value(crop_bgr: np.ndarray) -> np.ndarray:
    """HSV Value channel only (brightness). Helps when text is white over
    a bright/saturated background — text is brightest, background varies."""
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    return cv2.cvtColor(hsv[:, :, 2], cv2.COLOR_GRAY2BGR)


def preprocess_white_mask(crop_bgr: np.ndarray) -> np.ndarray:
    """Mask out everything except bright text pixels.

    Mob names are near-white but the leading level token is tinted
    yellow/orange/red by the game. Include saturated-bright colors so
    the level prefix survives into segmentation.
    """
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([179, 60, 255]))
    colored = cv2.inRange(hsv, np.array([0, 80, 180]), np.array([179, 255, 255]))
    mask = cv2.bitwise_or(white, colored)
    # Black background, white text where mask is set
    out = np.zeros_like(crop_bgr)
    out[mask > 0] = (255, 255, 255)
    return out


def preprocess_topblack_white(crop_bgr: np.ndarray) -> np.ndarray:
    """Subtract local mean (top-hat) then white-mask.

    Top-hat suppresses slow brightness gradients in the background while
    leaving narrow bright text strokes intact.
    """
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 9))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    _, binary = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def preprocess_value_clahe(crop_bgr: np.ndarray) -> np.ndarray:
    """CLAHE-enhanced V channel. Boosts local contrast across noisy bg."""
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 4))
    v = clahe.apply(v)
    return cv2.cvtColor(v, cv2.COLOR_GRAY2BGR)


PREPROCESS_STRATEGIES: list[tuple[str, callable]] = [
    ("raw", preprocess_raw),
    ("value", preprocess_value),
    ("white_mask", preprocess_white_mask),
    ("tophat_otsu", preprocess_topblack_white),
    ("value_clahe", preprocess_value_clahe),
]


# ---------------------------------------------------------------------------
# Maturity name database & matching (compact, Levenshtein-based)
# ---------------------------------------------------------------------------
# OCR frequently inserts spurious spaces inside long words ("Gokibu sagi"
# instead of "Gokibusagi") and may add trailing junk. We compare names in
# a "compact" form: lowercased, alphanumerics only, all whitespace removed.
# This collapses internal misreads while still detecting close matches via
# bounded Levenshtein.

@dataclass
class NameplateEntry:
    full: str          # display nameplate
    mob_name: str
    maturity_name: str
    level: int | None
    compact: str       # lowercase alphanumeric, no spaces

# Permissive level prefix: requires an actual L-like letter (l/L/I/i),
# optionally preceded by '1' (OCR misread). We do NOT accept a bare leading
# digit as a level — '15 Foo' should NOT be parsed as level 5; '15' may be
# part of the name (e.g. '50 Foot Android Party Girl').
#
# Accepted forms: "L15", "l 15", "I15", "i 15", "1L15", "1 l 15", "L15Foo"
_LEVEL_RE = re.compile(
    r"^[^a-zA-Z0-9]*(?:1[\s]?)?[lLiI][\s]?(\d{1,4})",
    re.UNICODE,
)
_COMPACT_RE = re.compile(r"[^a-z0-9]+")


def _compact(text: str) -> str:
    return _COMPACT_RE.sub("", text.lower())


_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def _strip_paren(name: str) -> str:
    """Strip parenthetical disambiguators like 'Atrox (Calypso)' -> 'Atrox'."""
    return _PAREN_RE.sub(" ", name).strip()


def build_nameplate_index(mobs: list[dict]) -> list[NameplateEntry]:
    """Build a list of all known nameplate strings from the mob database."""
    entries: list[NameplateEntry] = []
    seen: set[str] = set()
    for mob in mobs:
        raw_mob_name = (mob.get("Name") or "").strip()
        mob_name = _strip_paren(raw_mob_name)
        if not mob_name:
            continue
        maturities = mob.get("Maturities") or []
        for mat in maturities:
            mat_name = _strip_paren((mat.get("Name") or "").strip())
            mode = mat.get("NameMode") or "Empty"
            level = (mat.get("Properties") or {}).get("Level")
            if mode == "Suffix":
                full = f"{mob_name} {mat_name}".strip()
            elif mode == "Verbatim":
                full = mat_name
            else:  # Empty / None
                full = mob_name
            if not full:
                continue
            key = _compact(full)
            if key in seen:
                continue
            seen.add(key)
            entries.append(NameplateEntry(
                full=full,
                mob_name=mob_name,
                maturity_name=mat_name if mode == "Suffix" else "",
                level=int(level) if isinstance(level, (int, float)) else None,
                compact=key,
            ))
        if not maturities:
            key = _compact(mob_name)
            if key not in seen:
                seen.add(key)
                entries.append(NameplateEntry(
                    full=mob_name, mob_name=mob_name, maturity_name="",
                    level=None, compact=key,
                ))
    return entries


@dataclass
class NameMatch:
    nameplate: str
    mob_name: str
    maturity_name: str
    level: int | None
    score: float
    raw_ocr: str


def parse_level(text: str) -> tuple[int | None, str]:
    """Strip a leading level token like 'L42' / '1L42' / 'I 42' from text."""
    m = _LEVEL_RE.match(text)
    if m:
        try:
            return int(m.group(1)), text[m.end():].strip()
        except ValueError:
            pass
    return None, text


def _bounded_levenshtein(a: str, b: str, max_dist: int) -> int:
    """Levenshtein distance with early termination at max_dist + 1."""
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        row_min = i
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_dist:
            return max_dist + 1
        prev = curr
    return prev[lb]


def match_nameplate(
    raw_text: str, entries: list[NameplateEntry], min_score: float = 0.65,
) -> NameMatch | None:
    """Match raw OCR text against the nameplate index using compact matching.

    Algorithm:
    1. Strip the leading level token (handles 'L15', '1L15', etc.)
    2. Compact-normalize the rest (lowercase alnum, no spaces)
    3. For each entry, check substring containment first (fast path)
    4. Otherwise compute bounded Levenshtein vs the entry's compact form
    5. Score = 1 - distance / entry_length, with substring bonus
    """
    if not raw_text:
        return None

    level, rest = parse_level(raw_text)
    ocr_compact = _compact(rest)
    if len(ocr_compact) < 3:
        return None

    best: tuple[float, NameplateEntry] | None = None
    for entry in entries:
        ek = entry.compact
        elen = len(ek)
        if elen < 3:
            continue

        # Fast path: entry compact appears as a substring of OCR (or vice versa)
        if ek in ocr_compact:
            # Entry contained in OCR — strong match. Score by entry length
            # vs OCR length (favors long entries that consume more of OCR).
            score = 0.9 + 0.1 * (elen / max(elen, len(ocr_compact)))
            if best is None or score > best[0]:
                best = (score, entry)
            continue
        if ocr_compact in ek and len(ocr_compact) >= elen * 0.6:
            score = 0.85 * (len(ocr_compact) / elen)
            if best is None or score > best[0]:
                best = (score, entry)
            continue

        # Fuzzy fallback: bounded Levenshtein
        max_dist = max(2, elen // 6)  # ~17% allowed edit distance
        # Compare against ocr_compact, but trim ocr_compact to a window of
        # similar length (entry might be a prefix/suffix of a longer OCR string)
        window = ocr_compact
        if len(window) > elen + max_dist:
            # Try the substring closest in length
            window = ocr_compact[:elen + max_dist]
        dist = _bounded_levenshtein(window, ek, max_dist)
        if dist <= max_dist:
            score = 1.0 - (dist / elen)
            if best is None or score > best[0]:
                best = (score, entry)

    if best is None or best[0] < min_score:
        return None

    score, entry = best
    return NameMatch(
        nameplate=entry.full,
        mob_name=entry.mob_name,
        maturity_name=entry.maturity_name,
        level=level if level is not None else entry.level,
        score=score,
        raw_ocr=raw_text,
    )


# ---------------------------------------------------------------------------
# Per-strategy OCR + match
# ---------------------------------------------------------------------------

def run_ocr(crop_bgr: np.ndarray) -> tuple[str, float, float]:
    """Run ONNX OCR (single batched call via recognize_text_wide).

    The wide reader handles natural word segmentation. Returns
    (text, confidence, elapsed_ms).
    """
    t0 = time.perf_counter()
    result = onnxtr_recognizer.recognize_text_wide(
        crop_bgr, min_confidence=NAME_MIN_CONFIDENCE,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    if result is None:
        return "", 0.0, elapsed
    return result[0], result[1], elapsed


# ---------------------------------------------------------------------------
# Stateful per-frame test
# ---------------------------------------------------------------------------

@dataclass
class FrameState:
    last_template_pos: tuple[int, int] | None = None
    last_hp_kind: str = "none"
    last_hp_pct: float | None = None
    last_match: NameMatch | None = None
    last_raw_name: str = ""
    frames_since_match: int = 0


def should_reread_name(state: FrameState, hp_kind: str, hp_pct: float,
                       new_template_pos: tuple[int, int]) -> str:
    """Decide if we should run name OCR this frame.

    Triggers (in priority order):
      'initial'      - no prior match yet
      'kind_change'  - HP bar kind transitioned (red <-> green)
      'hp_up'        - HP increased noticeably (mob change; downward HP never triggers)
      'periodic'     - cheap insurance recheck every N frames
      'skip'         - reuse cached match

    Note: template position is NOT used as a trigger because the target lock
    chevron is a 3D world overlay — camera panning moves it on screen even
    though the target hasn't changed.
    """
    if state.last_match is None or state.last_template_pos is None:
        return "initial"
    if hp_kind != state.last_hp_kind:
        return "kind_change"
    if state.last_hp_pct is not None and hp_pct - state.last_hp_pct > HP_UP_THRESHOLD:
        return "hp_up"
    if state.frames_since_match >= NAME_RECHECK_INTERVAL:
        return "periodic"
    return "skip"


def capture_and_test(capturer, hwnd, template_raw, mask_bool, inv_bool,
                     heart_template, entries, state: FrameState,
                     idx: int) -> None:
    frame = capturer.capture_window(hwnd)
    if frame is None:
        print(f"  [frame {idx}] capture failed")
        return

    # Find player heart for exclusion (false positives near player status)
    exclusion = find_heart(frame, heart_template)

    pos, match_conf = find_template(frame, template_raw, mask_bool, inv_bool,
                                    exclusion=exclusion)
    if pos is None:
        print(f"  [frame {idx}] no target lock (best={match_conf:.2f})")
        state.last_template_pos = None
        return

    tx, ty = pos

    hp_region = extract_roi(frame, tx, ty, ROI_HP)
    shared_region = extract_roi(frame, tx, ty, ROI_SHARED)
    name_region = extract_roi(frame, tx, ty, ROI_NAME)

    hp_kind, hp_pct, hp_dbg = ("none", 0.0, "")
    if hp_region is not None:
        hp_kind, hp_pct, hp_dbg = read_hp_pct(hp_region)

    # If HP bar isn't recognizable, this is likely a template false positive
    if hp_kind == "none":
        print(f"  [frame {idx}] template at ({tx},{ty}) conf={match_conf:.2f} "
              f"REJECTED (no HP bar: {hp_dbg})")
        state.last_template_pos = None
        return

    is_shared, shared_dbg = (False, "")
    if shared_region is not None:
        is_shared, shared_dbg = detect_shared(shared_region)

    # Decide whether to re-read name
    reason = should_reread_name(state, hp_kind, hp_pct, pos)

    hp_str = f"{hp_kind.upper()}={hp_pct:.0%}"
    print(f"\n  [frame {idx}] template at ({tx},{ty}) conf={match_conf:.2f} "
          f"| HP={hp_str} ({hp_dbg}) "
          f"| shared={is_shared} ({shared_dbg}) "
          f"| name action={reason}")

    if reason == "skip" and state.last_match:
        print(f"    => Reusing: \"{state.last_match.nameplate}\" "
              f"(L{state.last_match.level}, {state.last_match.score:.0%})")
        state.last_hp_pct = hp_pct
        state.last_hp_kind = hp_kind
        state.last_template_pos = pos
        state.frames_since_match += 1
        return

    if name_region is None:
        print(f"    name ROI out of bounds")
        return

    # Try every preprocessing strategy
    print(f"    {'strategy':<14} {'OCR text':<50} {'conf':>6} {'time':>7} "
          f"{'matched':<48} {'score':>6}")
    print(f"    {'-'*14} {'-'*50} {'-'*6} {'-'*7} {'-'*48} {'-'*6}")

    best_match: NameMatch | None = None
    best_score = -1.0
    best_strategy = ""
    best_raw = ""

    for name, fn in PREPROCESS_STRATEGIES:
        prepped = fn(name_region)
        text, conf, ms = run_ocr(prepped)
        match = match_nameplate(text, entries) if text else None
        score = match.score if match else 0.0
        matched = match.nameplate if match else "-"
        if len(matched) > 47:
            matched = matched[:47] + ".."
        text_disp = (text or "-")
        if len(text_disp) > 48:
            text_disp = text_disp[:48] + ".."
        print(f"    {name:<14} {text_disp:<50} {conf:>5.0%} {ms:>5.1f}ms "
              f"{matched:<48} {score:>5.0%}")
        if match and score > best_score:
            best_score = score
            best_match = match
            best_strategy = name
            best_raw = text

    # Save the name ROI (4x for visibility) and the best preprocessed version
    cv2.imwrite(
        os.path.join(OUTPUT_DIR, f"frame_{idx:03d}_name_roi.png"),
        cv2.resize(name_region, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST),
    )
    if best_match:
        print(f"\n    => MATCH: \"{best_match.nameplate}\" "
              f"L{best_match.level} via [{best_strategy}] "
              f"({best_score:.0%}, raw=\"{best_raw}\")")
        state.last_match = best_match
        state.last_raw_name = best_raw
        state.frames_since_match = 0
    else:
        print(f"\n    => NO MATCH (raw best=\"{best_raw}\")")
        # Reset frame counter so we keep trying
        state.frames_since_match = 0

    state.last_hp_pct = hp_pct
    state.last_hp_kind = hp_kind
    state.last_template_pos = pos

    # Save annotated frame crop
    annotated = frame.copy()
    th, tw = template_raw.shape[:2]
    cv2.rectangle(annotated, (tx, ty), (tx + tw, ty + th), (0, 255, 0), 1)
    if hp_region is not None:
        rx = tx + ROI_HP["dx"]; ry = ty + ROI_HP["dy"]
        cv2.rectangle(annotated, (rx, ry), (rx + ROI_HP["w"], ry + ROI_HP["h"]),
                      (0, 0, 255), 1)
    if shared_region is not None:
        rx = tx + ROI_SHARED["dx"]; ry = ty + ROI_SHARED["dy"]
        cv2.rectangle(annotated, (rx, ry), (rx + ROI_SHARED["w"], ry + ROI_SHARED["h"]),
                      (0, 255, 255), 1)
    if name_region is not None:
        rx = tx + ROI_NAME["dx"]; ry = ty + ROI_NAME["dy"]
        cv2.rectangle(annotated, (rx, ry), (rx + ROI_NAME["w"], ry + ROI_NAME["h"]),
                      (255, 200, 0), 1)
    margin = 60
    ih, iw = frame.shape[:2]
    crop = annotated[
        max(0, ty - margin):min(ih, ty + th + margin),
        max(0, tx + ROI_NAME["dx"] - 10):min(iw, tx + ROI_NAME["dx"] + ROI_NAME["w"] + 30),
    ]
    cv2.imwrite(os.path.join(OUTPUT_DIR, f"frame_{idx:03d}_annotated.png"), crop)


def main():
    parser = argparse.ArgumentParser(description="Test target lock OCR")
    parser.add_argument("--loop", type=int, default=1,
                        help="Number of captures (1s apart)")
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    template_raw = cv2.imread(TEMPLATE_PATH, cv2.IMREAD_UNCHANGED)
    if template_raw is None:
        print(f"ERROR: cannot load template: {TEMPLATE_PATH}")
        sys.exit(1)
    if template_raw.shape[2] < 4:
        print(f"ERROR: template has no alpha channel")
        sys.exit(1)
    mask_bool = template_raw[:, :, 3] > 0
    inv_bool = ~mask_bool

    heart_template = cv2.imread(HEART_TEMPLATE_PATH, cv2.IMREAD_UNCHANGED)
    if heart_template is None:
        print(f"WARNING: heart template missing — false positives possible")

    print("Loading mob database...")
    config = AppConfig()
    dc = DataClient(config)
    mobs = dc.get_mobs()
    entries = build_nameplate_index(mobs)
    print(f"  Built {len(entries)} nameplate entries from {len(mobs)} mobs")

    print("Loading ONNX model...")
    if not onnxtr_recognizer.is_available():
        print("ERROR: ONNX runtime not available")
        sys.exit(1)
    # Warm-up
    onnxtr_recognizer.recognize_text_wide(
        np.zeros((14, 100, 3), dtype=np.uint8), min_confidence=0.0,
    )
    print("ONNX model ready.\n")

    hwnd = _platform.find_window_by_title_prefix(GAME_TITLE_PREFIX)
    if not hwnd:
        print(f"ERROR: game window not found")
        sys.exit(1)
    print(f"Game window: hwnd={hwnd}")

    capturer = ScreenCapturer(capture_backend="bitblt")
    state = FrameState()

    print(f"Capturing {args.loop} frame(s)...")
    for i in range(args.loop):
        if i > 0:
            time.sleep(1.0)
        capture_and_test(capturer, hwnd, template_raw, mask_bool, inv_bool,
                         heart_template, entries, state, i)

    print(f"\nOutput saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
