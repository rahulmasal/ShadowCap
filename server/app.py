"""
Screen Recorder Server
Main Flask application with modular architecture
"""

import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, redirect, url_for, flash, session, request
from flask_cors import CORS
from flask_migrate import Migrate

# Add shared module to path
# Check multiple locations for the shared module
_shared_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"),  # server/shared
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "shared"
    ),  # ../shared (project root)
]
for _shared_path in _shared_paths:
    if os.path.isdir(_shared_path):
        sys.path.insert(0, _shared_path)
        break

# Import local modules
from config import settings
from models import db, init_db, Client, License, Video, AuditLog
from auth import (
    auth_manager,
    require_auth,
    require_csrf,
    rate_limit,
    create_session,
    destroy_session,
)
from routes.api import api_bp, legacy_bp

# Import license manager
from license_manager import LicenseManager

# Configure logging with structured logging support
try:
    from logging_config import setup_logging, ContextLogger

    setup_logging(
        level=settings.log_level,
        log_format="colored",  # Use 'structured' for JSON logging in production
        service_name="screen-recorder-server",
    )
    logger = logging.getLogger(__name__)
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(
        level=getattr(logging, settings.log_level), format=settings.log_format
    )
    logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = settings.secret_key
app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length
app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Enable CORS with restricted origins
CORS(app, origins=settings.cors_origins, supports_credentials=True)

# Initialize database
init_db(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(legacy_bp)

# Initialize WebSocket manager (optional)
try:
    from websocket_manager import ws_manager

    if ws_manager.init_app(app):
        logger.info("WebSocket manager initialized")
    else:
        logger.info("WebSocket manager not available (flask-socketio not installed)")
except ImportError:
    logger.info("WebSocket manager module not available")


# ============ Security Headers ============
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    # Content Security Policy — allows Bootstrap CDN resources
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://cdn.jsdelivr.net; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net"
    )
    return response


# ============ HTTPS Enforcement ============
if settings.enforce_https:
    from flask_talisman import Talisman

    talisman = Talisman(app, force_https=True)
    logger.info("HTTPS enforcement enabled")


# ============ Key Management ============


def init_keys():
    """Initialize RSA keys for license signing

    If KEY_PASSPHRASE is set in the environment, the private key is
    encrypted at rest using AES-256-CBC (BestAvailableEncryption).
    """
    private_key_path = settings.keys_folder / "private_key.pem"
    public_key_path = settings.keys_folder / "public_key.pem"
    passphrase = settings.key_passphrase

    if private_key_path.exists() and public_key_path.exists():
        with open(private_key_path, "r") as f:
            private_key = f.read()
        with open(public_key_path, "r") as f:
            public_key = f.read()
        logger.info("Loaded existing keys%s", " (encrypted)" if passphrase else "")
    else:
        private_key, public_key = LicenseManager.generate_key_pair(
            passphrase=passphrase
        )
        with open(private_key_path, "w") as f:
            f.write(private_key)
        with open(public_key_path, "w") as f:
            f.write(public_key)
        logger.info("Generated new keys%s", " (encrypted)" if passphrase else "")

    return private_key, public_key


PRIVATE_KEY, PUBLIC_KEY = init_keys()

# Initialize license manager — pass passphrase so it can decrypt the key
license_manager = LicenseManager(passphrase=settings.key_passphrase)
license_manager.load_private_key(PRIVATE_KEY, passphrase=settings.key_passphrase)

# Store in app config so routes can reuse the singleton
app.config["_license_manager"] = license_manager


# ============ Template Setup ============

# Ensure templates directory exists (templates are standalone .html files)
Path(__file__).parent.joinpath("templates").mkdir(parents=True, exist_ok=True)

# Add datetime filter for Jinja templates
app.jinja_env.filters["datetime"] = lambda x: (
    datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S") if x else "N/A"
)


# ============ Register Admin Blueprint ============

from routes.admin import admin_bp

app.register_blueprint(admin_bp)


# ============ Cleanup Background Task ============


def _run_cleanup():
    """Run periodic cleanup tasks (audit logs, old videos) based on config policies."""
    with app.app_context():
        now = datetime.now(timezone.utc)

        # Audit log retention
        if settings.audit_log_retention_days > 0:
            cutoff = now - timedelta(days=settings.audit_log_retention_days)
            deleted = db.session.execute(
                db.delete(AuditLog).where(AuditLog.timestamp < cutoff)
            )
            db.session.commit()
            if deleted.rowcount:
                logger.info(
                    "Cleaned up %d audit logs older than %d days",
                    deleted.rowcount,
                    settings.audit_log_retention_days,
                )

        # Video retention by age
        if settings.video_retention_days > 0:
            cutoff = now - timedelta(days=settings.video_retention_days)
            old_videos = (
                db.session.execute(db.select(Video).where(Video.upload_time < cutoff))
                .scalars()
                .all()
            )
            for v in old_videos:
                filepath = settings.upload_folder / v.file_path
                if filepath.exists():
                    filepath.unlink()
                db.session.delete(v)
            if old_videos:
                db.session.commit()
                logger.info(
                    "Cleaned up %d videos older than %d days",
                    len(old_videos),
                    settings.video_retention_days,
                )

        # Video retention by disk limit
        if settings.video_disk_limit_mb > 0:
            total_bytes = (
                db.session.execute(db.select(db.func.sum(Video.file_size))).scalar()
                or 0
            )
            limit_bytes = settings.video_disk_limit_mb * 1024 * 1024
            if total_bytes > limit_bytes:
                # Delete oldest videos until under limit
                excess = total_bytes - limit_bytes
                oldest = (
                    db.session.execute(
                        db.select(Video).order_by(Video.upload_time.asc())
                    )
                    .scalars()
                    .all()
                )
                freed = 0
                for v in oldest:
                    filepath = settings.upload_folder / v.file_path
                    if filepath.exists():
                        filepath.unlink()
                    freed += v.file_size
                    db.session.delete(v)
                    if freed >= excess:
                        break
                db.session.commit()
                logger.info(
                    "Freed %d MB to stay under disk limit", freed // (1024 * 1024)
                )


# Schedule cleanup every hour if running in main thread
import threading

_cleanup_stop = threading.Event()


def _cleanup_loop():
    """Background thread that runs cleanup tasks periodically."""
    while not _cleanup_stop.is_set():
        _cleanup_stop.wait(3600)  # Run every hour
        if not _cleanup_stop.is_set():
            try:
                _run_cleanup()
            except Exception as e:
                logger.error("Cleanup task failed: %s", e)


_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()


# ============ Main ============

if __name__ == "__main__":
    port = settings.port
    debug = settings.debug

    logger.info(f"Starting server on port {port}")
    app.run(host=settings.host, port=port, debug=debug)
