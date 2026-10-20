"""Configuration manager for Blind-Spotter.
Handles loading, saving, and defaults for user settings.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("blind_spotter.config")

# Project root is parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"


@dataclass
class AppConfig:
    cooldown_seconds: int = 10
    lock_screen_on_alert: bool = False
    confidence_threshold: float = 0.5
    camera_index: int = 0
    sample_interval: float = 0.7
    consecutive_frames_required: int = 2
    play_sound: bool = True

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
            filtered["sample_interval"] = max(0.2, min(5.0, float(filtered["sample_interval"])))
        if "consecutive_frames_required" in filtered:
            filtered["consecutive_frames_required"] = max(1, int(filtered["consecutive_frames_required"]))
        if "lock_screen_on_alert" in filtered:
            filtered["lock_screen_on_alert"] = bool(filtered["lock_screen_on_alert"])
        if "play_sound" in filtered:
            filtered["play_sound"] = bool(filtered["play_sound"])
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Thread-safe configuration loader and saver."""

    def __init__(self, filepath: Path = CONFIG_FILE) -> None:
        self.filepath = filepath
        self._config: AppConfig = self.load()

    @property
    def config(self) -> AppConfig:
        return self._config

    def load(self) -> AppConfig:
        if not self.filepath.exists():
            default_cfg = AppConfig()
            self.save(default_cfg)
            return default_cfg

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._config = AppConfig.from_dict(data)
            return self._config
        except Exception as e:
            logger.warning("Failed to parse config file (%s), using defaults.", e)
            self._config = AppConfig()
            return self._config

    def save(self, new_config: AppConfig | None = None) -> None:
        if new_config is not None:
            self._config = new_config

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2)
            logger.info("Configuration saved successfully to %s", self.filepath)
        except Exception as e:
            logger.error("Failed to save configuration to %s: %s", self.filepath, e)

    def update(self, **kwargs: Any) -> AppConfig:
        current_dict = self._config.to_dict()
        current_dict.update(kwargs)
        self._config = AppConfig.from_dict(current_dict)
        self.save()
        return self._config
