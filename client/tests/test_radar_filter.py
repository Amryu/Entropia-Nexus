"""Tests for radar coordinate filtering: digit correction, velocity gate,
two-tier speed detection, teleport detection, and RGB-spread preprocessing."""

import unittest

import numpy as np

from client.ocr.radar_detector import (
    RadarDetector,
    RADAR_TELEPORT_CONFIRM_COUNT,
    RADAR_TELEPORT_THRESHOLD,
    RADAR_WALK_SPEED,
    RADAR_VEHICLE_SPEED,
    RADAR_OCCLUSION_VEHICLE_ASSUME_S,
    RADAR_OCCLUSION_RESET_S,
)


class _FakeConfig:
    radar_enabled = True
    radar_last_circle = [100, 100, 95]
    radar_base_radius = None
    radar_lon_roi = (-87, 93, 80, 18)
    radar_lat_roi = (-87, 110, 80, 18)
    radar_teleport_confirm = RADAR_TELEPORT_CONFIRM_COUNT
    radar_max_walk_speed = RADAR_WALK_SPEED
    radar_max_vehicle_speed = RADAR_VEHICLE_SPEED


class _FakeEventBus:
    def subscribe(self, *a, **kw):
        pass

    def publish(self, *a, **kw):
        pass


def _make_detector(**config_overrides) -> RadarDetector:
    config = _FakeConfig()
    for k, v in config_overrides.items():
        setattr(config, k, v)
    return RadarDetector(config, _FakeEventBus(), None)


class TestCorrectDigitFlip(unittest.TestCase):
    """Tests for RadarDetector._correct_digit_flip."""

    def test_no_change(self):
        self.assertEqual(RadarDetector._correct_digit_flip(72282, 72282, 5), 72282)

    def test_small_change_within_threshold(self):
        self.assertEqual(RadarDetector._correct_digit_flip(72287, 72282, 10), 72287)

    def test_single_100s_flip_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(72582, 72282, 5), 72282)

    def test_single_1000s_flip_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(73282, 72282, 5), 72282)

    def test_single_10000s_flip_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(82282, 72282, 5), 72282)

    def test_two_high_digit_flips_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(85282, 82282, 5), 82282)

    def test_three_high_digit_flips_not_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(53182, 72282, 5), 53182)

    def test_teleport_many_digits_differ_not_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(50000, 72282, 5), 50000)

    def test_different_digit_count_not_corrected(self):
        self.assertEqual(RadarDetector._correct_digit_flip(7228, 72282, 5), 7228)

    def test_common_ocr_confusions(self):
        # 8↔5 in 100s
        self.assertEqual(RadarDetector._correct_digit_flip(72582, 72282, 5), 72282)
        # 6↔9 in 100s
        self.assertEqual(RadarDetector._correct_digit_flip(72982, 72682, 5), 72682)
        # 5↔6 in 1000s
        self.assertEqual(RadarDetector._correct_digit_flip(76282, 75282, 5), 75282)


