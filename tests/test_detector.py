"""Tests for OnlookerDetector CV engine and temporal state machine.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np

from src.config import AppConfig, ConfigManager
from src.detector import OnlookerDetector


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "test_config.json"
        self.config_mgr = ConfigManager(self.config_path)
        self.notifier = MagicMock()
        self.detector = OnlookerDetector(config_mgr=self.config_mgr, notifier=self.notifier)

    def tearDown(self):
        if self.detector.is_running:
            self.detector.stop()
        self.temp_dir.cleanup()

    def test_backend_initialization(self):
        # Should initialize OpenCV DNN or Haar Cascade fallback
        self.assertIn("OpenCV DNN", self.detector.backend_name)
        self.assertFalse(self.detector.is_running)
        self.assertFalse(self.detector.is_paused)

    def test_dummy_frame_inference(self):
        # 640x480 blank frame
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        boxes = self.detector._detect_faces(dummy)
        self.assertIsInstance(boxes, list)
        self.assertEqual(len(boxes), 0)

    def test_pause_resume_toggle(self):
        self.assertFalse(self.detector.is_paused)
        self.detector.pause()
        self.assertTrue(self.detector.is_paused)
        self.detector.resume()
        self.assertFalse(self.detector.is_paused)
        paused = self.detector.toggle_pause()
        self.assertTrue(paused)
        self.assertTrue(self.detector.is_paused)

    def test_status_callback(self):
        status_updates = []
        detector = OnlookerDetector(
            config_mgr=self.config_mgr,
            notifier=self.notifier,
            on_status_change=lambda s: status_updates.append(s),
        )
        detector.pause()
        detector.resume()
        self.assertEqual(status_updates, ["Paused", "Active"])


if __name__ == "__main__":
    unittest.main()
