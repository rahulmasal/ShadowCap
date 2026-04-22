"""
Logging Configuration Module
Provides structured logging with JSON formatters and contextual information
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def __init__(self, service_name: str = "screen-recorder"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add optional fields
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "machine_id"):
            log_data["machine_id"] = record.machine_id

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development"""

    # ANSI color codes
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors"""
        color = self.COLORS.get(record.levelno, "")
        levelname = f"{color}{record.levelname}{self.RESET}"
        timestamp = f"\033[90m{datetime.fromtimestamp(record.created).strftime('%H:%M:%S')}{self.RESET}"
        name = f"\033[36m{record.name}\033[0m"
        message = (
            f"{color}{record.getMessage()}{self.RESET}"
            if color
            else record.getMessage()
        )

        return f"{timestamp} | {levelname:8} | {name:25} | {message}"


def setup_logging(
    level: str = "INFO",
    log_format: str = "colored",
    service_name: str = "screen-recorder",
    log_file: Optional[str] = None,
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('colored', 'structured', 'simple')
        service_name: Name of the service for structured logging
        log_file: Optional file path for file logging
    """
    # Get log level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Set formatter based on format type
    if log_format == "structured":
        formatter = StructuredFormatter(service_name)
    elif log_format == "simple":
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:  # colored (default)
        formatter = ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified (with rotation to prevent unbounded growth)
    if log_file:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(log_level)
        file_formatter = StructuredFormatter(service_name)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Log configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={level}, format={log_format}")


class ContextLogger:
    """
    Logger wrapper that adds contextual information to log messages.

    Usage:
        logger = ContextLogger("my_module", machine_id="abc123")
        logger.info("Processing request", extra={"request_id": "xyz"})
    """

    def __init__(self, name: str, **context):
        self.logger = logging.getLogger(name)
        self.context = context

    def _log_with_context(self, level: int, msg: str, **kwargs):
        """Log message with context"""
        extra = kwargs.pop("extra", {})
        extra.update(self.context)
        extra.update(kwargs.pop("extra_fields", {}))
        kwargs["extra"] = extra

        self.logger.log(level, msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        self._log_with_context(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log_with_context(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log_with_context(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log_with_context(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log_with_context(logging.CRITICAL, msg, **kwargs)


# NOTE: Do not call setup_logging() here at module level.
# It should only be called explicitly from app.py with custom settings.
