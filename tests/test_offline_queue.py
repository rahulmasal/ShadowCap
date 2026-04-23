"""
Tests for offline queue module
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from client_config import UploadTask
from offline_queue import OfflineQueue


class TestUploadTask:
    """Test cases for UploadTask dataclass"""

    def test_increment_retry(self):
        task = UploadTask(
            video_path=Path("/tmp/test.mp4"),
            timestamp=datetime.now(timezone.utc),
            max_retries=3,
        )
        assert task.retry_count == 0
        assert task.increment_retry() is True  # 1 < 3
        assert task.retry_count == 1
        task.increment_retry()  # 2
        assert task.increment_retry() is False  # 3 >= 3

    def test_default_values(self):
        task = UploadTask(
            video_path=Path("/tmp/test.mp4"),
            timestamp=datetime.now(timezone.utc),
        )
        assert task.retry_count == 0
        assert task.max_retries == 5
        assert task.last_error is None


class TestOfflineQueue:
    """Test cases for OfflineQueue"""

    def test_add_and_count(self, tmp_path):
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir()
        video_file = queue_dir / "test.mp4"
        video_file.write_text("fake video data")

        q = OfflineQueue(queue_dir, max_storage_mb=1000)
        assert q.is_empty()
        assert q.count() == 0

        result = q.add(video_file)
        assert result is True
        assert q.count() == 1
        assert not q.is_empty()

    def test_get_next(self, tmp_path):
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir()
        video_file = queue_dir / "test.mp4"
        video_file.write_text("fake video data")

        q = OfflineQueue(queue_dir)
        q.add(video_file)
        task = q.get_next()
        assert task is not None
        assert task.video_path == video_file

    def test_remove(self, tmp_path):
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir()
        video_file = queue_dir / "test.mp4"
        video_file.write_text("fake video data")

        q = OfflineQueue(queue_dir)
        q.add(video_file)
        task = q.get_next()
        q.remove(task)
        assert q.is_empty()

    def test_persistence(self, tmp_path):
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir()
        video_file = queue_dir / "test.mp4"
        video_file.write_text("fake video data")

        q1 = OfflineQueue(queue_dir)
        q1.add(video_file)
        assert q1.count() == 1

        q2 = OfflineQueue(queue_dir)
        assert q2.count() == 1

    def test_get_total_size(self, tmp_path):
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir()
        video_file = queue_dir / "test.mp4"
        video_file.write_bytes(b"x" * 1024)

        q = OfflineQueue(queue_dir)
        q.add(video_file)
        assert q.get_total_size() == 1024