class TestFilterCoordinates(unittest.TestCase):
    """Tests for RadarDetector._filter_coordinates with two-tier speed."""

    def test_first_reading_always_accepted(self):
        det = _make_detector()
        r = det._filter_coordinates(72282, 82066, 0.95, 1000.0)
        self.assertEqual(r, (72282, 82066))

    def test_stationary_always_accepted(self):
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        for i in range(10):
            r = det._filter_coordinates(72282, 82066, 0.95, t + (i + 1) * 0.5)
            self.assertIsNotNone(r)

    def test_walking_speed_accepted(self):
        """Movement at ~8 m/s (within walk cap of 10) accepted."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        # 4 units in 0.5s = 8 m/s
        r = det._filter_coordinates(72286, 82069, 0.95, t + 0.5)
        self.assertIsNotNone(r)

    def test_above_walk_speed_rejected_in_walk_mode(self):
        """Movement at ~20 m/s rejected while in walking mode."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        # 10 units in 0.5s = 20 m/s > walk cap 10
        r = det._filter_coordinates(72292, 82066, 0.95, t + 0.5)
        self.assertIsNone(r)

    def test_vehicle_mode_accepts_higher_speed(self):
        """After entering vehicle mode, speeds up to 30 m/s are accepted."""
        det = _make_detector()
        det._vehicle_mode = True  # force vehicle mode
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        # 12 units in 0.5s = 24 m/s — above walk, below vehicle
        r = det._filter_coordinates(72294, 82066, 0.95, t + 0.5)
        self.assertIsNotNone(r)

    def test_mode_switches_to_vehicle_on_sustained_speed(self):
        """After enough fast samples, mode switches from walking to vehicle."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # Force vehicle mode by filling speed samples above walk speed
        for i in range(10):
            det._speed_samples.append(15.0)  # 15 m/s

        self.assertFalse(det._vehicle_mode)
        # Next accepted reading triggers mode evaluation
        r = det._filter_coordinates(72286, 82069, 0.95, t + 0.5)
        self.assertTrue(det._vehicle_mode)

    def test_mode_switches_back_to_walking(self):
        """After enough slow samples, mode reverts from vehicle to walking."""
        det = _make_detector()
        det._vehicle_mode = True
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # Fill speed samples with walking speed
        for i in range(10):
            det._speed_samples.append(3.0)

        # Next reading triggers mode evaluation
        det._filter_coordinates(72283, 82067, 0.95, t + 0.5)
        self.assertFalse(det._vehicle_mode)

    def test_single_jitter_spike_does_not_trigger_vehicle_mode(self):
        """One high-speed outlier among walking samples doesn't switch mode."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # 9 walking samples + 1 spike
        for i in range(9):
            det._speed_samples.append(3.0)
        det._speed_samples.append(25.0)  # single jitter spike

        det._filter_coordinates(72283, 82067, 0.95, t + 0.5)
        self.assertFalse(det._vehicle_mode, "Single spike should not trigger vehicle mode")

    def test_100s_flip_corrected_not_rejected(self):
        """OCR error flipping a 100s digit gets corrected."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        det._filter_coordinates(72282, 82066, 0.95, t + 0.5)
        det._filter_coordinates(72282, 82066, 0.95, t + 1.0)
        r = det._filter_coordinates(72582, 82066, 0.90, t + 1.5)
        self.assertIsNotNone(r, "Should correct, not reject")
        lon, _ = r
        self.assertAlmostEqual(lon, 72282, delta=10)

    def test_teleport_accepted_after_consistent_reads(self):
        """100+ jump accepted as teleport after enough consistent reads."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        accepted = None
        for i in range(RADAR_TELEPORT_CONFIRM_COUNT + 1):
            r = det._filter_coordinates(
                50000 + i * 3, 60000 + i * 2, 0.95, t + 0.5 + i * 0.5,
            )
            if r is not None:
                accepted = r

        self.assertIsNotNone(accepted)
        self.assertAlmostEqual(accepted[0], 50000, delta=50)

    def test_random_noise_never_accepted_as_teleport(self):
        """Inconsistent rejected reads don't trigger teleport acceptance."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        noise = [(50000, 60000), (30000, 40000), (90000, 10000),
                 (50500, 60500), (31000, 41000), (80000, 20000)]
        for i, (lon, lat) in enumerate(noise):
            r = det._filter_coordinates(lon, lat, 0.90, t + 0.5 + i * 0.5)
            self.assertIsNone(r, f"Noise tick {i} should be rejected")

    def test_between_vehicle_cap_and_teleport_rejected_not_teleport(self):
        """Jumps between vehicle cap and 100 are rejected but don't enter teleport logic."""
        det = _make_detector()
        det._vehicle_mode = True
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # 50 unit jump: above vehicle cap (30*0.5=15), below teleport threshold (100)
        r = det._filter_coordinates(72332, 82066, 0.95, t + 0.5)
        self.assertIsNone(r)
        self.assertEqual(len(det._rejected_streak), 0, "Should not enter teleport streak")

    def test_recalibrate_resets_filter_state(self):
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        det._vehicle_mode = True
        det._speed_samples.append(20.0)

        det.trigger_recalibrate()

        self.assertFalse(det._vehicle_mode)
        self.assertEqual(len(det._speed_samples), 0)
        r = det._filter_coordinates(50000, 60000, 0.95, t + 1.0)
        self.assertEqual(r, (50000, 60000))

    def test_config_overrides_speed_caps(self):
        det = _make_detector(radar_max_walk_speed=20, radar_max_vehicle_speed=50)
        self.assertEqual(det._walk_speed, 20)
        self.assertEqual(det._vehicle_speed, 50)

    def test_config_overrides_teleport_confirm(self):
        det = _make_detector(radar_teleport_confirm=10)
        self.assertEqual(det._teleport_confirm, 10)


