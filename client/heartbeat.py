"""
Heartbeat manager module — extracted from screen_recorder.py

Manages heartbeat communication with server.
"""

import logging
import threading
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class HeartbeatManager:
    """Manages heartbeat communication with server"""

    def __init__(self, config, license_key: str, machine_id: str):
        self.config = config
        self.license_key = license_key
        self.machine_id = machine_id
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start heartbeat loop in background thread"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("Heartbeat started (interval: %ds)", self.config.heartbeat_interval)

    def stop(self) -> None:
        """Stop heartbeat loop"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat stopped")

    def _heartbeat_loop(self) -> None:
        """Background heartbeat loop"""
        while not self._stop_event.is_set():
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error("Heartbeat error: %s", e)
            self._stop_event.wait(self.config.heartbeat_interval)

    def _send_heartbeat(self) -> None:
        """Send heartbeat to server"""
        try:
            response = requests.post(
                f"{self.config.server_url}/api/v1/heartbeat",
                data={
                    "machine_id": self.machine_id,
                    "license": self.license_key,
                },
                timeout=10,
            )
            if response.status_code == 200:
                logger.debug("Heartbeat sent successfully")
            else:
                logger.warning("Heartbeat failed: HTTP %d", response.status_code)
        except requests.RequestException as e:
            logger.warning("Heartbeat request failed: %s", e)
