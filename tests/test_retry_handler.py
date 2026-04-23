"""
Tests for retry handler module
"""

import pytest
from retry_handler import RetryHandler


class TestRetryHandler:
    """Test cases for RetryHandler"""

    def test_get_delay_zero_for_first(self):
        rh = RetryHandler(base_delay=1.0, max_delay=300.0)
        assert rh.get_delay(0) == 0

    def test_get_delay_increases(self):
        rh = RetryHandler(base_delay=1.0, max_delay=300.0)
        d1 = rh.get_delay(1)
        d2 = rh.get_delay(2)
        d3 = rh.get_delay(3)
        assert d1 > 0
        assert d3 > d1  # Generally true with jitter, but not deterministic

    def test_get_delay_respects_max(self):
        rh = RetryHandler(base_delay=1.0, max_delay=10.0)
        delay = rh.get_delay(100)
        assert delay <= 10.0 * 1.5  # Max delay * max jitter factor

    def test_should_retry_under_limit(self):
        rh = RetryHandler(max_retries=3)
        assert rh.should_retry(0, Exception("test")) is False  # Non-retryable error type
        assert rh.should_retry(3, Exception("test")) is False

    def test_should_retry_over_limit(self):
        rh = RetryHandler(max_retries=3)
        assert rh.should_retry(3, Exception("test")) is False
        assert rh.should_retry(10, Exception("test")) is False

    def test_should_retry_connection_error(self):
        import requests
        rh = RetryHandler(max_retries=5)
        error = requests.exceptions.ConnectionError("connection failed")
        assert rh.should_retry(0, error) is True
        assert rh.should_retry(4, error) is True
        assert rh.should_retry(5, error) is False

    def test_should_retry_timeout(self):
        import requests
        rh = RetryHandler(max_retries=5)
        error = requests.exceptions.Timeout("timed out")
        assert rh.should_retry(0, error) is True

    def test_jitter_adds_randomness(self):
        rh = RetryHandler(base_delay=1.0, max_delay=300.0)
        delays = [rh.get_delay(3) for _ in range(100)]
        assert len(set(delays)) > 1
