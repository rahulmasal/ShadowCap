"""
Retry handler module — extracted from screen_recorder.py

Handles retry logic with exponential backoff and jitter.
"""

import logging
import random
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetryHandler:
    """Handles retry logic with exponential backoff"""

    max_retries: int = 5
    base_delay: float = 2.0
    max_delay: float = 300.0
    jitter: bool = True

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for the given retry count with exponential backoff"""
        delay = min(self.base_delay * (2**retry_count), self.max_delay)
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    def should_retry(self, retry_count: int, error: Exception) -> bool:
        """Determine if the operation should be retried"""
        if retry_count >= self.max_retries:
            logger.warning(
                "Max retries (%d) exceeded for error: %s", self.max_retries, error
            )
            return False

        # Don't retry on authentication/authorization errors
        if hasattr(error, "status_code") and error.status_code in (401, 403):
            return False

        return True
