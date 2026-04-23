"""
Heartbeat manager for server communication.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import requests

from client_config import Config

logger = logging.getLogger(__name__)


class HeartbeatManager:
    """Manages heartbeat communication with server"""

    def __init__(self, config: Config, license_key: str, machine_id: str):
        self.config = config
        self.license_key = license_key
        self.machine_id = machine_id
        self.last_heartbeat: Optional[datetime] = None
        self.server_reachable = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("Heartbeat manager started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat manager stopped")

    def _heartbeat_loop(self) -> None:
        logger.info("[HEARTBEAT] Heartbeat loop started")
        while not self._stop_event.is_set():
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error(f"[HEARTBEAT] Error in heartbeat loop: {e}", exc_info=True)

            logger.debug(f"[HEARTBEAT] Sleeping for {self.config.heartbeat_interval} seconds")
            self._stop_event.wait(self.config.heartbeat_interval)

    def _send_heartbeat(self) -> None:
        url = f"{self.config.server_url}/api/v1/heartbeat"
        logger.debug(f"[HEARTBEAT] Sending heartbeat to {url}")

        headers = {
            "X-License-Key": self.license_key,
            "X-Machine-ID": self.machine_id,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json={"timestamp": datetime.now(timezone.utc).isoformat()},
                timeout=10,
            )

            if response.status_code == 200:
                self.last_heartbeat = datetime.now(timezone.utc)
                self.server_reachable = True
                logger.debug("[HEARTBEAT] Heartbeat successful")
            else:
                self.server_reachable = False
                logger.warning(f"[HEARTBEAT] Heartbeat failed: HTTP {response.status_code} - {response.text[:100]}")

        except requests.exceptions.RequestException as e:
            self.server_reachable = False
            logger.warning(f"[HEARTBEAT] Heartbeat failed (server unreachable): {e}")
