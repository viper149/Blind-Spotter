"""Notification and Alert System for Blind-Spotter.
Delivers native Windows notifications, audible alerts, and optional workstation locking.
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
import threading
import winsound
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("blind_spotter.notifier")

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


class Notifier:
    """Manages notifications and defensive alert actions on Windows."""

    DEFAULT_TITLE = "⚠️ Blind-Spotter Alert"
    DEFAULT_MESSAGE = "Someone is detected behind you! Keep sensitive data safe."

    def __init__(self, tray_icon: Optional[Any] = None) -> None:
        self.tray_icon = tray_icon

    def set_tray_icon(self, tray_icon: Any) -> None:
        self.tray_icon = tray_icon

    def trigger_onlooker_alert(
        self,
        title: str = DEFAULT_TITLE,
        message: str = DEFAULT_MESSAGE,
        lock_screen: bool = False,
        play_sound: bool = True,
    ) -> None:
        """Trigger an onlooker detection alert asynchronously."""
        logger.warning("ONLOOKER DETECTED! Dispatching alerts... (lock_screen=%s)", lock_screen)

        # 1. Play sound asynchronously to avoid frame lag
        if play_sound:
            threading.Thread(target=self._play_alert_sound, daemon=True, name="AudioAlertThread").start()

        # 2. Dispatch toast notification asynchronously
        threading.Thread(
            target=self._send_toast,
            args=(title, message),
            daemon=True,
            name="ToastNotifyThread",
        ).start()

        # 3. Lock workstation if enabled by user
        if lock_screen:
            threading.Thread(target=self._lock_workstation, daemon=True, name="LockScreenThread").start()

    def _play_alert_sound(self) -> None:
        try:
            # Play standard Windows exclamation beep
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as e:
            logger.debug("Failed to play alert sound: %s", e)

    def _send_toast(self, title: str, message: str) -> None:
        """Send native notification using pystray, WinRT via PowerShell, or plyer."""
        sent = False

        # Attempt 1: If pystray icon is active, use native tray notification
        if self.tray_icon is not None and hasattr(self.tray_icon, "notify"):
            try:
                self.tray_icon.notify(message, title)
                sent = True
            except Exception as e:
                logger.debug("pystray.notify failed: %s", e)

        # Attempt 2: Native Windows 10/11 WinRT Toast via hidden PowerShell
        if not sent:
            try:
                # Escape single quotes
                safe_title = title.replace("'", "''")
                safe_msg = message.replace("'", "''")
                if ICON_PATH.exists():
                    safe_icon = str(ICON_PATH.resolve()).replace("\\", "/")
                    ps_script = (
                        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
                        "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastImageAndText02); "
                        "$textNodes = $template.GetElementsByTagName('text'); "
                        f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) | Out-Null; "
                        f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) | Out-Null; "
                        "$imageNodes = $template.GetElementsByTagName('image'); "
                        f"$imageNodes.Item(0).Attributes.GetNamedItem('src').NodeValue = '{safe_icon}'; "
                        "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Blind-Spotter').Show($toast);"
                    )
                else:
                    ps_script = (
                        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
                        "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                        "$textNodes = $template.GetElementsByTagName('text'); "
                        f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) | Out-Null; "
                        f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) | Out-Null; "
                        "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Blind-Spotter').Show($toast);"
                    )
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                sent = True
            except Exception as e:
                logger.debug("PowerShell WinRT toast failed: %s", e)

        # Attempt 3: Plyer fallback
        if not sent:
            try:
                from plyer import notification

                notification.notify(
                    title=title,
                    message=message,
                    app_name="Blind-Spotter",
                    app_icon=str(ICON_PATH) if ICON_PATH.exists() else None,
                    timeout=5,
                )
                sent = True
            except Exception as e:
                logger.warning("All toast methods failed: %s", e)

    def _lock_workstation(self) -> None:
        """Lock the Windows desktop using user32.dll LockWorkStation."""
        try:
            logger.info("Executing LockWorkStation API call...")
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            logger.error("Failed to lock workstation: %s", e)


# Global default notifier
default_notifier = Notifier()
