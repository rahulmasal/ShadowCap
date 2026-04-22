"""
WebSocket Manager Module
Handles real-time communication with clients using Socket.IO
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)

# Try to import flask_socketio
try:
    from flask_socketio import SocketIO, emit, join_room, leave_room

    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    logger.warning("flask-socketio not available - WebSocket disabled")


@dataclass
class ClientConnection:
    """Represents a connected client"""

    sid: str
    machine_id: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sid": self.sid,
            "machine_id": self.machine_id,
            "connected_at": self.connected_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "metadata": self.metadata,
        }


class WebSocketManager:
    """Manages WebSocket connections and real-time updates"""

    def __init__(self):
        self.socketio: Optional[Any] = None
        self.clients: Dict[str, ClientConnection] = {}
        self.admin_sids: Set[str] = set()
        self._lock = threading.Lock()
        self._initialized = False

    def init_app(self, app) -> bool:
        """Initialize SocketIO with Flask app"""
        if not SOCKETIO_AVAILABLE:
            logger.warning("SocketIO not available, WebSocket features disabled")
            return False

        try:
            from config import settings

            self.socketio = SocketIO(
                app,
                cors_allowed_origins=settings.cors_origins,
                async_mode="threading",
                logger=False,
                engineio_logger=False,
            )
            self._register_handlers()
            self._initialized = True
            logger.info("WebSocket manager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket: {e}")
            return False

    def _register_handlers(self):
        """Register Socket.IO event handlers"""

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection"""
            from flask import request

            sid = request.sid
            logger.info(f"WebSocket client connected: {sid}")
            emit("connection_response", {"status": "connected", "sid": sid})

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection"""
            from flask import request

            sid = request.sid
            logger.info(f"WebSocket client disconnected: {sid}")

            with self._lock:
                # Remove from clients
                if sid in self.clients:
                    machine_id = self.clients[sid].machine_id
                    del self.clients[sid]
                    self._broadcast_client_status(machine_id, "disconnected")

                # Remove from admins
                self.admin_sids.discard(sid)

        @self.socketio.on("register_client")
        def handle_register_client(data):
            """Register a recording client"""
            from flask import request

            sid = request.sid
            machine_id = data.get("machine_id", "unknown")

            with self._lock:
                self.clients[sid] = ClientConnection(
                    sid=sid,
                    machine_id=machine_id,
                    metadata=data,
                )

            logger.info(f"Client registered: {machine_id} (sid: {sid})")
            join_room(f"client_{machine_id}")
            emit("registration_confirmed", {"machine_id": machine_id})
            self._broadcast_client_status(machine_id, "connected")

        @self.socketio.on("register_admin")
        def handle_register_admin():
            """Register an admin dashboard"""
            from flask import request

            sid = request.sid

            with self._lock:
                self.admin_sids.add(sid)

            join_room("admins")
            logger.info(f"Admin registered: {sid}")
            emit("registration_confirmed", {"role": "admin"})

            # Send current client list
            with self._lock:
                clients_data = [c.to_dict() for c in self.clients.values()]
            emit("client_list", {"clients": clients_data})

        @self.socketio.on("client_status")
        def handle_client_status(data):
            """Handle status update from client"""
            from flask import request

            sid = request.sid

            with self._lock:
                if sid in self.clients:
                    self.clients[sid].last_heartbeat = datetime.now(timezone.utc)
                    self.clients[sid].metadata.update(data)

            # Broadcast to admins
            machine_id = data.get("machine_id", "unknown")
            self._broadcast_client_status(machine_id, "active", data)

        @self.socketio.on("recording_started")
        def handle_recording_started(data):
            """Handle recording started event"""
            machine_id = data.get("machine_id", "unknown")
            logger.info(f"Recording started: {machine_id}")
            self._broadcast_client_status(machine_id, "recording", data)

        @self.socketio.on("recording_stopped")
        def handle_recording_stopped(data):
            """Handle recording stopped event"""
            machine_id = data.get("machine_id", "unknown")
            logger.info(f"Recording stopped: {machine_id}")
            self._broadcast_client_status(machine_id, "stopped", data)

        @self.socketio.on("video_uploaded")
        def handle_video_uploaded(data):
            """Handle video uploaded event"""
            machine_id = data.get("machine_id", "unknown")
            filename = data.get("filename", "unknown")
            logger.info(f"Video uploaded: {filename} from {machine_id}")
            self._broadcast_to_admins(
                "video_uploaded",
                {"machine_id": machine_id, "filename": filename, **data},
            )

        @self.socketio.on("error_report")
        def handle_error_report(data):
            """Handle error report from client"""
            machine_id = data.get("machine_id", "unknown")
            error = data.get("error", "Unknown error")
            logger.error(f"Client error from {machine_id}: {error}")
            self._broadcast_to_admins(
                "client_error",
                {"machine_id": machine_id, "error": error, **data},
            )

    def _broadcast_client_status(
        self, machine_id: str, status: str, data: Optional[Dict] = None
    ):
        """Broadcast client status to admins"""
        message = {
            "machine_id": machine_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(data or {}),
        }
        self._broadcast_to_admins("client_status", message)

    def _broadcast_to_admins(self, event: str, data: Dict[str, Any]):
        """Broadcast message to all admins"""
        if self.socketio and self._initialized:
            try:
                self.socketio.emit(event, data, room="admins")
            except Exception as e:
                logger.error(f"Failed to broadcast to admins: {e}")

    def broadcast_video_uploaded(
        self, machine_id: str, filename: str, file_size: int
    ) -> None:
        """Broadcast video upload notification"""
        self._broadcast_to_admins(
            "video_uploaded",
            {
                "machine_id": machine_id,
                "filename": filename,
                "file_size": file_size,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def broadcast_client_heartbeat(
        self, machine_id: str, metadata: Dict = None
    ) -> None:
        """Broadcast client heartbeat"""
        self._broadcast_to_admins(
            "client_heartbeat",
            {
                "machine_id": machine_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            },
        )

    def get_connected_clients(self) -> list:
        """Get list of connected clients"""
        with self._lock:
            return [c.to_dict() for c in self.clients.values()]

    def is_available(self) -> bool:
        """Check if WebSocket is available"""
        return SOCKETIO_AVAILABLE and self._initialized

    def get_status(self) -> Dict[str, Any]:
        """Get WebSocket manager status"""
        return {
            "available": SOCKETIO_AVAILABLE,
            "initialized": self._initialized,
            "connected_clients": len(self.clients),
            "connected_admins": len(self.admin_sids),
        }


# Global instance
ws_manager = WebSocketManager()
