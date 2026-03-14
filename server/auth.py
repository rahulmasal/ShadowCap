"""
Authentication module with JWT support and secure session management
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Tuple

import jwt
from flask import request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash

from config import settings


class AuthManager:
    """Manages authentication with JWT tokens and secure sessions"""

    def __init__(self):
        self.secret_key = settings.secret_key
        self.token_expiry = settings.session_timeout
        self.algorithm = "HS256"

    def hash_password(self, password: str) -> str:
        """Hash a password using werkzeug"""
        return generate_password_hash(password, method="scrypt")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return check_password_hash(password_hash, password)

    def generate_token(self, user_id: str, expires_in: Optional[int] = None) -> str:
        """Generate a JWT token"""
        if expires_in is None:
            expires_in = self.token_expiry

        payload = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=expires_in),
            "jti": secrets.token_hex(16),  # Unique token ID
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Tuple[bool, Optional[dict]]:
        """Verify a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, {"error": "Token has expired"}
        except jwt.InvalidTokenError as e:
            return False, {"error": f"Invalid token: {str(e)}"}

    def generate_csrf_token(self) -> str:
        """Generate a CSRF token"""
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(32)
        return session["_csrf_token"]

    def validate_csrf_token(self, token: str) -> bool:
        """Validate a CSRF token"""
        session_token = session.get("_csrf_token")
        if session_token and token and secrets.compare_digest(session_token, token):
            return True
        return False


# Global auth manager instance
auth_manager = AuthManager()


def require_auth(f):
    """Decorator to require authentication for a route"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session auth first
        if session.get("admin_auth"):
            g.user_id = "admin"
            return f(*args, **kwargs)

        # Check JWT token in header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            is_valid, result = auth_manager.verify_token(token)
            if is_valid:
                g.user_id = result["sub"]
                return f(*args, **kwargs)
            else:
                return jsonify({"error": result.get("error", "Authentication required")}), 401

        # No valid authentication found
        return jsonify({"error": "Authentication required"}), 401

    return decorated_function


def require_csrf(f):
    """Decorator to require CSRF token for POST/PUT/DELETE requests"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ["POST", "PUT", "DELETE"]:
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not auth_manager.validate_csrf_token(token):
                return jsonify({"error": "Invalid CSRF token"}), 403
        return f(*args, **kwargs)

    return decorated_function


def rate_limit(limit: int = 60, window: int = 60):
    """Decorator for rate limiting requests

    Args:
        limit: Maximum requests allowed in window
        window: Time window in seconds
    """
    from time import time

    # Simple in-memory rate limiting (use Redis in production)
    _rate_limit_store = {}

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not settings.rate_limit_enabled:
                return f(*args, **kwargs)

            # Get client identifier (IP + optional user ID)
            client_id = request.remote_addr
            if hasattr(g, "user_id"):
                client_id = f"{client_id}:{g.user_id}"

            current_time = time()
            key = f"{f.__name__}:{client_id}"

            # Clean old entries
            if key in _rate_limit_store:
                _rate_limit_store[key] = [
                    t for t in _rate_limit_store[key] if current_time - t < window
                ]
            else:
                _rate_limit_store[key] = []

            # Check limit
            if len(_rate_limit_store[key]) >= limit:
                return jsonify(
                    {"error": "Rate limit exceeded. Please try again later."}
                ), 429

            # Record request
            _rate_limit_store[key].append(current_time)

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def validate_admin_password(password: str) -> Tuple[bool, str]:
    """Validate admin password with rate limiting"""
    # Use werkzeug's secure password hashing
    from werkzeug.security import check_password_hash, generate_password_hash
    
    # For backward compatibility, check if password is already hashed
    # If not, hash it and store (this should be done during setup)
    stored_hash = settings.admin_password
    
    # If the stored password looks like a plain text (not a werkzeug hash),
    # we need to hash it. In production, passwords should be pre-hashed.
    if not stored_hash.startswith(('pbkdf2:', 'scrypt:')):
        # Plain text password - hash it for comparison
        stored_hash = generate_password_hash(stored_hash, method='scrypt')
    
    if check_password_hash(stored_hash, password):
        return True, "Authentication successful"
    return False, "Invalid password"


def create_session(password: str) -> Tuple[bool, Optional[str]]:
    """Create an authenticated session"""
    is_valid, message = validate_admin_password(password)

    if is_valid:
        # Set session - use a secure token instead of password hash
        session["admin_auth"] = secrets.token_hex(32)
        session["admin_login_time"] = datetime.utcnow().isoformat()
        session.permanent = True

        # Generate JWT token for API access
        token = auth_manager.generate_token("admin")

        return True, token

    return False, None


def hash_password(password: str) -> str:
    """Hash a password using werkzeug's secure hashing"""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password, method='scrypt')


def destroy_session():
    """Destroy the current session"""
    session.clear()


def get_client_ip() -> str:
    """Get the real client IP address"""
    if request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        return request.headers["X-Real-IP"]
    return request.remote_addr or "unknown"
</task_progress>
- [ ] Security fixes
  - [x] Add proper authentication with JWT
  - [x] Add CSRF protection
  - [x] Add rate limiting
  - [ ] Secure license key transmission
- [ ] Code quality improvements
  - [ ] Fix bare except clauses
  - [ ] Add input validation
  - [ ] Add type hints
- [ ] Architecture improvements
  - [x] Add database support with SQLAlchemy
  - [ ] Restructure server code
  - [ ] Add API versioning
- [ ] Add unit tests
- [ ] Add Docker support
- [ ] Add API documentation
- [ ] Client improvements
  - [ ] Add retry logic
  - [ ] Add offline queue
  - [ ] Add heartbeat
</task_progress>
</write_to_file>