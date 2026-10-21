"""Tests for configuration manager and AppConfig dataclass.
"""

from pathlib import Path
import tempfile
import unittest

from src.config import AppConfig, ConfigManager


class TestAppConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = AppConfig()
        self.assertEqual(cfg.cooldown_seconds, 10)
        self.assertFalse(cfg.lock_screen_on_alert)
        self.assertAlmostEqual(cfg.confidence_threshold, 0.5)
        self.assertEqual(cfg.camera_index, 0)
        self.assertAlmostEqual(cfg.sample_interval, 0.2)
        self.assertEqual(cfg.consecutive_frames_required, 2)
        self.assertTrue(cfg.play_sound)

    def test_from_dict_and_limits(self):
        data = {
            "cooldown_seconds": -5,
            "confidence_threshold": 1.5,
            "camera_index": -1,
            "sample_interval": 0.05,
            "consecutive_frames_required": 0,
            "lock_screen_on_alert": 1,
            "play_sound": 0,
            "unknown_field": "ignore_me",
        }
        cfg = AppConfig.from_dict(data)
        # Verify clamped and coerced values
        self.assertEqual(cfg.cooldown_seconds, 1)
        self.assertAlmostEqual(cfg.confidence_threshold, 1.0)
        self.assertEqual(cfg.camera_index, 0)
        self.assertAlmostEqual(cfg.sample_interval, 0.1)
        self.assertEqual(cfg.consecutive_frames_required, 1)
        self.assertTrue(cfg.lock_screen_on_alert)
        self.assertFalse(cfg.play_sound)
        self.assertFalse(hasattr(cfg, "unknown_field"))

    def test_to_dict_roundtrip(self):
        cfg = AppConfig(cooldown_seconds=15, confidence_threshold=0.65)
        d = cfg.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["cooldown_seconds"], 15)
        self.assertAlmostEqual(d["confidence_threshold"], 0.65)
        cfg2 = AppConfig.from_dict(d)
        self.assertEqual(cfg, cfg2)


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "test_config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_creates_default_when_missing(self):
        mgr = ConfigManager(self.config_path)
        self.assertTrue(self.config_path.exists())
        self.assertEqual(mgr.config.cooldown_seconds, 10)

    def test_save_and_reload(self):
        mgr = ConfigManager(self.config_path)
        mgr.save(AppConfig(cooldown_seconds=20, camera_index=1))

        mgr2 = ConfigManager(self.config_path)
        self.assertEqual(mgr2.config.cooldown_seconds, 20)
        self.assertEqual(mgr2.config.camera_index, 1)

    def test_update(self):
        mgr = ConfigManager(self.config_path)
        updated = mgr.update(cooldown_seconds=30, play_sound=False)
        self.assertEqual(updated.cooldown_seconds, 30)
        self.assertFalse(updated.play_sound)
        self.assertEqual(mgr.config.cooldown_seconds, 30)

    def test_corrupt_json_fallback(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json file")

        mgr = ConfigManager(self.config_path)
        self.assertEqual(mgr.config.cooldown_seconds, 10)


if __name__ == "__main__":
    unittest.main()
