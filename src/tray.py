"""Windows System Tray Manager for Blind-Spotter.
Runs silently in the background tray with dynamic status icons and control menus.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
from typing import Optional

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

from src.detector import OnlookerDetector
from src.paths import get_log_dir
from src.settings_dialog import SettingsDialog

logger = logging.getLogger("blind_spotter.tray")


def create_tray_image(status: str = "active", size: int = 64) -> Image.Image:
    """Dynamically generate a sleek system tray icon for the given status."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 4
    # Circular dark badge background
    draw.ellipse([margin, margin, size - margin, size - margin], fill=(20, 24, 33, 255))

    if status == "alert":
        # Flashing Red Alert State
        color = (239, 68, 68, 255)
        draw.ellipse([margin + 2, margin + 2, size - margin - 2, size - margin - 2], outline=color, width=3)
        # Warning center dot
        draw.ellipse([size // 2 - 8, size // 2 - 8, size // 2 + 8, size // 2 + 8], fill=color)
    elif status == "paused":
        # Paused Amber State
        color = (245, 158, 11, 255)
        draw.ellipse([margin + 2, margin + 2, size - margin - 2, size - margin - 2], outline=color, width=2)
        # Two vertical pause bars
        bar_w = 4
        bar_h = 18
        top = (size - bar_h) // 2
        draw.rectangle([size // 2 - 6, top, size // 2 - 6 + bar_w, top + bar_h], fill=color)
        draw.rectangle([size // 2 + 2, top, size // 2 + 2 + bar_w, top + bar_h], fill=color)
    else:
        # Active Emerald Green Radar / Eye State
        color = (16, 185, 129, 255)
        outer_ring = (56, 189, 248, 255)
        draw.ellipse([margin + 2, margin + 2, size - margin - 2, size - margin - 2], outline=outer_ring, width=2)
        # Eye curve
        draw.arc([14, 20, size - 14, size - 20], start=0, end=180, fill=outer_ring, width=2)
        draw.arc([14, 20, size - 14, size - 20], start=180, end=360, fill=outer_ring, width=2)
        # Center active pupil
        draw.ellipse([size // 2 - 6, size // 2 - 6, size // 2 + 6, size // 2 + 6], fill=color)

    return img


class TrayApp:
    """Encapsulates the pystray tray application and its lifecycle."""

    def __init__(self, detector: OnlookerDetector, settings_dialog: SettingsDialog) -> None:
        self.detector = detector
        self.settings_dialog = settings_dialog
        self.icon: Optional[pystray.Icon] = None
        self._alert_timer: Optional[threading.Timer] = None

    def build_menu(self) -> pystray.Menu:
        """Create dynamic tray context menu."""
        return pystray.Menu(
            item(
                lambda text: f"Status: {'Paused' if self.detector.is_paused else 'Active (Watching)'}",
                action=None,
                enabled=False,
            ),
            item(
                lambda text: f"Engine: {self.detector.backend_name}",
                action=None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            item(
                lambda text: "Resume Monitoring" if self.detector.is_paused else "Pause Monitoring",
                self._on_toggle_pause,
                default=True,  # Primary double-click action
            ),
            item("Settings (Adjust Cooldown)...", self._on_open_settings),
            item("Open Diagnostics Logs", self._on_open_logs),
            item("Test Alert Notification", self._on_test_alert),
            pystray.Menu.SEPARATOR,
            item("About Blind-Spotter", self._on_about),
            item("Exit", self._on_exit),
        )

    def _on_toggle_pause(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.detector.toggle_pause()
        self.update_icon_state()

    def _on_open_settings(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.settings_dialog.show()

    def _on_open_logs(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        log_dir = get_log_dir()
        try:
            os.startfile(str(log_dir))
        except Exception as e:
            logger.warning("Could not open logs folder: %s", e)

    def _on_test_alert(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.detector.notifier.trigger_onlooker_alert(
            title="🔔 Blind-Spotter Test Alert",
            message="Test successful! Detection and notifications are working properly.",
            lock_screen=False,
            play_sound=self.detector.config.play_sound,
        )

    def _on_about(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        about_text = (
            "Blind-Spotter v1.1.0-Enterprise\n"
            "Stealthy onlooker & shoulder-surfing detection for your desktop.\n\n"
            "• 100% On-Device & Privacy First\n"
            "• Low CPU & Background Silent Operation\n"
            "• Windows Named Mutex & AppData Roaming Isolation\n\n"
            "An Ashnif Arnob Product\n"
            "Copyright (c) 2026 Ashnif Arnob. All rights reserved."
        )
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                about_text,
                "About Blind-Spotter",
                0x00000040 | 0x00010000,  # MB_ICONINFORMATION | MB_SETFOREGROUND
            )
        except Exception as e:
            logger.debug("Could not show about dialog: %s", e)

    def _on_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Exiting Blind-Spotter application...")
        self.detector.stop()
        if self.icon is not None:
            self.icon.stop()

    def update_icon_state(self, status: Optional[str] = None) -> None:
        """Update the icon graphic based on detector state."""
        if self.icon is None:
            return

        if status is None:
            status = "paused" if self.detector.is_paused else "active"

        self.icon.icon = create_tray_image(status)

    def pulse_alert(self) -> None:
        """Briefly pulse red icon when an onlooker alert occurs."""
        self.update_icon_state("alert")
        if self._alert_timer and self._alert_timer.is_alive():
            self._alert_timer.cancel()

        # Revert to active/paused state after 3 seconds
        self._alert_timer = threading.Timer(3.0, self.update_icon_state)
        self._alert_timer.daemon = True
        self._alert_timer.start()

    def run(self) -> None:
        """Initialize and run the system tray event loop."""
        initial_img = create_tray_image("active")
        self.icon = pystray.Icon(
            name="Blind-Spotter",
            icon=initial_img,
            title="Blind-Spotter — Shoulder-Surfing Detection",
            menu=self.build_menu(),
        )

        # Connect notifier to tray icon for native toast dispatching
        self.detector.notifier.set_tray_icon(self.icon)

        # Hook detector alert to pulse icon
        self.detector.on_alert = self.pulse_alert

        logger.info("Starting pystray system tray icon loop...")
        self.icon.run()