class TestOcclusionRecovery(unittest.TestCase):
    """Tests for graceful recovery after OCR starvation (occluded radar)."""

    def test_short_occlusion_uses_vehicle_speed(self):
        """After 3s+ gap, vehicle speed is used for max allowance."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # 5s gap, moved 100 units (20 m/s — above walk, below vehicle)
        r = det._filter_coordinates(72382, 82066, 0.95, t + 5.0)
        self.assertIsNotNone(r, "Should accept: 100 units / 5s = 20 m/s < vehicle cap 30")

    def test_short_occlusion_walking_mode_still_accepts_vehicle_distance(self):
        """In walking mode, a 4s gap still uses vehicle speed for recovery."""
        det = _make_detector()
        self.assertFalse(det._vehicle_mode)
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # 4s gap, 80 units (20 m/s) — above walk cap but within vehicle cap * dt
        r = det._filter_coordinates(72362, 82066, 0.95, t + 4.0)
        self.assertIsNotNone(r, "Vehicle speed assumed during occlusion")

    def test_long_occlusion_resets_filter(self):
        """After 30s+ gap, filter resets entirely — any reading accepted."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)
        det._vehicle_mode = True
        for i in range(10):
            det._speed_samples.append(20.0)

        # 35s gap, completely different location
        r = det._filter_coordinates(50000, 60000, 0.95, t + 35.0)
        self.assertEqual(r, (50000, 60000))
        self.assertFalse(det._vehicle_mode, "Mode should reset after long occlusion")
        self.assertEqual(len(det._speed_samples), 0)

    def test_medium_occlusion_accepts_within_vehicle_range(self):
        """After 3s+ gap, readings within vehicle-speed distance accepted."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # 4s gap, 18 units (4.5 m/s) — well within vehicle cap * 4s
        r = det._filter_coordinates(72300, 82080, 0.95, t + 4.0)
        self.assertIsNotNone(r)

    def test_no_occlusion_normal_filtering(self):
        """Normal tick interval doesn't trigger occlusion logic."""
        det = _make_detector()
        t = 1000.0
        det._filter_coordinates(72282, 82066, 0.95, t)

        # Normal 0.5s gap, 15 units (30 m/s) — exceeds walk cap, no occlusion
        r = det._filter_coordinates(72297, 82066, 0.95, t + 0.5)
        self.assertIsNone(r, "Without occlusion, walk mode rejects 30 m/s")


class TestSaturationMask(unittest.TestCase):
    """Tests for the Gaussian saturation mask."""

    def test_colored_background_suppressed(self):
        green = np.full((14, 45, 3), [50, 200, 50], dtype=np.uint8)
        result, _ = RadarDetector._apply_saturation_mask(green)
        self.assertLess(result.mean(), 10)

    def test_white_text_preserved(self):
        white = np.full((14, 45, 3), [240, 240, 238], dtype=np.uint8)
        result, _ = RadarDetector._apply_saturation_mask(white)
        self.assertGreater(result.mean(), 190)

    def test_mixed_preserves_text_removes_background(self):
        img = np.zeros((20, 40, 3), dtype=np.uint8)
        img[:10, :] = [50, 200, 50]
        img[10:, :] = [235, 240, 238]
        result, _ = RadarDetector._apply_saturation_mask(img)
        self.assertLess(result[:10, :].mean(), 20)
        self.assertGreater(result[10:, :].mean(), 190)

    def test_gaussian_smooth_transition(self):
        """Saturation mask produces smooth gradients, not hard cutoffs."""
        img = np.zeros((1, 5, 3), dtype=np.uint8)
        img[0, 0] = [240, 240, 240]  # rel_sat = 0.0
        img[0, 1] = [230, 240, 240]  # rel_sat ≈ 0.04
        img[0, 2] = [200, 240, 240]  # rel_sat ≈ 0.17
        img[0, 3] = [150, 240, 240]  # rel_sat ≈ 0.38
        img[0, 4] = [50, 240, 240]   # rel_sat ≈ 0.79

        result, _ = RadarDetector._apply_saturation_mask(img)
        brightnesses = [result[0, i].mean() for i in range(5)]
        for i in range(len(brightnesses) - 1):
            self.assertGreaterEqual(
                brightnesses[i], brightnesses[i + 1],
                f"Pixel {i} should be brighter than pixel {i+1}",
            )
        self.assertGreater(brightnesses[0], 230)
        self.assertLess(brightnesses[4], 10)


if __name__ == "__main__":
    unittest.main()
