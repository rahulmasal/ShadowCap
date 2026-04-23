"""
Retry handler with exponential backoff and throttled file reader.
"""

import time
import random
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ThrottledFileReader:
    """File-like wrapper that throttles read speed for bandwidth-limited uploads."""

    def __init__(self, file_obj, speed_limit_kbps: int = 0, chunk_size: int = 8192):
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

            elapsed = time.time() - self._start_time
            allowed_bytes = self._speed_limit_kbps * 1024 * elapsed
            if self._bytes_read > allowed_bytes:
                sleep_time = (self._bytes_read - allowed_bytes) / (self._speed_limit_kbps * 1024)
                time.sleep(min(sleep_time, 1.0))

        return data

    def __getattr__(self, name):
        return getattr(self._file, name)


class RetryHandler:
    """Handles retry logic with exponential backoff"""

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
        if retry_count <= 0:
            return 0
        delay = self.base_delay * (2 ** (retry_count - 1))
        jitter = random.uniform(0.5, 1.5)
        delay *= jitter
        return min(delay, self.max_delay)

    def should_retry(self, retry_count: int, error: Exception) -> bool:
        if retry_count >= self.max_retries:
            return False

        if isinstance(error, RetryHandler.RETRYABLE_ERRORS):
            return True

        if isinstance(error, requests.exceptions.HTTPError):
            if hasattr(error, "response") and error.response is not None:
                return 500 <= error.response.status_code < 600

        return False
