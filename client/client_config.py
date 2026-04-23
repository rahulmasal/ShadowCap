"""
Configuration, state, and data types for the Screen Recorder Client.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from logging_setup import LOG_DIR

logger = logging.getLogger(__name__)


class ClientState(Enum):
    INITIALIZING = "initializing"
    LICENSE_INVALID = "license_invalid"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class UploadTask:
    video_path: Path
    timestamp: datetime
    processed_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    retry_count: int = 0
    max_retries: int = 5
    last_error: Optional[str] = None

    def increment_retry(self) -> bool:
        self.retry_count += 1
        return self.retry_count < self.max_retries


@dataclass
class Config:
    server_url: str = "http://localhost:5000"
    upload_interval: int = 300
    recording_fps: int = 10
    video_quality: int = 80
    chunk_duration: int = 60
    license_file: str = "license.key"
    hidden_mode: bool = True
    heartbeat_interval: int = 60
    max_offline_storage_mb: int = 1000
    retry_base_delay: float = 1.0
    retry_max_delay: float = 300.0
    upload_speed_limit_kbps: int = 0
    min_disk_space_mb: int = 500

    monitor_selection: int = 1
    region_x: int = 0
    region_y: int = 0
    region_width: int = 0
    region_height: int = 0

    enable_audio: bool = False
    audio_sample_rate: int = 44100
    audio_channels: int = 2

    enable_compression: bool = True
    compression_quality: int = 23
    generate_thumbnails: bool = True
    thumbnail_pct: float = 0.1
    ffmpeg_path: str = "ffmpeg"

    use_websocket: bool = False
    websocket_url: str = "http://localhost:5000"

    def __post_init__(self):
        self._load_from_file()

    def _load_from_file(self) -> None:
        config_file = LOG_DIR / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self, key):
                            setattr(self, key, value)
                logger.info("Configuration loaded from file")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config: {e}")

    def save_to_file(self) -> None:
        config_file = LOG_DIR / "config.json"
        try:
            with open(config_file, "w") as f:
                json.dump(self.__dict__, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save config: {e}")
