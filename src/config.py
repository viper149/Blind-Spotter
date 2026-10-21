"""Configuration manager for Blind-Spotter.
Handles loading, saving, and defaults for user settings with enterprise
AppData profile separation and atomic file operations.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.paths import get_appdata_dir, PROJECT_ROOT

logger = logging.getLogger("blind_spotter.config")


def get_default_config_path() -> Path:
    """Determine the appropriate config path.
    Prefers user AppData for enterprise installations, but supports
    local portable config.json if present in the executable folder.
    """
    # Check for portable config in executable directory or project root
    if hasattr(sys, "_MEIPASS"):
        exe_dir = Path(sys.executable).resolve().parent
        portable_cfg = exe_dir / "config.json"
        if portable_cfg.exists():
            return portable_cfg
    else:
        local_cfg = PROJECT_ROOT / "config.json"
        if local_cfg.exists():
            return local_cfg

    return get_appdata_dir() / "config.json"


CONFIG_FILE = get_default_config_path()


@dataclass
class AppConfig:
    cooldown_seconds: int = 10
    lock_screen_on_alert: bool = False
    confidence_threshold: float = 0.5
    camera_index: int = 0
    sample_interval: float = 0.2
    consecutive_frames_required: int = 2
    play_sound: bool = True
    start_with_windows: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        # Type coercions
        if "cooldown_seconds" in filtered:
            filtered["cooldown_seconds"] = max(1, int(filtered["cooldown_seconds"]))
        if "confidence_threshold" in filtered:
            filtered["confidence_threshold"] = max(0.1, min(1.0, float(filtered["confidence_threshold"])))
        if "camera_index" in filtered:
            filtered["camera_index"] = max(0, int(filtered["camera_index"]))
        if "sample_interval" in filtered:
            filtered["sample_interval"] = max(0.1, min(5.0, float(filtered["sample_interval"])))
        if "consecutive_frames_required" in filtered:
            filtered["consecutive_frames_required"] = max(1, int(filtered["consecutive_frames_required"]))
        if "lock_screen_on_alert" in filtered:
            filtered["lock_screen_on_alert"] = bool(filtered["lock_screen_on_alert"])
        if "play_sound" in filtered:
            filtered["play_sound"] = bool(filtered["play_sound"])
        if "start_with_windows" in filtered:
            filtered["start_with_windows"] = bool(filtered["start_with_windows"])
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Thread-safe and atomic configuration loader and saver."""

    def __init__(self, filepath: Optional[Path] = None) -> None:
        self.filepath = filepath or get_default_config_path()
        self._last_mtime: float = 0.0
        self._config: AppConfig = self.load()

    @property
    def config(self) -> AppConfig:
        try:
            if self.filepath.exists():
                mtime = self.filepath.stat().st_mtime
                if mtime > self._last_mtime:
                    self.load()
        except Exception:
            pass
        return self._config

    def load(self) -> AppConfig:
        if not self.filepath.exists():
            default_cfg = AppConfig()
            self.save(default_cfg)
            return default_cfg

        try:
            if self.filepath.exists():
                self._last_mtime = self.filepath.stat().st_mtime
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._config = AppConfig.from_dict(data)
            return self._config
        except Exception as e:
            logger.warning("Failed to parse config file (%s), using defaults.", e)
            self._config = AppConfig()
            return self._config

    def save(self, new_config: Optional[AppConfig] = None) -> None:
        if new_config is not None:
            self._config = new_config

        try:
            # Ensure parent folder exists
            self.filepath.parent.mkdir(parents=True, exist_ok=True)

            # Atomic save: write to temp file then rename to avoid file corruption
            temp_file = self.filepath.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2)
            temp_file.replace(self.filepath)
            logger.info("Configuration saved successfully to %s", self.filepath)
        except Exception as e:
            logger.error("Failed to save configuration to %s: %s", self.filepath, e)

    def update(self, **kwargs: Any) -> AppConfig:
        current_dict = self._config.to_dict()
        current_dict.update(kwargs)
        self._config = AppConfig.from_dict(current_dict)
        self.save()
        return self._config
