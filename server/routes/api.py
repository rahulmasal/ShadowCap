"""
API Routes for Screen Recorder Server
Version 1 API endpoints with proper validation and error handling
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Optional

from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename

# Import from parent directory
import sys
import os

_server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _server_dir)

# Check for shared module in multiple locations (same pattern as app.py)
_shared_same_level = os.path.join(_server_dir, "shared")
_shared_parent_level = os.path.join(_server_dir, "..", "shared")
if os.path.isdir(_shared_same_level):
    sys.path.insert(0, _shared_same_level)
else:
    sys.path.insert(0, _shared_parent_level)

from config import settings
from models import db, Client, License, Video, AuditLog
from auth import auth_manager, require_auth, rate_limit, get_client_ip
from validators import InputValidator, validate_request_data

logger = logging.getLogger(__name__)

# Create blueprint with URL prefix for API versioning
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ============ Error Handlers ============


@api_bp.errorhandler(400)
def bad_request(error):
    """Handle bad request errors"""
    return jsonify({"error": "Bad request", "details": str(error)}), 400


@api_bp.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized errors"""
    return jsonify({"error": "Unauthorized", "details": str(error)}), 401


@api_bp.errorhandler(403)
def forbidden(error):
    """Handle forbidden errors"""
    return jsonify({"error": "Forbidden", "details": str(error)}), 403


@api_bp.errorhandler(404)
def not_found(error):
    """Handle not found errors"""
    return jsonify({"error": "Not found", "details": str(error)}), 404


