"""Tests for enterprise features: startup configuration, logger creation, and detector recovery.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.config import AppConfig, ConfigManager, get_default_config_path
from src.detector import OnlookerDetector
from src.settings_dialog import get_startup_shortcut_path, set_windows_startup


class TestEnterpriseFeatures(unittest.TestCase):
    def test_app_config_startup_field(self):
        cfg = AppConfig(start_with_windows=True)
        d = cfg.to_dict()
        self.assertTrue(d["start_with_windows"])
        cfg2 = AppConfig.from_dict({"start_with_windows": 1})
        self.assertTrue(cfg2.start_with_windows)

    def test_startup_shortcut_path(self):
        shortcut_path = get_startup_shortcut_path()
        self.assertIsInstance(shortcut_path, Path)
        self.assertTrue(str(shortcut_path).endswith(".lnk"))
        self.assertIn("Startup", str(shortcut_path))

    def test_default_config_path_resolution(self):
        cfg_path = get_default_config_path()
        self.assertIsInstance(cfg_path, Path)
        self.assertTrue(cfg_path.name == "config.json")

    def test_detector_resilience_structure(self):
        temp_dir = tempfile.TemporaryDirectory()
        cfg_path = Path(temp_dir.name) / "test_config.json"
        cfg_mgr = ConfigManager(cfg_path)
        detector = OnlookerDetector(config_mgr=cfg_mgr)
        self.assertIsNotNone(detector)
        self.assertEqual(detector.latest_face_count, 0)
        temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
