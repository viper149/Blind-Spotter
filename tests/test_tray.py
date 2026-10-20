"""Tests for system tray icon generator and menu builder.
"""

import unittest
from unittest.mock import MagicMock

from PIL import Image

from src.tray import create_tray_image, TrayApp


class TestTray(unittest.TestCase):
    def test_create_tray_image_modes(self):
        for status in ("active", "paused", "alert", "unknown_defaults_to_active"):
            img = create_tray_image(status, size=64)
            self.assertIsInstance(img, Image.Image)
            self.assertEqual(img.size, (64, 64))
            self.assertEqual(img.mode, "RGBA")

    def test_tray_menu_structure(self):
        mock_detector = MagicMock()
        mock_detector.is_paused = False
        mock_detector.backend_name = "OpenCV DNN"
        mock_settings = MagicMock()

        app = TrayApp(detector=mock_detector, settings_dialog=mock_settings)
        menu = app.build_menu()
        self.assertIsNotNone(menu)

        # Toggle pause call
        app._on_toggle_pause(None, None)
        mock_detector.toggle_pause.assert_called_once()


if __name__ == "__main__":
    unittest.main()