@api_bp.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit errors"""
    return (
        jsonify({"error": "Rate limit exceeded", "details": "Please try again later"}),
        429,
    )


@api_bp.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {error}")
    return (
        jsonify(
            {
                "error": "Internal server error",
                "details": "An unexpected error occurred",
            }
        ),
        500,
    )


# ============ Helper Functions ============


def log_audit(
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    """Log an audit entry"""
    try:
        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:255],
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")


# ============ License Validation Decorator ============


def validate_license_in_request(fn):
    """Decorator to validate license in request"""
    from functools import wraps

    @wraps(fn)
    def decorated_function(*args, **kwargs):
        # Get license from header (preferred) or form data
        license_token = request.headers.get("X-License-Token")
        license_key = request.form.get("license") or request.headers.get(
            "X-License-Key"
        )
        machine_id = request.form.get("machine_id") or request.headers.get(
            "X-Machine-ID"
        )

        if not license_key and not license_token:
            return jsonify({"error": "License key required"}), 401

        # Reuse the app-level license_manager singleton from app.py
        from flask import current_app

        lm = current_app.config.get("_license_manager")
        if lm is None:
            # Fallback: use the module-level instance from app.py
            try:
                from app import license_manager as app_lm

                lm = app_lm
                current_app.config["_license_manager"] = lm
            except ImportError:
                pass

        if lm is None:
            # Last resort: instantiate and cache
            from license_manager import LicenseManager

            lm = LicenseManager()
            public_key_path = settings.keys_folder / "public_key.pem"
            if public_key_path.exists():
                with open(public_key_path, "r") as key_file:
                    lm.load_public_key(key_file.read())
            else:
                return jsonify({"error": "Server configuration error"}), 500
            current_app.config["_license_manager"] = lm

        is_valid, result = lm.validate_license(license_key or license_token, machine_id)

        if not is_valid:
            return jsonify({"error": f"Invalid license: {result}"}), 401

        # Store license data in request context
        g.license_data = result
        g.machine_id = machine_id

        return fn(*args, **kwargs)

    return decorated_function


# ============ Upload Routes ============


@api_bp.route("/upload", methods=["POST"])
@rate_limit(limit=30, window=60)
@validate_license_in_request
def upload_video():
    """Handle video upload from client"""
    try:
        # Validate file
        if "video" not in request.files:
            return jsonify({"error": "No video file provided"}), 400

        file = request.files["video"]

        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Validate file extension
        is_valid, error = InputValidator.validate_file_extension(
            file.filename, settings.allowed_extensions
        )
        if not is_valid:
            return jsonify({"error": error}), 400

        # Validate filename
        is_valid, error = InputValidator.validate_filename(file.filename)
        if not is_valid:
            return jsonify({"error": error}), 400

        machine_id = g.machine_id
        timestamp = request.form.get(
            "timestamp", datetime.now(timezone.utc).isoformat()
        )

        # Get or create client
        client = db.session.execute(
            db.select(Client).where(Client.machine_id == machine_id)
        ).scalar_one_or_none()

        if client is None:
            client = Client(machine_id=machine_id)
            db.session.add(client)
            db.session.flush()

        # Update last seen
        client.last_seen = datetime.now(timezone.utc)

        # Create client-specific folder
        client_folder = settings.upload_folder / machine_id
        client_folder.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        filename = secure_filename(file.filename)
        date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{date_prefix}_{filename}"
        filepath = client_folder / unique_filename

        # Save file
        file.save(filepath)
        file_size = filepath.stat().st_size

        # Create video record
        video = Video(
            filename=unique_filename,
            original_filename=filename,
            file_path=str(filepath),
            file_size=file_size,
            client_id=client.id,
            client_timestamp=datetime.fromisoformat(timestamp) if timestamp else None,
        )
        db.session.add(video)
        db.session.commit()

        # Log audit
        log_audit(
            action="video_upload",
            entity_type="video",
            entity_id=video.id,
            details={"filename": unique_filename, "size": file_size},
        )

        logger.info(f"Video uploaded: {unique_filename} from {machine_id}")

        return jsonify(
            {
                "success": True,
                "message": "Video uploaded successfully",
                "filename": unique_filename,
                "video_id": video.id,
            }
        )

    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": "Internal server error",
                    "details": "An unexpected error occurred",
                }
            ),
            500,
        )


# ============ License Routes ============


@api_bp.route("/validate-license", methods=["POST"])
@rate_limit(limit=10, window=60)
def validate_license():
    """Validate a license key"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"valid": False, "error": "No data provided"}), 400

        license_key = data.get("license")
        machine_id = data.get("machine_id")

        # Validate inputs
        is_valid, error = InputValidator.validate_license_key(license_key)
        if not is_valid:
            return jsonify({"valid": False, "error": error}), 400

        if machine_id:
            is_valid, error = InputValidator.validate_machine_id(machine_id)
            if not is_valid:
                return jsonify({"valid": False, "error": error}), 400

        # Validate license
        from license_manager import LicenseManager

        lm = LicenseManager()

        public_key_path = settings.keys_folder / "public_key.pem"
        if public_key_path.exists():
            with open(public_key_path, "r") as f:
                lm.load_public_key(f.read())
        else:
            return jsonify({"valid": False, "error": "Server configuration error"}), 500

        is_valid, result = lm.validate_license(license_key, machine_id)

        return jsonify(
            {
                "valid": is_valid,
                "data": result if is_valid else None,
                "error": None if is_valid else result,
            }
        )

    except Exception as e:
        logger.error(f"License validation error: {e}", exc_info=True)
        return jsonify({"valid": False, "error": "Internal server error"}), 500


# ============ Client Routes ============


