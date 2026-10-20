"""Blind-Spotter
Main entrypoint orchestrating the stealth background detector and Windows System Tray app.

An Ashnif Arnob Product
Copyright (c) 2026 Ashnif Arnob
"""

from __future__ import annotations

import logging
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
from src.settings_dialog import SettingsDialog
from src.tray import TrayApp


def setup_logging() -> None:
    """Setup logging format and levels."""
    log_level = logging.INFO if os.environ.get("BLIND_SPOTTER_DEBUG") else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("blind_spotter.main")
    logger.info("Initializing Blind-Spotter...")

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
        logger.info("Blind-Spotter terminated cleanly.")


if __name__ == "__main__":
    main()
