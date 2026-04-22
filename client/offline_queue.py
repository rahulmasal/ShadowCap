"""
Offline queue module — extracted from screen_recorder.py

Manages offline video queue for when server is unavailable.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class UploadTask:
    """Represents a video upload task"""

    video_path: str
    added_at: float = 0.0
    retry_count: int = 0
    max_retries: int = 5

    def increment_retry(self) -> bool:
        """Increment retry count and return True if retries remain"""
        self.retry_count += 1
        return self.retry_count <= self.max_retries


class OfflineQueue:
    """Manages offline video queue for when server is unavailable"""

    def __init__(self, queue_dir: Path, max_storage_mb: int = 1000):
        self.queue_dir = queue_dir
        self.max_storage_bytes = max_storage_mb * 1024 * 1024
        self._queue: List[UploadTask] = []
        self._lock = threading.Lock()
        self._load_queue()

    def _load_queue(self) -> None:
        """Load pending uploads from disk"""
        queue_file = self.queue_dir / "upload_queue.json"
        if queue_file.exists():
            try:
                with open(queue_file, "r") as f:
                    data = json.load(f)
                self._queue = [
                    UploadTask(
                        video_path=item["video_path"],
                        added_at=item.get("added_at", 0),
                        retry_count=item.get("retry_count", 0),
                    )
                    for item in data
                    if Path(item["video_path"]).exists()
                ]
                logger.info("Loaded %d pending uploads from queue", len(self._queue))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load upload queue: %s", e)
                self._queue = []

    def _save_queue(self) -> None:
        """Save pending uploads to disk"""
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        queue_file = self.queue_dir / "upload_queue.json"
        try:
            data = [
                {
                    "video_path": task.video_path,
                    "added_at": task.added_at,
                    "retry_count": task.retry_count,
                }
                for task in self._queue
            ]
            with open(queue_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error("Failed to save upload queue: %s", e)

    def add(self, video_path: Path) -> bool:
        """Add a video to the offline queue"""
        with self._lock:
            if not video_path.exists():
                logger.error("Video file does not exist: %s", video_path)
                return False

            import time

            task = UploadTask(
                video_path=str(video_path),
                added_at=time.time(),
            )
            self._queue.append(task)

            # Check storage limit
            total = self.get_total_size()
            if total > self.max_storage_bytes:
                self._remove_oldest_until_fits(total)

            self._save_queue()
            logger.info(
                "Added %s to offline queue (queue size: %d)",
                video_path.name,
                len(self._queue),
            )
            return True

    def remove(self, task: UploadTask) -> None:
        """Remove a task from the queue"""
        with self._lock:
            self._queue.remove(task)
            self._save_queue()

    def get_next(self) -> Optional[UploadTask]:
        """Get the next task to process"""
        with self._lock:
            return self._queue[0] if self._queue else None

    def get_total_size(self) -> int:
        """Get total size of all queued videos"""
        total = 0
        for task in self._queue:
            path = Path(task.video_path)
            if path.exists():
                total += path.stat().st_size
        return total

    def _remove_oldest_until_fits(self, needed_space: int) -> None:
        """Remove oldest entries until storage fits within limit"""
        while self._queue and needed_space > self.max_storage_bytes:
            oldest = self._queue.pop(0)
            path = Path(oldest.video_path)
            if path.exists():
                needed_space -= path.stat().st_size
                path.unlink()
                logger.warning("Removed old queued video to free space: %s", path.name)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self._queue) == 0

    def count(self) -> int:
        """Get number of items in queue"""
        return len(self._queue)
