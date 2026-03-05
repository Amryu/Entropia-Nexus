"""Diagnostic script: examine actual pixel values for problematic skill rows.

Loads image.png, extracts cells the same way as TestRealGameCells, and reports
the full matching pipeline including the column density text detection.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import cv2

from client.ocr.detector import DEFAULT_ROI_PIXELS, ROW_TEXT_RATIO
from client.ocr.font_matcher import (
    FontMatcher, BINARY_THRESHOLD, WIDTH_TOLERANCE,
    MIN_COL_DENSITY, MAX_TEXT_GAP, TEXT_DETECT_THRESHOLD,
)
from client.ocr.skill_parser import SkillMatcher, RankVerifier

IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "image.png")
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "arial-unicode-bold.ttf")

EXPECTED = [
    ("Agility",                 None,           "95"),
    ("Aim",                     "Marvelous",    "6256"),
    ("Alertness",               "Astonishing",  "6563"),
    ("Analysis",                "Specialist",   "4133"),
    ("Anatomy",                 "Great Master",  "11496"),
    ("Animal Lore",             "Qualified",    "1073"),
    ("Animal Taming",           "Trained",      "1247"),
    ("Archaeological Lore",     "Newbie",       "1"),
    ("Armor Technology",        "Poor",         "26"),
    ("Artefact Preservation",   "Newbie",       "1"),
    ("Athletics",               "Arch Master",  "8997"),
    ("Attachments Technology",  "Adept",        "1862"),
]


def main():
    game_image = cv2.imread(IMAGE_PATH)
    if game_image is None:
        print(f"ERROR: Cannot load {IMAGE_PATH}")
        return

    gray = cv2.cvtColor(game_image, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape
    ww, wh = img_w, img_h
    print(f"Image: {img_w}x{img_h}")

    # Use native ROI defaults directly (no template scaling for diagnostic)
    row_height = DEFAULT_ROI_PIXELS["row_offset"][3]
    row_pitch = DEFAULT_ROI_PIXELS["row_offset"][1]
    text_h = int(row_height * ROW_TEXT_RATIO)
    first_row_x = DEFAULT_ROI_PIXELS["first_row"][0]
    table_top = DEFAULT_ROI_PIXELS["first_row"][1]

    name_offset = DEFAULT_ROI_PIXELS["name_column_offset"][0]
    name_w = DEFAULT_ROI_PIXELS["name_column_offset"][2]
    name_s = first_row_x + name_offset
    name_e = name_s + name_w

    print(f"Row height: {row_height}, pitch: {row_pitch}, text zone: {text_h}")
    print(f"Table top: {table_top}, name cols: {name_s}-{name_e}")

    # Set up font matcher
    sm = SkillMatcher()
    rv = RankVerifier()
    all_skills = [s["name"] for s in sm.get_all_skills()]
    fm = FontMatcher(all_skills, rv._rank_names, font_path=FONT_PATH)
    fm.calibrate(wh)

    print(f"Font size: {fm.font_size}, calibrated: {fm.calibrated}")

    # Templates for problem skills
    for name in ["Aim", "Rifle", "Agility", "First Aid"]:
        tpl = fm._skill_templates.get(name)
        if tpl is not None:
            print(f"  Template '{name}': {tpl.shape[1]}x{tpl.shape[0]}")

    print("\n" + "="*80)
    print("ROW-BY-ROW ANALYSIS (with column density text detection)")
    print("="*80)

    for row_idx in range(12):
        y = table_top + row_idx * row_pitch
        if y + text_h > wh:
            break

        expected_name = EXPECTED[row_idx][0]
        name_gray = gray[y:y + text_h, name_s:name_e]
        name_bgr = game_image[y:y + text_h, name_s:name_e]

        # Binary
        cell_bin = ((name_gray > BINARY_THRESHOLD).astype(np.uint8)) * 255

        # === Two-level text detection ===
        extent = fm._detect_text_region(name_gray)

        # Old method (for comparison)
        cols_any = np.any(cell_bin > 0, axis=0)
        if np.any(cols_any):
            bc = np.where(cols_any)[0]
            old_text_width = int(bc[-1] - bc[0] + 1)
        else:
            old_text_width = 0

        # Brightness check
        bright_pct_80 = float(np.mean(name_gray > 80))
        bright_pct_120 = float(np.mean(name_gray > 120))

        # Color analysis
        bright_mask = name_gray > 80
        if np.sum(bright_mask) > 0:
            r_mean = np.mean(name_bgr[:,:,2][bright_mask])
            g_mean = np.mean(name_bgr[:,:,1][bright_mask])
            b_mean = np.mean(name_bgr[:,:,0][bright_mask])
        else:
            r_mean = g_mean = b_mean = 0

        # Matching results
        skill_match = fm.match_skill_name(name_gray)
        best_match = fm.best_skill_match(name_gray)

        # Print results
        is_orange = r_mean > 150 and g_mean < 120
        color_label = "ORANGE" if is_orange else "green/white"

        print(f"\n--- Row {row_idx}: Expected='{expected_name}' ({color_label}) ---")
        print(f"  RGB bright: R={r_mean:.0f} G={g_mean:.0f} B={b_mean:.0f}")
        print(f"  Brightness >80: {bright_pct_80:.4f}, >120: {bright_pct_120:.4f}")

        if extent:
            text_start, text_end = extent
            new_text_width = text_end - text_start
            print(f"  Text detection: extent=({text_start}, {text_end}), "
                  f"NEW width={new_text_width}px (OLD={old_text_width}px)")
        else:
            new_text_width = 0
            print(f"  Text detection: FAILED (OLD width={old_text_width}px)")

        print(f"  match_skill_name(): {skill_match}")
        print(f"  best_skill_match():  {best_match}")

        # Detailed scoring against expected template (with cropped cell)
        if extent and expected_name in fm._skill_templates:
            text_start, text_end = extent
            pad = WIDTH_TOLERANCE
            crop_left = max(0, text_start - pad)
            crop_right = min(cell_bin.shape[1], text_end + pad)
            cell_cropped = cell_bin[:, crop_left:crop_right]  # BINARY_THRESHOLD for matching

            tpl = fm._skill_templates[expected_name]
            tpl_bin = ((tpl > BINARY_THRESHOLD).astype(np.uint8)) * 255
            th, tw = tpl_bin.shape
            ch, cw = cell_cropped.shape

            if tw <= cw and th <= ch:
                score = cv2.matchTemplate(cell_cropped, tpl_bin, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(score)
                wr = min(tw, new_text_width) / max(tw, new_text_width) if new_text_width > 0 else 1.0
                adj = max_val * wr if max_val > 0 else max_val
                print(f"  CROPPED match vs '{expected_name}' ({tw}px): "
                      f"raw={max_val:.4f} wr={wr:.3f} adj={adj:.4f} "
                      f"(cropped cell={cw}px)")
            else:
                print(f"  CROPPED match vs '{expected_name}': template too big "
                      f"({tw}x{th} > {cw}x{ch})")

        # Width-filtered candidates with new text width
        if new_text_width > 0:
            filtered_names = []
            for w, entries in fm._skill_width_index.items():
                if abs(w - new_text_width) <= WIDTH_TOLERANCE:
                    filtered_names.extend([n for n, _ in entries])
            print(f"  Width candidates (±{WIDTH_TOLERANCE} of {new_text_width}): "
                  f"{len(filtered_names)} [{', '.join(sorted(filtered_names)[:8])}]")


if __name__ == "__main__":
    main()
