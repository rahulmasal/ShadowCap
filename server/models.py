"""
Database models for the Screen Recorder Server
"""

from datetime import datetime, timezone
from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Text, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

db = SQLAlchemy()


class Client(db.Model):
    """Client model for registered machines"""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    system_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    videos: Mapped[list["Video"]] = db.relationship(
        "Video", back_populates="client", cascade="all, delete-orphan"
    )
    license: Mapped[Optional["License"]] = db.relationship(
        "License", back_populates="client", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Client {self.machine_id[:12]}...>"


class License(db.Model):
    """License model for client licenses"""

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    license_key: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship
    client_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("clients.id"))
    client: Mapped[Optional["Client"]] = db.relationship(
        "Client", back_populates="license"
    )

    @property
    def is_expired(self) -> bool:
        """Check if license is expired"""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def days_remaining(self) -> int:
        """Get days remaining until expiration"""
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def __repr__(self) -> str:
        return f"<License {self.machine_id[:12]}... expires={self.expires_at}>"


class Video(db.Model):
    """Video model for uploaded recordings"""

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    client_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    mime_type: Mapped[str] = mapped_column(String(100), default="video/mp4")

    # Metadata
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    client_id: Mapped[int] = mapped_column(db.ForeignKey("clients.id"), nullable=False)
    client: Mapped["Client"] = db.relationship("Client", back_populates="videos")

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)

    @property
    def file_size_gb(self) -> float:
        """Get file size in GB"""
        return round(self.file_size / (1024 * 1024 * 1024), 4)

    def __repr__(self) -> str:
        return f"<Video {self.filename}>"


class AuditLog(db.Model):
    """Audit log for tracking actions"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} at {self.timestamp}>"


class ApiKey(db.Model):
    """API key for programmatic access"""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<ApiKey {self.name}>"


def init_db(app) -> None:
    """Initialize database with app"""
    db.init_app(app)
    # Schema management is handled by Flask-Migrate (flask db upgrade).
    # Do NOT call db.create_all() here — it conflicts with migration versioning.


def get_or_create_client(machine_id: str, system_info: Optional[dict] = None) -> Client:
    """Get existing client or create new one"""
    client = db.session.execute(
        db.select(Client).where(Client.machine_id == machine_id)
    ).scalar_one_or_none()

    if client is None:
        client = Client(machine_id=machine_id, system_info=system_info)
        db.session.add(client)
        db.session.commit()
    else:
        client.last_seen = datetime.now(timezone.utc)
        if system_info:
            client.system_info = system_info
        db.session.commit()

    return client
