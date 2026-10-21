"""Tests for paths, resource resolution, and single-instance mutex.
"""

import os
from pathlib import Path
import sys
import unittest

from src.paths import (
    acquire_single_instance_mutex,
    release_single_instance_mutex,
    get_resource_path,
    get_appdata_dir,
    get_local_appdata_dir,
    get_log_dir,
)


class TestPaths(unittest.TestCase):
    def test_get_resource_path_standard(self):
        icon_path = get_resource_path("assets/icon.png")
        self.assertTrue(icon_path.exists(), f"Resource not found at {icon_path}")
        proto_path = get_resource_path("models/deploy.prototxt")
        self.assertTrue(proto_path.exists(), f"Resource not found at {proto_path}")

    def test_get_resource_path_frozen_mock(self):
        # Mock sys._MEIPASS
        fake_bundle = Path("C:/mock/bundle")
        setattr(sys, "_MEIPASS", str(fake_bundle))
        try:
            resolved = get_resource_path("assets/icon.png")
            self.assertEqual(resolved, fake_bundle / "assets" / "icon.png")
        finally:
            delattr(sys, "_MEIPASS")

    def test_appdata_directories(self):
        appdata = get_appdata_dir()
        self.assertIsInstance(appdata, Path)
        self.assertTrue(appdata.exists())

        local_appdata = get_local_appdata_dir()
        self.assertIsInstance(local_appdata, Path)
        self.assertTrue(local_appdata.exists())

        log_dir = get_log_dir()
        self.assertIsInstance(log_dir, Path)
        self.assertTrue(log_dir.exists())

    def test_single_instance_mutex(self):
        test_mutex_name = "BlindSpotter_UnitTest_Mutex_12345"
        handle1 = acquire_single_instance_mutex(test_mutex_name)
        self.assertIsNotNone(handle1)

        # Attempt to acquire same mutex with active handle should return None on Windows
        if os.name == "nt":
            handle2 = acquire_single_instance_mutex(test_mutex_name)
            self.assertIsNone(handle2, "Second instance must not acquire active mutex")

        # Cleanup
        release_single_instance_mutex(handle1)


if __name__ == "__main__":
    unittest.main()
