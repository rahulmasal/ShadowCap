"""
Admin Blueprint — all admin dashboard routes extracted from app.py

This keeps app.py focused on app initialization and lets the admin
routes be maintained independently.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

# Add shared module to path
_shared_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"),
]
for _shared_path in _shared_paths:
    if os.path.isdir(_shared_path):
        sys.path.insert(0, _shared_path)
        break

from config import settings
from models import db, Client, License, Video, AuditLog
from auth import (
    auth_manager,
    require_auth,
    require_csrf,
    create_session,
    destroy_session,
)
from license_manager import LicenseManager

logger = logging.getLogger(__name__)

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../templates",
)


# ============ Login / Logout ============


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        csrf_token = request.form.get("csrf_token")

        # Validate CSRF
        if not auth_manager.validate_csrf_token(csrf_token):
            error = "Invalid CSRF token"
        else:
            is_valid, token = create_session(password)
            if is_valid:
                return redirect(url_for("admin.admin_dashboard"))
            else:
                error = "Invalid password"

    return render_template(
        "login.html", error=error, csrf_token=auth_manager.generate_csrf_token()
    )


@admin_bp.route("/logout", methods=["POST"])
@require_csrf
def admin_logout():
    """Admin logout (requires POST for CSRF protection)"""
    destroy_session()
    return redirect(url_for("admin.admin_login"))


# ============ Dashboard ============


@admin_bp.route("/")
@require_auth
def admin_dashboard():
    """Admin dashboard with pagination support"""
    from sqlalchemy import func

    # Pagination
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    per_page = max(5, min(per_page, 100))
    offset = (page - 1) * per_page

    # Get total client count for pagination
    total_clients = db.session.execute(db.select(func.count(Client.id))).scalar() or 0
    total_pages = max(1, (total_clients + per_page - 1) // per_page)

    # Get paginated clients
    clients = (
        db.session.execute(
            db.select(Client)
            .order_by(Client.last_seen.desc())
            .limit(per_page)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    # Get active licenses
    licenses = (
        db.session.execute(
            db.select(License).where(License.expires_at > datetime.now(timezone.utc))
        )
        .scalars()
        .all()
    )

    # Get aggregated video statistics
    video_stats = db.session.execute(
        db.select(
            Video.client_id,
            func.count(Video.id).label("video_count"),
            func.sum(Video.file_size).label("total_size"),
        ).group_by(Video.client_id)
    ).all()

    # Map stats by client_id
    stats_map = {
        stat.client_id: {
            "video_count": stat.video_count,
            "total_size": stat.total_size or 0,
        }
        for stat in video_stats
    }

    # Prepare client data
    client_data = []
    for client in clients:
        stats = stats_map.get(client.id, {"video_count": 0, "total_size": 0})
        client_data.append(
            {
                "machine_id": client.machine_id,
                "video_count": stats["video_count"],
                "total_size": stats["total_size"],
                "last_seen": client.last_seen,
            }
        )

    # Calculate overall totals (from ALL clients, not just current page)
    total_videos = sum(s.video_count for s in video_stats)
    total_size = sum(s.total_size or 0 for s in video_stats)

    return render_template(
        "dashboard.html",
        clients=client_data,
        licenses=[
            {
                "machine_id": l.machine_id,
                "expires_at": l.expires_at.isoformat() if l.expires_at else "",
            }
            for l in licenses
        ],
        total_videos=total_videos,
        total_size=total_size,
        total_clients=total_clients,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        csrf_token=auth_manager.generate_csrf_token(),
    )


# ============ License Management ============


@admin_bp.route("/generate-license", methods=["GET", "POST"])
@require_auth
@require_csrf
def generate_license():
    """Generate a new license"""
    if request.method == "POST":
        machine_id = request.form.get("machine_id")
        expiry_days = int(request.form.get("expiry_days", 365))
        features = request.form.getlist("features")

        if not machine_id:
            flash("Machine ID is required", "error")
            return redirect(url_for("admin.generate_license"))

        # Generate license
        features_dict = {
            "recording": "recording" in features,
            "upload": "upload" in features,
        }

        # Use the app-level license manager singleton
        from flask import current_app

        lm = current_app.config.get("_license_manager")
        if lm is None:
            flash("Server configuration error: license manager not available", "error")
            return redirect(url_for("admin.generate_license"))

        license_key = lm.generate_license(
            machine_id, expiry_days=expiry_days, features=features_dict
        )

        # Link license to client if client exists
        now = datetime.now(timezone.utc)
        client = db.session.execute(
            db.select(Client).where(Client.machine_id == machine_id)
        ).scalar_one_or_none()

        license_obj = License(
            machine_id=machine_id,
            license_key=license_key,
            expires_at=now + timedelta(days=expiry_days),
            features=features_dict,
            client_id=client.id if client else None,
        )
        db.session.add(license_obj)
        db.session.commit()

        license_info = {
            "machine_id": machine_id,
            "license_key": license_key,
            "expires_at": (now + timedelta(days=expiry_days)).isoformat(),
            "features": features_dict,
        }

        flash("License generated successfully", "success")
        return render_template("license_result.html", license_info=license_info)

    return render_template(
        "generate_license.html", csrf_token=auth_manager.generate_csrf_token()
    )


@admin_bp.route("/delete-license/<machine_id>", methods=["POST"])
@require_auth
@require_csrf
def delete_license(machine_id):
    """Delete a license"""
    license_obj = db.session.execute(
        db.select(License).where(License.machine_id == machine_id)
    ).scalar_one_or_none()

    if license_obj:
        db.session.delete(license_obj)
        db.session.commit()
        flash("License deleted", "success")
    else:
        flash("License not found", "error")

    return redirect(url_for("admin.admin_dashboard"))


# ============ Client Management ============


@admin_bp.route("/clients/<machine_id>")
@require_auth
def view_client(machine_id):
    """View client details and videos"""
    client = db.session.execute(
        db.select(Client).where(Client.machine_id == machine_id)
    ).scalar_one_or_none()

    if not client:
        flash("Client not found", "error")
        return redirect(url_for("admin.admin_dashboard"))

    videos = (
        db.session.execute(
            db.select(Video)
            .where(Video.client_id == client.id)
            .order_by(Video.upload_time.desc())
        )
        .scalars()
        .all()
    )

    video_data = [
        {"filename": v.filename, "size": v.file_size, "created": v.upload_time}
        for v in videos
    ]

    return render_template(
        "client.html",
        machine_id=machine_id,
        videos=video_data,
        csrf_token=auth_manager.generate_csrf_token(),
    )


# ============ Video Management ============


@admin_bp.route("/download/<machine_id>/<filename>")
@require_auth
def download_video(machine_id, filename):
    """Download a video file"""
    filepath = settings.upload_folder / machine_id / filename

    if not filepath.exists():
        flash("File not found", "error")
        return redirect(url_for("admin.view_client", machine_id=machine_id))

    return send_file(filepath, as_attachment=True)


@admin_bp.route("/delete-video/<machine_id>/<filename>", methods=["POST"])
@require_auth
@require_csrf
def delete_video(machine_id, filename):
    """Delete a video file"""
    filepath = settings.upload_folder / machine_id / filename

    if filepath.exists():
        filepath.unlink()
        # Also delete from database
        client = db.session.execute(
            db.select(Client).where(Client.machine_id == machine_id)
        ).scalar_one_or_none()
        if client:
            video = db.session.execute(
                db.select(Video).where(
                    Video.filename == filename,
                    Video.client_id == client.id,
                )
            ).scalar_one_or_none()
            if video:
                db.session.delete(video)
                db.session.commit()
        flash("Video deleted", "success")
    else:
        flash("File not found", "error")

    return redirect(url_for("admin.view_client", machine_id=machine_id))


# ============ Logs ============


@admin_bp.route("/logs")
@require_auth
def admin_logs():
    """Connection and activity logs page"""

    # Query params
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    filter_action = request.args.get("action", "").strip()
    filter_machine_id = request.args.get("machine_id", "").strip()

    per_page = max(10, min(per_page, 200))  # clamp
    offset = (page - 1) * per_page

    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    # ---- Summary counters ----
    active_clients = (
        db.session.execute(
            db.select(db.func.count(Client.id)).where(Client.is_active == True)
        ).scalar()
        or 0
    )

    uploads_24h = (
        db.session.execute(
            db.select(db.func.count(AuditLog.id)).where(
                AuditLog.action == "video_upload",
                AuditLog.timestamp >= since_24h,
            )
        ).scalar()
        or 0
    )

    heartbeats_24h = (
        db.session.execute(
            db.select(db.func.count(AuditLog.id)).where(
                AuditLog.action == "heartbeat",
                AuditLog.timestamp >= since_24h,
            )
        ).scalar()
        or 0
    )

    errors_24h = (
        db.session.execute(
            db.select(db.func.count(AuditLog.id)).where(
                AuditLog.action.like("%error%"),
                AuditLog.timestamp >= since_24h,
            )
        ).scalar()
        or 0
    )

    # ---- Client online status (last heartbeat within 2 minutes = online) ----
    clients_raw = (
        db.session.execute(db.select(Client).order_by(Client.last_seen.desc()))
        .scalars()
        .all()
    )
    clients_status = [
        {
            "machine_id": c.machine_id,
            "online": c.last_seen is not None
            and (now - c.last_seen).total_seconds() < 120,
            "first_seen": (
                c.first_seen.strftime("%Y-%m-%d %H:%M:%S") if c.first_seen else "N/A"
            ),
            "last_seen": (
                c.last_seen.strftime("%Y-%m-%d %H:%M:%S") if c.last_seen else "N/A"
            ),
        }
        for c in clients_raw
    ]

    # ---- Build log query with optional filters ----
    log_query = db.select(AuditLog).order_by(AuditLog.timestamp.desc())
    count_query = db.select(db.func.count(AuditLog.id))

    if filter_action:
        log_query = log_query.where(AuditLog.action == filter_action)
        count_query = count_query.where(AuditLog.action == filter_action)

    # Get total count via SQL (never loads all rows into memory)
    total_logs = db.session.execute(count_query).scalar() or 0
    total_pages = max(1, (total_logs + per_page - 1) // per_page)

    # Apply SQL-level pagination
    log_query = log_query.limit(per_page).offset(offset)
    logs_raw = db.session.execute(log_query).scalars().all()

    # Resolve machine_id for each log via details or entity_id
    log_data = []
    for log in logs_raw:
        machine_id_label = None
        # Check details dict first (heartbeat stores machine_id there)
        if log.details and "machine_id" in log.details:
            mid = log.details["machine_id"]
            if mid:
                machine_id_label = (mid[:16] + "...") if len(mid) > 16 else mid
        elif log.action == "video_upload" and log.entity_id:
            video = db.session.get(Video, log.entity_id)
            if video and video.client and video.client.machine_id:
                machine_id_label = video.client.machine_id[:16] + "..."

        # If a machine_id text filter is active, skip non-matching rows
        if filter_machine_id:
            if (
                not machine_id_label
                or filter_machine_id.lower() not in machine_id_label.lower()
            ):
                continue

        log_data.append(
            {
                "timestamp": (
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
                ),
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "machine_id": machine_id_label,
                "ip_address": log.ip_address,
                "details": log.details or {},
            }
        )

    return render_template(
        "connection_logs.html",
        logs=log_data,
        total_logs=total_logs,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        filter_action=filter_action,
        filter_machine_id=filter_machine_id,
        active_clients=active_clients,
        uploads_24h=uploads_24h,
        heartbeats_24h=heartbeats_24h,
        errors_24h=errors_24h,
        clients=clients_status,
    )
