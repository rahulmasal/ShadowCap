"""
Tests for retry handler module
"""

import pytest
from retry_handler import RetryHandler


class TestRetryHandler:
    """Test cases for RetryHandler"""

    def test_get_delay_increases(self):
        rh = RetryHandler(base_delay=1.0, max_delay=300.0, jitter=False)
        d0 = rh.get_delay(0)
        d1 = rh.get_delay(1)
        d2 = rh.get_delay(2)
        assert d0 < d1 < d2

    def test_get_delay_respects_max(self):
        rh = RetryHandler(base_delay=1.0, max_delay=10.0, jitter=False)
        delay = rh.get_delay(100)  # Very high retry count
        assert delay <= 10.0

    def test_should_retry_under_limit(self):
        rh = RetryHandler(max_retries=3)
        assert rh.should_retry(0, Exception("test")) is True
        assert rh.should_retry(2, Exception("test")) is True

    def test_should_retry_over_limit(self):
        rh = RetryHandler(max_retries=3)
        assert rh.should_retry(3, Exception("test")) is False
        assert rh.should_retry(10, Exception("test")) is False

    def test_should_not_retry_auth_errors(self):
        rh = RetryHandler(max_retries=5)
        error = Exception("Unauthorized")
        error.status_code = 401
        assert rh.should_retry(0, error) is False

        error.status_code = 403
        assert rh.should_retry(0, error) is False

    def test_jitter_adds_randomness(self):
        rh = RetryHandler(base_delay=1.0, max_delay=300.0, jitter=True)
        delays = [rh.get_delay(1) for _ in range(100)]
        # With jitter, not all delays should be identical
        assert len(set(delays)) > 1

    def test_no_jitter_deterministic(self):
        rh = RetryHandler(base_delay=1.0, max_delay=300.0, jitter=False)
        d1 = rh.get_delay(1)
        d2 = rh.get_delay(1)
        assert d1 == d2
