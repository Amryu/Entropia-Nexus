import unittest

import cv2
import numpy as np

from client.ocr.detector import (
    NATIVE_TEMPLATE_H,
    NATIVE_TEMPLATE_W,
    TEMPLATE_HEIGHT_RATIO,
    TEMPLATE_OFFSET_X,
    TEMPLATE_OFFSET_Y,
    TEMPLATE_WIDTH_RATIO,
    SkillsWindowDetector,
)


class _DummyCapturer:
    pass


class TestDetectorSingleScale(unittest.TestCase):
    def _make_detector(self) -> SkillsWindowDetector:
        detector = SkillsWindowDetector(_DummyCapturer())
        template = np.zeros((NATIVE_TEMPLATE_H, NATIVE_TEMPLATE_W), dtype=np.uint8)
        cv2.putText(
            template, "SKILLS", (1, 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, 255, 1, cv2.LINE_AA,
        )
        detector._template = template
        detector._template_mask_bool = None
        detector._template_inv_bool = None
        return detector

    def test_find_by_template_detects_exact_size(self):
        detector = self._make_detector()
        gray = np.full((1400, 2400), 20, dtype=np.uint8)
        tx, ty = 700, 200
        gray[ty:ty + NATIVE_TEMPLATE_H, tx:tx + NATIVE_TEMPLATE_W] = detector._template

        bounds = detector._find_by_template(gray, 0, 0)

        self.assertIsNotNone(bounds)
        expected_w = int(NATIVE_TEMPLATE_W / TEMPLATE_WIDTH_RATIO)
        expected_h = int(NATIVE_TEMPLATE_H / TEMPLATE_HEIGHT_RATIO)
        expected_x = tx - int(expected_w * TEMPLATE_OFFSET_X)
        expected_y = ty - int(expected_h * TEMPLATE_OFFSET_Y)
        self.assertEqual(bounds[0], expected_x)
        self.assertEqual(bounds[1], expected_y)
        self.assertEqual(bounds[2], expected_w)
        self.assertEqual(bounds[3], expected_h)
        self.assertEqual(detector._title_match[2], NATIVE_TEMPLATE_W)
        self.assertEqual(detector._title_match[3], NATIVE_TEMPLATE_H)

    def test_quick_adjust_tracks_shift_single_scale(self):
        detector = self._make_detector()
        tx, ty = 700, 200
        panel_w = int(NATIVE_TEMPLATE_W / TEMPLATE_WIDTH_RATIO)
        panel_h = int(NATIVE_TEMPLATE_H / TEMPLATE_HEIGHT_RATIO)
        panel_x = tx - int(panel_w * TEMPLATE_OFFSET_X)
        panel_y = ty - int(panel_h * TEMPLATE_OFFSET_Y)

        detector._game_origin = (0, 0)
        detector._cached_bounds = (panel_x, panel_y, panel_w, panel_h)
        detector._title_match = (tx - panel_x, ty - panel_y, NATIVE_TEMPLATE_W, NATIVE_TEMPLATE_H)

        shifted = np.full((1400, 2400), 20, dtype=np.uint8)
        shifted[204:204 + NATIVE_TEMPLATE_H, 706:706 + NATIVE_TEMPLATE_W] = detector._template
        shifted_bgr = cv2.cvtColor(shifted, cv2.COLOR_GRAY2BGR)

        moved = detector.quick_adjust(shifted_bgr)

        self.assertIsNotNone(moved)
        self.assertEqual(moved[0], panel_x + 6)
        self.assertEqual(moved[1], panel_y + 4)
        self.assertEqual(moved[2], panel_w)
        self.assertEqual(moved[3], panel_h)
