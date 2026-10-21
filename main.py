"""Blind-Spotter
Main entrypoint orchestrating the stealth background detector and Windows System Tray app.

An Ashnif Arnob Product
Copyright (c) 2026 Ashnif Arnob
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigManager
from src.detector import OnlookerDetector
from src.notifier import Notifier
from src.paths import (
    acquire_single_instance_mutex,
    release_single_instance_mutex,
    get_log_dir,
)
from src.settings_dialog import SettingsDialog
from src.tray import TrayApp


def setup_logging() -> None:
    """Setup dual logging: console (debug) and enterprise rotating file."""
    log_dir = get_log_dir()
    log_file = log_dir / "blind_spotter.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Rotating File Handler (2MB max, 3 backups)
    try:
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not configure file logger at {log_file}: {e}", file=sys.stderr)

    # 2. Console Handler (if running interactively)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_level = logging.DEBUG if os.environ.get("BLIND_SPOTTER_DEBUG") else logging.WARNING
    console_handler.setLevel(console_level)
    root_logger.addHandler(console_handler)


def main() -> None:
    # 0. Check if invoked in standalone settings mode (isolated Tcl/Tk process)
    if "--settings" in sys.argv:
        setup_logging()
        config_mgr = ConfigManager()
        settings_dialog = SettingsDialog(config_mgr=config_mgr)
        settings_dialog.run_standalone()
        sys.exit(0)

    # 1. Enforce single-instance mutex
    mutex_handle = acquire_single_instance_mutex()
    if mutex_handle is None:
        # Another instance is already active
        print("Blind-Spotter is already running in the Windows System Tray.")
        sys.exit(0)

    # 2. Initialize enterprise logging
    setup_logging()
    logger = logging.getLogger("blind_spotter.main")
    logger.info("Initializing Blind-Spotter v1.1.0-Enterprise...")

    config_mgr = ConfigManager()
    notifier = Notifier()
    detector = OnlookerDetector(config_mgr=config_mgr, notifier=notifier)
    settings_dialog = SettingsDialog(config_mgr=config_mgr)
    tray_app = TrayApp(detector=detector, settings_dialog=settings_dialog)

    def handle_signal(sig, frame):
        logger.info("Termination signal received. Shutting down...")
        detector.stop()
        if tray_app.icon is not None:
            tray_app.icon.stop()
        release_single_instance_mutex(mutex_handle)
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except Exception:
        pass

    # Start background detection thread
    detector.start()

    # Start system tray loop (blocks on main thread until user clicks Exit)
    try:
        tray_app.run()
    finally:
        detector.stop()
        release_single_instance_mutex(mutex_handle)
        logger.info("Blind-Spotter terminated cleanly.")


if __name__ == "__main__":
    main()
