"""
Screen Recorder Server
Main Flask application with modular architecture
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, redirect, url_for, flash, session, request
from flask_cors import CORS

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

# Import local modules
from config import settings
from models import db, init_db, Client, License, Video, AuditLog
from auth import auth_manager, require_auth, rate_limit, create_session, destroy_session
from routes.api import api_bp, legacy_bp

# Import license manager
from license_manager import LicenseManager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = settings.secret_key
app.config['MAX_CONTENT_LENGTH'] = settings.max_content_length
app.config['SQLALCHEMY_DATABASE_URI'] = settings.database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CORS
CORS(app)

# Initialize database
init_db(app)

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(legacy_bp)


# ============ Key Management ============

def init_keys():
    """Initialize RSA keys for license signing"""
    private_key_path = settings.keys_folder / "private_key.pem"
    public_key_path = settings.keys_folder / "public_key.pem"

    if private_key_path.exists() and public_key_path.exists():
        with open(private_key_path, "r") as f:
            private_key = f.read()
        with open(public_key_path, "r") as f:
            public_key = f.read()
        logger.info("Loaded existing keys")
    else:
        private_key, public_key = LicenseManager.generate_key_pair()
        with open(private_key_path, "w") as f:
            f.write(private_key)
        with open(public_key_path, "w") as f:
            f.write(public_key)
        logger.info("Generated new keys")

    return private_key, public_key


PRIVATE_KEY, PUBLIC_KEY = init_keys()

# Initialize license manager
license_manager = LicenseManager()
license_manager.load_private_key(PRIVATE_KEY)


# ============ Template Creation ============

def create_templates():
    """Create HTML templates"""
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    # Templates are created only if they don't exist
    templates = {
        "login.html": '''<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h4 class="mb-0">Admin Login</h4>
                    </div>
                    <div class="card-body">
                        {% if error %}
                        <div class="alert alert-danger">{{ error }}</div>
                        {% endif %}
                        <form method="POST">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <div class="mb-3">
                                <label class="form-label">Password</label>
                                <input type="password" name="password" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Login</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>''',
        "dashboard.html": '''<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <div>
                <a href="/admin/generate-license" class="btn btn-success btn-sm me-2">Generate License</a>
                <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-white bg-primary">
                    <div class="card-body">
                        <h6>Total Clients</h6>
                        <h2>{{ total_clients }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-success">
                    <div class="card-body">
                        <h6>Total Videos</h6>
                        <h2>{{ total_videos }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-info">
                    <div class="card-body">
                        <h6>Total Storage</h6>
                        <h2>{{ "%.2f"|format(total_size / 1024 / 1024 / 1024) }} GB</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-secondary">
                    <div class="card-body">
                        <h6>Active Licenses</h6>
                        <h2>{{ licenses|length }}</h2>
                    </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header"><h5>Clients</h5></div>
                    <div class="card-body">
                        {% if clients %}
                        <table class="table">
                            <thead><tr><th>Machine ID</th><th>Videos</th><th>Storage</th><th>Actions</th></tr></thead>
                            <tbody>
                                {% for client in clients %}
                                <tr>
                                    <td><code>{{ client.machine_id[:12] }}...</code></td>
                                    <td>{{ client.video_count }}</td>
                                    <td>{{ "%.2f"|format(client.total_size / 1024 / 1024) }} MB</td>
                                    <td><a href="/admin/clients/{{ client.machine_id }}" class="btn btn-sm btn-primary">View</a></td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% else %}
                        <p class="text-muted">No clients yet</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header"><h5>Licenses</h5></div>
                    <div class="card-body">
                        {% if licenses %}
                        <table class="table table-sm">
                            <thead><tr><th>Machine ID</th><th>Expires</th><th>Actions</th></tr></thead>
                            <tbody>
                                {% for license in licenses %}
                                <tr>
                                    <td><code>{{ license.machine_id[:8] }}...</code></td>
                                    <td>{{ license.expires_at[:10] }}</td>
                                    <td>
                                        <form action="/admin/delete-license/{{ license.machine_id }}" method="POST" style="display:inline">
                                            <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Delete this license?')">Delete</button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% else %}
                        <p class="text-muted">No licenses yet</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>''',
        "generate_license.html": '''<!DOCTYPE html>
<html>
<head>
    <title>Generate License - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h5>Generate New License</h5></div>
                    <div class="card-body">
                        <form method="POST">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <div class="mb-3">
                                <label class="form-label">Machine ID</label>
                                <input type="text" name="machine_id" class="form-control" required placeholder="Enter client machine ID">
                                <small class="text-muted">Run the client with --get-id to get the machine ID</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Expiry (Days)</label>
                                <input type="number" name="expiry_days" class="form-control" value="365" min="1">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Features</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="features" value="recording" checked>
                                    <label class="form-check-label">Recording</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="features" value="upload" checked>
                                    <label class="form-check-label">Upload</label>
                                </div>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Generate License</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>''',
        "license_result.html": '''<!DOCTYPE html>
<html>
<head>
    <title>License Generated - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header bg-success text-white"><h5>License Generated Successfully</h5></div>
                    <div class="card-body">
                        <p><strong>Machine ID:</strong> <code>{{ license_info.machine_id }}</code></p>
                        <p><strong>Expires:</strong> {{ license_info.expires_at }}</p>
                        <p><strong>Features:</strong> {{ license_info.features }}</p>
                        <hr>
                        <label class="form-label"><strong>License Key (save as license.key):</strong></label>
                        <textarea class="form-control" rows="5" readonly>{{ license_info.license_key }}</textarea>
                        <div class="mt-3">
                            <button onclick="copyToClipboard()" class="btn btn-primary">Copy to Clipboard</button>
                            <a href="/admin" class="btn btn-secondary">Back to Dashboard</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
    function copyToClipboard() {
        const textarea = document.querySelector('textarea');
        textarea.select();
        document.execCommand('copy');
        alert('License key copied to clipboard!');
    }
    </script>
</body>
</html>''',
        "client.html": '''<!DOCTYPE html>
<html>
<head>
    <title>Client {{ machine_id }} - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Client: <code>{{ machine_id }}</code></h2>
            <a href="/admin" class="btn btn-secondary">Back to Dashboard</a>
        </div>
        {% if videos %}
        <table class="table">
            <thead><tr><th>Filename</th><th>Size</th><th>Created</th><th>Actions</th></tr></thead>
            <tbody>
                {% for video in videos %}
                <tr>
                    <td>{{ video.filename }}</td>
                    <td>{{ "%.2f"|format(video.size / 1024 / 1024) }} MB</td>
                    <td>{{ video.created }}</td>
                    <td>
                        <a href="/admin/download/{{ machine_id }}/{{ video.filename }}" class="btn btn-sm btn-success">Download</a>
                        <form action="/admin/delete-video/{{ machine_id }}/{{ video.filename }}" method="POST" style="display:inline">
                            <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Delete this video?')">Delete</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="alert alert-info">No videos uploaded yet</div>
        {% endif %}
    </div>
</body>
</html>'''
    }
    
    for name, content in templates.items():
        template_path = templates_dir / name
        if not template_path.exists():
            with open(template_path, "w") as f:
                f.write(content)
    
    # Add datetime filter
    app.jinja_env.filters["datetime"] = lambda x: (
        datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S") if x else "N/A"
    )


create_templates()


# ============ Admin Routes ============

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    error = None
    if request.method == "POST":
        from flask import request
        password = request.form.get("password")
        csrf_token = request.form.get("csrf_token")
        
        # Validate CSRF
        if not auth_manager.validate_csrf_token(csrf_token):
            error = "Invalid CSRF token"
        else:
            is_valid, token = create_session(password)
            if is_valid:
                return redirect(url_for("admin_dashboard"))
            else:
                error = "Invalid password"
    
    return render_template("login.html", error=error, csrf_token=auth_manager.generate_csrf_token())


@app.route("/admin/logout")
def admin_logout():
    """Admin logout"""
    destroy_session()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@require_auth
def admin_dashboard():
    """Admin dashboard"""
    from flask import request
    
    # Get statistics from database
    clients = db.session.execute(
        db.select(Client).order_by(Client.last_seen.desc())
    ).scalars().all()
    
    licenses = db.session.execute(
        db.select(License).where(License.is_active == True)
    ).scalars().all()
    
    total_videos = db.session.execute(
        db.select(db.func.count(Video.id))
    ).scalar() or 0
    
    total_size = db.session.execute(
        db.select(db.func.sum(Video.file_size))
    ).scalar() or 0
    
    # Get client video counts
    client_data = []
    for client in clients:
        video_count = db.session.execute(
            db.select(db.func.count(Video.id)).where(Video.client_id == client.id)
        ).scalar() or 0
        
        storage = db.session.execute(
            db.select(db.func.sum(Video.file_size)).where(Video.client_id == client.id)
        ).scalar() or 0
        
        client_data.append({
            "machine_id": client.machine_id,
            "video_count": video_count,
            "total_size": storage,
            "last_seen": client.last_seen
        })
    
    return render_template(
        "dashboard.html",
        clients=client_data,
        licenses=[{
            "machine_id": l.machine_id,
            "expires_at": l.expires_at.isoformat() if l.expires_at else "",
        } for l in licenses],
        total_videos=total_videos,
        total_size=total_size,
        total_clients=len(clients)
    )


@app.route("/admin/generate-license", methods=["GET", "POST"])
@require_auth
def generate_license():
    """Generate a new license"""
    from flask import request
    
    if request.method == "POST":
        machine_id = request.form.get("machine_id")
        expiry_days = int(request.form.get("expiry_days", 365))
        features = request.form.getlist("features")
        
        if not machine_id:
            flash("Machine ID is required", "error")
            return redirect(url_for("generate_license"))
        
        # Generate license
        features_dict = {
            "recording": "recording" in features,
            "upload": "upload" in features,
        }
        
        license_key = license_manager.generate_license(
            machine_id, expiry_days=expiry_days, features=features_dict
        )
        
        # Save to database
        from datetime import timedelta
        license_obj = License(
            machine_id=machine_id,
            license_key=license_key,
            expires_at=datetime.utcnow() + timedelta(days=expiry_days),
            features=features_dict
        )
        db.session.add(license_obj)
        db.session.commit()
        
        license_info = {
            "machine_id": machine_id,
            "license_key": license_key,
            "expires_at": (datetime.utcnow() + timedelta(days=expiry_days)).isoformat(),
            "features": features_dict
        }
        
        flash("License generated successfully", "success")
        return render_template("license_result.html", license_info=license_info)
    
    return render_template("generate_license.html", csrf_token=auth_manager.generate_csrf_token())


@app.route("/admin/clients/<machine_id>")
@require_auth
def view_client(machine_id):
    """View client details and videos"""
    client = db.session.execute(
        db.select(Client).where(Client.machine_id == machine_id)
    ).scalar_one_or_none()
    
    if not client:
        flash("Client not found", "error")
        return redirect(url_for("admin_dashboard"))
    
    videos = db.session.execute(
        db.select(Video).where(Video.client_id == client.id).order_by(Video.upload_time.desc())
    ).scalars().all()
    
    video_data = [{
        "filename": v.filename,
        "size": v.file_size,
        "created": v.upload_time
    } for v in videos]
    
    return render_template("client.html", machine_id=machine_id, videos=video_data)


@app.route("/admin/download/<machine_id>/<filename>")
@require_auth
def download_video(machine_id, filename):
    """Download a video file"""
    from flask import send_file
    
    filepath = settings.upload_folder / machine_id / filename
    
    if not filepath.exists():
        flash("File not found", "error")
        return redirect(url_for("view_client", machine_id=machine_id))
    
    return send_file(filepath, as_attachment=True)


@app.route("/admin/delete-license/<machine_id>", methods=["POST"])
@require_auth
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
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete-video/<machine_id>/<filename>", methods=["POST"])
@require_auth
def delete_video(machine_id, filename):
    """Delete a video file"""
    filepath = settings.upload_folder / machine_id / filename
    
    if filepath.exists():
        filepath.unlink()
        # Also delete from database
        video = db.session.execute(
            db.select(Video).where(Video.filename == filename)
        ).scalar_one_or_none()
        if video:
            db.session.delete(video)
            db.session.commit()
        flash("Video deleted", "success")
    else:
        flash("File not found", "error")
    
    return redirect(url_for("view_client", machine_id=machine_id))


# ============ Main ============

if __name__ == "__main__":
    port = settings.port
    debug = settings.debug
    
    logger.info(f"Starting server on port {port}")
    app.run(host=settings.host, port=port, debug=debug)
</task_progress>
- [x] Security fixes
  - [x] Add proper authentication with JWT
  - [x] Add CSRF protection
  - [x] Add rate limiting
  - [x] Secure license key transmission
- [x] Code quality improvements
  - [x] Fix bare except clauses
  - [x] Add input validation
  - [x] Add type hints throughout
- [x] Architecture improvements
  - [x] Add database support with SQLAlchemy
  - [x] Restructure server code with blueprints
  - [x] Add API versioning
- [x] Add unit tests
- [x] Add Docker support
- [x] Add API documentation
- [x] Client improvements
  - [x] Add retry logic
  - [x] Add offline queue
  - [x] Add heartbeat
</task_progress>
</write_to_file>