@api_bp.route("/heartbeat", methods=["POST"])
@rate_limit(limit=60, window=60)
@validate_license_in_request
def heartbeat():
    """Receive heartbeat from client"""
    try:
        machine_id = g.machine_id

        # machine_id is required — reject early with a clear error instead of
        # letting a None value propagate into the database and cause a 500.
        if not machine_id:
            logger.warning("[HEARTBEAT] Received heartbeat with no machine_id")
            return jsonify({"error": "machine_id is required"}), 400

        # Get or create client
        client = db.session.execute(
            db.select(Client).where(Client.machine_id == machine_id)
        ).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if client is None:
            client = Client(machine_id=machine_id)
            client.last_seen = now
            client.is_active = True
            db.session.add(client)
            db.session.flush()  # Flush to get client.id before commit
        else:
            client.last_seen = now
            client.is_active = True

        db.session.commit()

        # Log heartbeat so it appears on the connection logs page.
        # Use a separate try/except so an audit-log failure never causes a
        # heartbeat 500 — the heartbeat itself was already committed above.
        try:
            log_audit(
                action="heartbeat",
                entity_type="client",
                entity_id=client.id,
                details={"machine_id": machine_id},
            )
        except Exception as audit_err:
            logger.warning(f"[HEARTBEAT] Audit log failed (non-fatal): {audit_err}")

        return jsonify(
            {
                "success": True,
                "message": "Heartbeat received",
                "server_time": datetime.now(timezone.utc).isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Heartbeat error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@api_bp.route("/get-machine-id", methods=["GET"])
def get_machine_id():
    """Get machine ID for the requesting client"""
    try:
        from license_manager import MachineIdentifier

        machine_id = MachineIdentifier.get_machine_id()
        return jsonify({"machine_id": machine_id})
    except Exception as e:
        logger.error(f"Get machine ID error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route("/get-public-key", methods=["GET"])
def get_public_key():
    """Get the public key for client embedding"""
    try:
        public_key_path = settings.keys_folder / "public_key.pem"
        if public_key_path.exists():
            with open(public_key_path, "r") as f:
                return jsonify({"public_key": f.read()})
        return jsonify({"error": "Public key not found"}), 404
    except Exception as e:
        logger.error(f"Get public key error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============ Health Check ============


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring with detailed system status"""
    try:
        from health_monitor import HealthMonitor, HealthStatus

        # Initialize monitor with correct paths - use instance folder for data
        instance_folder = (
            settings.upload_folder.parent
            if settings.upload_folder.parent
            and settings.upload_folder.parent.name == "instance"
            else settings.upload_folder.parent
        )
        monitor = HealthMonitor(
            upload_folder=str(settings.upload_folder),
            data_folder=str(instance_folder or "."),
        )

        # Run health checks with database session
        health_status = monitor.check_all(db.session)

        return jsonify(health_status)
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "overall": "error",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0.0",
                    "error": str(e),
                }
            ),
            500,
        )


# ============ Video Streaming Routes ============


@api_bp.route("/video/<machine_id>/<path:filename>")
@require_auth
def stream_video(machine_id: str, filename: str):
    """Stream video file with range support for partial content"""
    from flask import Response, make_response

    try:
        # Validate inputs
        is_valid, error = InputValidator.validate_filename(filename)
        if not is_valid:
            return jsonify({"error": error}), 400

        is_valid, error = InputValidator.validate_machine_id(machine_id)
        if not is_valid:
            return jsonify({"error": error}), 400

        # Get video file path
        video_path = settings.upload_folder / machine_id / filename

        if not video_path.exists():
            return jsonify({"error": "Video not found"}), 404

        # Get file size
        file_size = video_path.stat().st_size

        # Parse range header for partial content
        range_header = request.headers.get("Range", None)

        if range_header:
            # Parse range (e.g., "bytes=0-1023")
            try:
                range_match = range_header.replace("bytes=", "").split("-")
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if range_match[1] else file_size - 1

                # Clamp values
                start = max(0, start)
                end = min(file_size - 1, end)

                length = end - start + 1

                def generate():
                    with open(video_path, "rb") as f:
                        f.seek(start)
                        remaining = length
                        chunk_size = 64 * 1024  # 64KB chunks
                        while remaining > 0:
                            read_size = min(chunk_size, remaining)
                            data = f.read(read_size)
                            if not data:
                                break
                            remaining -= len(data)
                            yield data

                response = Response(
                    generate(),
                    206,
                    mimetype="video/mp4",
                    direct_passthrough=True,
                )
                response.headers.add(
                    "Content-Range", f"bytes {start}-{end}/{file_size}"
                )
                response.headers.add("Accept-Ranges", "bytes")
                response.headers.add("Content-Length", str(length))
                return response

            except (ValueError, IndexError):
                # Invalid range header, return full file
                pass

        # No range header or invalid range, return full file
        def generate_full():
            with open(video_path, "rb") as f:
                chunk_size = 64 * 1024  # 64KB chunks
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield data

        response = Response(
            generate_full(),
            200,
            mimetype="video/mp4",
            direct_passthrough=True,
        )
        response.headers.add("Accept-Ranges", "bytes")
        response.headers.add("Content-Length", str(file_size))
        return response

    except Exception as e:
        logger.error(f"Video streaming error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route("/video/<machine_id>/<path:filename>/thumbnail")
@require_auth
def get_thumbnail(machine_id: str, filename: str):
    """Get or generate thumbnail for a video"""
    from flask import send_file

    try:
        # Validate inputs
        is_valid, error = InputValidator.validate_filename(filename)
        if not is_valid:
            return jsonify({"error": error}), 400

        is_valid, error = InputValidator.validate_machine_id(machine_id)
        if not is_valid:
            return jsonify({"error": error}), 400

        # Check if video exists
        video_path = settings.upload_folder / machine_id / filename
        if not video_path.exists():
            return jsonify({"error": "Video not found"}), 404

        # Check for existing thumbnail
        thumbnail_path = (
            settings.upload_folder / "thumbnails" / f"{video_path.stem}_thumb.jpg"
        )

        if thumbnail_path.exists():
            return send_file(thumbnail_path, mimetype="image/jpeg")

        # Generate thumbnail
        try:
            from video_processor import VideoProcessor

            processor = VideoProcessor(settings.upload_folder / "thumbnails")
            result = processor.generate_thumbnail(video_path)

            if result and result.exists():
                return send_file(result, mimetype="image/jpeg")
        except ImportError:
            pass

        # Return placeholder or 404
        return jsonify({"error": "Thumbnail not available"}), 404

    except Exception as e:
        logger.error(f"Thumbnail error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route("/video-info/<machine_id>/<filename>", methods=["GET"])
def get_video_info(machine_id: str, filename: str):
    """Get video information including duration, resolution, etc."""
    try:
        # Validate inputs
        is_valid, error = InputValidator.validate_filename(filename)
        if not is_valid:
            return jsonify({"error": error}), 400

        is_valid, error = InputValidator.validate_machine_id(machine_id)
        if not is_valid:
            return jsonify({"error": error}), 400

        # Get video file path
        video_path = settings.upload_folder / machine_id / filename
        if not video_path.exists():
            return jsonify({"error": "Video not found"}), 404

        # Get video info
        try:
            from video_processor import VideoProcessor

            processor = VideoProcessor(settings.upload_folder / "thumbnails")
            info = processor.get_video_info(video_path)
            return jsonify(info)
        except ImportError:
            # Fallback to basic info
            return jsonify(
                {
                    "exists": True,
                    "size": video_path.stat().st_size,
                    "duration": None,
                    "width": None,
                    "height": None,
                    "fps": None,
                }
            )

    except Exception as e:
        logger.error(f"Video info error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============ Legacy API Routes (for backward compatibility) ============

# These routes maintain backward compatibility with older clients
legacy_bp = Blueprint("legacy", __name__, url_prefix="/api")


@legacy_bp.route("/upload", methods=["POST"])
@rate_limit(limit=30, window=60)
@validate_license_in_request
def legacy_upload():
    """Legacy upload endpoint - redirects to v1"""
    return upload_video()


@legacy_bp.route("/validate-license", methods=["POST"])
@rate_limit(limit=10, window=60)
def legacy_validate_license():
    """Legacy validate license endpoint"""
    return validate_license()


@legacy_bp.route("/get-machine-id", methods=["GET"])
def legacy_get_machine_id():
    """Legacy get machine ID endpoint"""
    return get_machine_id()


@legacy_bp.route("/get-public-key", methods=["GET"])
def legacy_get_public_key():
    """Legacy get public key endpoint"""
    return get_public_key()
