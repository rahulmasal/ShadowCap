"""
Client configuration module — extracted from screen_recorder.py

Manages all client-side settings with file persistence.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration manager for the client"""

    server_url: str = "http://localhost:5000"
    license_key: str = ""
    machine_id: str = ""
    video_dir: str = ""
    audio_enabled: bool = True
    audio_device_index: int = -1
    monitor_index: int = 0
    fps: int = 15
    codec: str = "XVID"
    quality: str = "medium"
    upload_on_stop: bool = True
    max_retries: int = 5
    retry_base_delay: float = 2.0
    retry_max_delay: float = 300.0
    heartbeat_interval: int = 60
    max_storage_mb: int = 1000
    upload_speed_limit_kbps: int = 0  # 0 = unlimited
    min_disk_space_mb: int = 100  # Minimum free disk space to start recording

    # Internal fields (not serialized)
    _config_file: str = field(default="", repr=False, compare=False)

    def __post_init__(self):
        if not self.video_dir:
            self.video_dir = str(Path.home() / "Videos" / "ScreenRecorder")
        if not self._config_file:
            self._config_file = str(Path(self.video_dir) / "config.json")

    def _load_from_file(self) -> None:
        """Load configuration from file"""
        config_file = Path(self._config_file)
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                # Only update known fields
                for key, value in data.items():
                    if hasattr(self, key) and not key.startswith("_"):
                        setattr(self, key, value)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load config: %s", e)

    def save_to_file(self) -> None:
        """Save configuration to file — only serializes declared dataclass fields"""
        config_file = Path(self._config_file)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Use asdict() to only serialize declared fields (no internal state leakage)
            data = asdict(self)
            # Remove internal fields
            data.pop("_config_file", None)
            with open(config_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error("Failed to save config: %s", e)

    @classmethod
    def from_file(cls, config_file: str) -> "Config":
        """Create a Config instance from a file"""
        config = cls(_config_file=config_file)
        config._load_from_file()
        return config
