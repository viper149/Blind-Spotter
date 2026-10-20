"""Tests for Windows notification and alerting system.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.notifier import Notifier, ICON_PATH


class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.notifier = Notifier()

    def test_icon_path_exists(self):
        # Ensure branding asset exists for notifications
        self.assertTrue(ICON_PATH.exists(), f"Branding icon missing at {ICON_PATH}")

    @patch("src.notifier.threading.Thread")
    def test_trigger_onlooker_alert_dispatches_threads(self, mock_thread):
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance

        # Test with sound and lock_screen enabled
        self.notifier.trigger_onlooker_alert(
            title="Alert",
            message="Onlooker found",
            lock_screen=True,
            play_sound=True,
        )

        # Should spawn 3 daemon threads (sound, toast, lock)
        self.assertEqual(mock_thread.call_count, 3)
        self.assertEqual(mock_instance.start.call_count, 3)

    @patch("src.notifier.threading.Thread")
    def test_trigger_onlooker_alert_sound_disabled(self, mock_thread):
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance

        # Test with sound and lock_screen disabled
        self.notifier.trigger_onlooker_alert(
            title="Alert",
            message="Onlooker found",
            lock_screen=False,
            play_sound=False,
        )

        # Should spawn only 1 thread (toast)
        self.assertEqual(mock_thread.call_count, 1)

    def test_tray_icon_notification(self):
        mock_tray = MagicMock()
        self.notifier.set_tray_icon(mock_tray)
        self.notifier._send_toast("Title", "Message")
        mock_tray.notify.assert_called_once_with("Message", "Title")


if __name__ == "__main__":
    unittest.main()
