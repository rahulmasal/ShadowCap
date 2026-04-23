"""
Logging setup for the Screen Recorder Client.
Initializes early crash logging, log directory detection, and structured logging.
All client modules should import LOG_DIR and logger from here.
"""

import os
import sys
import logging
import tempfile
from pathlib import Path


def _get_log_dir():
    installed_log_dir = Path("C:\\ScreenRecorderClient\\ScreenRecSvc")
    if installed_log_dir.exists():
        return installed_log_dir

    script_dir = Path(__file__).parent.resolve()
    script_log_dir = script_dir / "ScreenRecSvc"
    try:
        script_log_dir.mkdir(parents=True, exist_ok=True)
        return script_log_dir
    except (OSError, PermissionError):
        pass

    temp_log_dir = Path(tempfile.gettempdir()) / "ScreenRecSvc"
    try:
        temp_log_dir.mkdir(parents=True, exist_ok=True)
        return temp_log_dir
    except (OSError, PermissionError):
        return Path.cwd() / "ScreenRecSvc"


LOG_DIR = _get_log_dir()
_LOG_FILE = LOG_DIR / "client.log"
_CRASH_FILE = LOG_DIR / "crash.log"


def _write_early_crash(exc_type, exc_value, exc_tb):
    import traceback

    try:
        with open(_CRASH_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"UNCAUGHT EXCEPTION at {__import__('datetime').datetime.now()}\n")
            f.write(f"Process: {sys.executable}\n")
            f.write(f"Script: {__file__}\n")
            f.write(f"CWD: {os.getcwd()}\n")
            f.write(f"Log Dir: {LOG_DIR}\n")
            f.write(f"{'='*60}\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            f.flush()
    except Exception:
        pass


sys.excepthook = _write_early_crash

# Structured logging setup
_log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)
_root_logger.addHandler(_stdout_handler)

try:
    _file_handler = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
    _file_handler.setFormatter(_log_formatter)
    _root_logger.addHandler(_file_handler)
except OSError as _fh_err:
    sys.stdout.write(f"WARNING: Could not open log file {_LOG_FILE}: {_fh_err}\n")
    sys.stdout.flush()

logger = logging.getLogger("screen_recorder")
logger.info("=" * 60)
logger.info("screen_recorder starting up...")
logger.info(f"Log file: {_LOG_FILE}")
logger.info(f"Crash log: {_CRASH_FILE}")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Log directory: {LOG_DIR}")
logger.info("=" * 60)
