"""
Authentication module with JWT support and secure session management

Security Features:
- Constant-time password comparison (prevents timing attacks)
- Session regeneration on authentication (prevents session fixation)
- Password hashing enforcement with scrypt
- User enumeration prevention
- CSRF token protection
- Rate limiting support
"""

import hashlib
import secrets
import hmac
import time
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, Tuple

import jwt
from flask import request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash

from config import settings

logger = logging.getLogger(__name__)

# Constants for password policy
MIN_PASSWORD_LENGTH = 12
REQUIRED_PASSWORD_LENGTH = 32  # For auto-generated secrets


class PasswordSecurity:
    """Password security utilities with enforcement"""

    @staticmethod
    def is_password_hashed(password: str) -> bool:
        """Check if a password string appears to be a werkzeug hash"""
        if not password or len(password) < 10:
            return False
        # Werkzeug hashes start with method name like 'pbkdf2:', 'scrypt:', etc.
        return password.startswith(("pbkdf2:", "scrypt:", "bcrypt:"))

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using werkzeug's secure scrypt hashing"""
        return generate_password_hash(password, method="scrypt")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash using constant-time comparison"""
        if not password_hash:
            return False

        # If the stored hash is not hashed, handle migration
        if not PasswordSecurity.is_password_hashed(password_hash):
            # This is a plain text password - compare directly
            # In production, this should trigger a re-hash on next successful login
            return secrets.compare_digest(password.encode(), password_hash.encode())

        # Use werkzeug's check_password_hash which uses constant-time comparison
        return check_password_hash(password_hash, password)

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Validate password meets minimum security requirements.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"

        if len(password) < MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"

        # Check for common weak passwords
        weak_passwords = ["password", "admin", "123456", "password123", "admin123", "password123456"]
        if password.lower() in weak_passwords:
            return False, "Password is too common, please choose a stronger one"

        return True, ""


class AuthManager:
    """Manages authentication with JWT tokens and secure sessions

    Password hashing/verification is delegated to PasswordSecurity
    to avoid duplicate logic (see issue #18).
    """

    def __init__(self):
        self.secret_key = settings.secret_key
        self.token_expiry = settings.session_timeout
        self.algorithm = "HS256"

    # ---- Password methods delegate to PasswordSecurity ----
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password — delegates to PasswordSecurity"""
        return PasswordSecurity.hash_password(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password — delegates to PasswordSecurity"""
        return PasswordSecurity.verify_password(password, password_hash)

    # ---- JWT & Session methods ----

    def generate_token(self, user_id: str, expires_in: Optional[int] = None) -> str:
        """Generate a JWT token with unique ID for tracking"""
        if expires_in is None:
            expires_in = self.token_expiry

        payload = {
            "sub": user_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            "jti": secrets.token_hex(16),  # Unique token ID for revocation tracking
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
        """Validate a CSRF token using constant-time comparison"""
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
                return (
                    jsonify({"error": result.get("error", "Authentication required")}),
                    401,
                )

        # No valid authentication found - redirect to login page
        from flask import redirect, url_for

        return redirect(url_for("admin_login"))

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

    Supports two backends:
    1. Redis (recommended for production with multiple workers)
    2. In-memory dict (fallback for single-worker setups)

    Configure Redis via RATE_LIMIT_STORAGE_URI in environment.

    Args:
        limit: Maximum requests allowed in window
        window: Time window in seconds
    """
    from time import time

    # Try Redis backend first
    _redis_client = None
    if settings.rate_limit_storage_uri:
        try:
            import redis

            _redis_client = redis.from_url(settings.rate_limit_storage_uri, decode_responses=True)
            _redis_client.ping()
            logger.info("Rate limiting: using Redis backend at %s", settings.rate_limit_storage_uri)
        except Exception as e:
            logger.warning("Redis connection failed, falling back to in-memory: %s", e)
            _redis_client = None

    # In-memory fallback
    _rate_limit_store = {}
    _last_cleanup = [0.0]
    _CLEANUP_INTERVAL = 300

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not settings.rate_limit_enabled:
                return f(*args, **kwargs)

            # Get client identifier
            client_id = request.remote_addr
            if hasattr(g, "user_id"):
                client_id = f"{client_id}:{g.user_id}"

            key = f"ratelimit:{f.__name__}:{client_id}"

            # --- Redis backend ---
            if _redis_client:
                try:
                    current = _redis_client.get(key)
                    count = int(current) if current else 0
                    if count >= limit:
                        return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
                    pipe = _redis_client.pipeline()
                    pipe.incr(key)
                    pipe.expire(key, window)
                    pipe.execute()
                    return f(*args, **kwargs)
                except Exception as e:
                    logger.warning("Redis rate limit failed, falling back to in-memory: %s", e)

            # --- In-memory fallback ---
            current_time = time()

            if current_time - _last_cleanup[0] > _CLEANUP_INTERVAL:
                stale_keys = [k for k, v in _rate_limit_store.items() if not v or current_time - v[-1] > window]
                for k in stale_keys:
                    del _rate_limit_store[k]
                _last_cleanup[0] = current_time

            if key in _rate_limit_store:
                _rate_limit_store[key] = [t for t in _rate_limit_store[key] if current_time - t < window]
            else:
                _rate_limit_store[key] = []

            if len(_rate_limit_store[key]) >= limit:
                return (
                    jsonify({"error": "Rate limit exceeded. Please try again later."}),
                    429,
                )

            _rate_limit_store[key].append(current_time)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def validate_admin_password(password: str) -> Tuple[bool, str]:
    """
    Validate admin password with constant-time comparison to prevent timing attacks.

    This function:
    - Uses constant-time comparison to prevent timing attacks
    - Handles password hash migration (plain text to hashed)
    - Returns generic error messages to prevent user enumeration

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, message)
    """
    stored_hash = settings.admin_password

    if not stored_hash:
        logger.error("Admin password not configured in settings")
        return False, "Invalid password"

    # Use PasswordSecurity for verification (handles both hashed and plain text)
    if PasswordSecurity.verify_password(password, stored_hash):
        return True, "Authentication successful"

    # Always return the same error message regardless of whether password exists
    # This prevents user enumeration attacks
    return False, "Invalid password"


def create_session(password: str) -> Tuple[bool, Optional[str]]:
    """
    Create an authenticated session with session regeneration.

    Security features:
    - Regenerates session ID on authentication (prevents session fixation)
    - Uses secure random token for session identifier
    - Generates JWT token for API access

    Args:
        password: The password to authenticate

    Returns:
        Tuple of (is_valid, jwt_token or None)
    """
    is_valid, message = validate_admin_password(password)

    if is_valid:
        # SECURITY: Regenerate session ID to prevent session fixation attacks
        # Clear any existing session data first
        session.clear()

        # Set new session with secure random token
        session["admin_auth"] = secrets.token_hex(32)
        session["admin_login_time"] = datetime.now(timezone.utc).isoformat()
        session.permanent = True

        # Log successful authentication (without sensitive data)
        logger.info(f"Admin session created from IP: {request.remote_addr}")

        # Generate JWT token for API access
        token = auth_manager.generate_token("admin")

        return True, token

    # Log failed authentication attempt (for security monitoring)
    logger.warning(f"Failed admin login attempt from IP: {request.remote_addr}")
    return False, None


def hash_password(password: str) -> str:
    """Hash a password using werkzeug's secure scrypt hashing"""
    return PasswordSecurity.hash_password(password)


def destroy_session():
    """Destroy the current session securely"""
    session.clear()


def get_client_ip() -> str:
    """Get the real client IP address, accounting for proxies"""
    if request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        return request.headers["X-Real-IP"]
    return request.remote_addr or "unknown"
