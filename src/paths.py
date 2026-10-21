"""Path, resource resolution, and single-instance mutex utilities for Blind-Spotter.
Ensures zero-friction enterprise execution, standalone PyInstaller bundling,
and user-space data isolation on Windows.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("blind_spotter.paths")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUTEX_NAME = "BlindSpotter_SingleInstance_Mutex"
ERROR_ALREADY_EXISTS = 183


def get_resource_path(relative_path: str | Path) -> Path:
    """Resolve an internal asset/model path.
    Supports both PyInstaller frozen bundles (sys._MEIPASS) and source checkout.
    """
    rel = Path(relative_path)
    if hasattr(sys, "_MEIPASS"):
        # Running inside PyInstaller onefile/onedir bundle
        bundle_dir = Path(getattr(sys, "_MEIPASS"))
        return bundle_dir / rel
    return PROJECT_ROOT / rel


def get_appdata_dir() -> Path:
    """Return user roaming AppData directory for persistent configuration.
    Falls back to user home directory if APPDATA is unset.
    """
    appdata_env = os.environ.get("APPDATA")
    if appdata_env:
        base = Path(appdata_env)
    else:
        base = Path.home() / "AppData" / "Roaming"
    target = base / "Blind-Spotter"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Could not create AppData directory (%s): %s", target, e)
    return target


def get_local_appdata_dir() -> Path:
    """Return user local AppData directory for diagnostics and logs."""
    local_env = os.environ.get("LOCALAPPDATA")
    if local_env:
        base = Path(local_env)
    else:
        base = Path.home() / "AppData" / "Local"
    target = base / "Blind-Spotter"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Could not create LocalAppData directory (%s): %s", target, e)
    return target


def get_log_dir() -> Path:
    """Return directory for rotating log files."""
    log_dir = get_local_appdata_dir() / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Could not create Log directory (%s): %s", log_dir, e)
    return log_dir


def acquire_single_instance_mutex(mutex_name: str = MUTEX_NAME) -> Optional[Any]:
    """Acquire a Windows Named Mutex to ensure only one instance runs.
    Returns the mutex handle if successfully acquired (first instance),
    or None if another instance is already running.
    """
    if os.name != "nt":
        # Non-Windows platform fallback (return dummy object)
        return object()

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            logger.info("Another instance of Blind-Spotter is already running (mutex detected).")
            if handle:
                kernel32.CloseHandle(handle)
            return None
        return handle
    except Exception as e:
        logger.warning("Could not acquire Windows mutex (%s): %s", mutex_name, e)
        # Default to allowing process to run if mutex check fails
        return object()


def release_single_instance_mutex(handle: Any) -> None:
    """Release and close a Windows mutex handle."""
    if os.name == "nt" and handle is not None and isinstance(handle, int):
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
