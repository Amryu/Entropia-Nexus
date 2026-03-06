import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from client.core.config import AppConfig, load_config, save_config, validate_config


class TestLoadConfigDefaults(unittest.TestCase):
    """Test loading config when no file exists."""

    def test_load_defaults_no_file(self):
        config = load_config("nonexistent_path_12345.json")
        self.assertEqual(config.poll_interval_ms, 500)
        self.assertEqual(config.loot_group_window_ms, 1500)
        self.assertAlmostEqual(config.overlay_opacity, 0.85)
        self.assertEqual(config.nexus_base_url, "https://entropianexus.com")
        self.assertEqual(config.api_base_url, "https://api.entropianexus.com")
        self.assertEqual(config.ocr_capture_backend, "auto")
        self.assertEqual(config.loot_blacklist, [])
        self.assertEqual(config.loot_blacklist_per_mob, {})

    def test_load_with_overrides(self, tmp_path=None):
        path = "_test_config_overrides.json"
        try:
            with open(path, "w") as f:
                json.dump({"poll_interval_ms": 1000, "overlay_opacity": 0.5}, f)
            config = load_config(path)
            self.assertEqual(config.poll_interval_ms, 1000)
            self.assertAlmostEqual(config.overlay_opacity, 0.5)
            # Non-overridden defaults still apply
            self.assertEqual(config.loot_group_window_ms, 1500)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_unknown_fields_ignored(self):
        path = "_test_config_unknown.json"
        try:
            with open(path, "w") as f:
                json.dump({"poll_interval_ms": 500, "totally_fake_field": True}, f)
            config = load_config(path)
            self.assertEqual(config.poll_interval_ms, 500)
            self.assertFalse(hasattr(config, "totally_fake_field"))
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestSaveAndReload(unittest.TestCase):

    def test_save_and_reload(self):
        path = "_test_config_roundtrip.json"
        try:
            config = AppConfig(
                poll_interval_ms=750,
                overlay_opacity=0.6,
                loot_blacklist=["Shrapnel"],
            )
            save_config(config, path)
            loaded = load_config(path)
            self.assertEqual(loaded.poll_interval_ms, 750)
            self.assertAlmostEqual(loaded.overlay_opacity, 0.6)
            self.assertEqual(loaded.loot_blacklist, ["Shrapnel"])
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestTupleListConversion(unittest.TestCase):

    def test_lists_converted_to_tuples(self):
        path = "_test_config_tuples.json"
        try:
            with open(path, "w") as f:
                json.dump({
                    "hunt_overlay_position": [100, 200],
                    "mob_name_region": [10, 20, 300, 40],
                }, f)
            config = load_config(path)
            self.assertEqual(config.hunt_overlay_position, (100, 200))
            self.assertEqual(config.mob_name_region, (10, 20, 300, 40))
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestLegacyOverlayMigration(unittest.TestCase):

    def test_legacy_overlay_position_migrated(self):
        path = "_test_config_legacy.json"
        try:
            with open(path, "w") as f:
                json.dump({"overlay_position": [999, 888]}, f)
            config = load_config(path)
            self.assertEqual(config.hunt_overlay_position, (999, 888))
            self.assertEqual(config.progress_overlay_position, (999, 888))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_legacy_does_not_override_explicit(self):
        path = "_test_config_legacy2.json"
        try:
            with open(path, "w") as f:
                json.dump({
                    "overlay_position": [999, 888],
                    "hunt_overlay_position": [111, 222],
                }, f)
            config = load_config(path)
            self.assertEqual(config.hunt_overlay_position, (111, 222))
            self.assertEqual(config.progress_overlay_position, (999, 888))
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestValidateConfig(unittest.TestCase):

    def test_validate_valid_config(self):
        config = AppConfig(
            chat_log_path=__file__,  # exists
            overlay_opacity=0.85,
            poll_interval_ms=500,
            ocr_confidence_threshold=0.7,
        )
        errors = validate_config(config)
        self.assertEqual(errors, [])

    def test_validate_bad_opacity(self):
        config = AppConfig(chat_log_path=__file__, overlay_opacity=1.5)
        errors = validate_config(config)
        self.assertTrue(any("overlay_opacity" in e for e in errors))

    def test_validate_bad_poll_interval(self):
        config = AppConfig(chat_log_path=__file__, poll_interval_ms=50)
        errors = validate_config(config)
        self.assertTrue(any("poll_interval_ms" in e for e in errors))

    def test_validate_bad_ocr_threshold(self):
        config = AppConfig(chat_log_path=__file__, ocr_confidence_threshold=2.0)
        errors = validate_config(config)
        self.assertTrue(any("ocr_confidence_threshold" in e for e in errors))

    def test_validate_bad_capture_backend(self):
        config = AppConfig(chat_log_path=__file__, ocr_capture_backend="nope")
        errors = validate_config(config)
        self.assertTrue(any("ocr_capture_backend" in e for e in errors))

    def test_validate_missing_chat_log(self):
        config = AppConfig(chat_log_path="")
        errors = validate_config(config)
        self.assertTrue(any("chat_log_path" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
