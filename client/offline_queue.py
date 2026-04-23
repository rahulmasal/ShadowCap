"""
Offline video queue for when server is unavailable.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from client_config import UploadTask
from logging_setup import LOG_DIR

logger = logging.getLogger(__name__)


class OfflineQueue:
    """Manages offline video queue for when server is unavailable"""

    def __init__(self, queue_dir: Path, max_storage_mb: int = 1000):
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.max_storage_bytes = max_storage_mb * 1024 * 1024
        self.queue: List[UploadTask] = []
        self._lock = threading.Lock()
        self._load_queue()

    def _load_queue(self) -> None:
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
        with self._lock:
            current_size = self.get_total_size()
            video_size = video_path.stat().st_size if video_path.exists() else 0
            logger.info(
                f"[OfflineQueue] Attempting to add {video_path.name} "
                f"(size: {video_size} bytes, current queue size: {current_size} bytes)"
            )

            if current_size + video_size > self.max_storage_bytes:
                logger.warning(
                    f"[OfflineQueue] Offline storage limit reached "
                    f"({current_size} + {video_size} > {self.max_storage_bytes}), removing oldest videos"
                )
                self._remove_oldest_until_fits(video_size)

            task = UploadTask(video_path=video_path, timestamp=datetime.now(timezone.utc))
            self.queue.append(task)
            self._save_queue()
            logger.info(
                f"[OfflineQueue] Added video to offline queue: {video_path.name} "
                f"(queue now has {len(self.queue)} items)"
            )
            return True

    def remove(self, task: UploadTask) -> None:
        with self._lock:
            if task in self.queue:
                self.queue.remove(task)
                self._save_queue()

    def get_next(self) -> Optional[UploadTask]:
        with self._lock:
            if self.queue:
                return self.queue[0]
            return None

    def get_total_size(self) -> int:
        return sum(task.video_path.stat().st_size for task in self.queue if task.video_path.exists())

    def _remove_oldest_until_fits(self, needed_space: int) -> None:
        while self.queue and self.get_total_size() + needed_space > self.max_storage_bytes:
            oldest = self.queue.pop(0)
            if oldest.video_path.exists():
                oldest.video_path.unlink()
                logger.info(f"Removed oldest video from queue: {oldest.video_path.name}")
            self._save_queue()

    def is_empty(self) -> bool:
        with self._lock:
            return len(self.queue) == 0

    def count(self) -> int:
        with self._lock:
            return len(self.queue)
