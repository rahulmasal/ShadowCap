"""
API Key authentication module — implements the unused ApiKey model

Provides programmatic access to the API without admin sessions.
API keys are hashed with scrypt and can have scoped permissions.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple

from flask import request, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, ApiKey

logger = logging.getLogger(__name__)


def generate_api_key(
    name: str, permissions: Optional[dict] = None, expires_days: Optional[int] = None
) -> Tuple[str, ApiKey]:
    """Generate a new API key

    Args:
        name: Human-readable name for the key
        permissions: Dict of permissions, e.g. {"read": True, "upload": True}
        expires_days: Optional expiry in days (None = never expires)

    Returns:
        Tuple of (raw_key_string, ApiKey_model_instance)
        The raw key is only returned once — it cannot be retrieved later.
    """
    # Generate a secure random key
    raw_key = f"sc_{secrets.token_hex(32)}"

    # Hash for storage (we only store the hash)
    key_hash = generate_password_hash(raw_key, method="scrypt")

    expires_at = None
    if expires_days:
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    api_key = ApiKey(
        key_hash=key_hash,
        name=name,
        permissions=permissions or {"read": True},
        expires_at=expires_at,
    )
    db.session.add(api_key)
    db.session.commit()

    logger.info("API key created: %s (id=%d)", name, api_key.id)
    return raw_key, api_key


def revoke_api_key(key_id: int) -> bool:
    """Revoke an API key by ID"""
    api_key = db.session.get(ApiKey, key_id)
    if api_key:
        api_key.is_active = False
        db.session.commit()
        logger.info("API key revoked: %s (id=%d)", api_key.name, key_id)
        return True
    return False


def validate_api_key(raw_key: str) -> Tuple[bool, Optional[ApiKey]]:
    """Validate a raw API key string

    Args:
        raw_key: The API key string from the request header

    Returns:
        Tuple of (is_valid, ApiKey_instance_or_None)
    """
    if not raw_key or not raw_key.startswith("sc_"):
        return False, None

    # Check all active keys (there should be very few)
    active_keys = db.session.execute(db.select(ApiKey).where(ApiKey.is_active == True)).scalars().all()

    for api_key in active_keys:
        # Check expiry
        if api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
            continue

        # Constant-time comparison via werkzeug
        if check_password_hash(api_key.key_hash, raw_key):
            # Update last_used timestamp
            api_key.last_used = datetime.now(timezone.utc)
            db.session.commit()
            return True, api_key

    return False, None


def require_api_key(f):
    """Decorator to require API key authentication for a route

    Checks the X-API-Key header for a valid API key.
    Can be used alongside or instead of @require_auth.
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key_str = request.headers.get("X-API-Key")
        if not api_key_str:
            return jsonify({"error": "API key required. Pass via X-API-Key header."}), 401

        is_valid, api_key = validate_api_key(api_key_str)
        if not is_valid:
            return jsonify({"error": "Invalid or expired API key"}), 401

        # Store API key info in request context
        g.api_key = api_key
        g.api_key_permissions = api_key.permissions or {}
        g.user_id = f"apikey:{api_key.name}"

        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission: str):
    """Decorator to require a specific API key permission

    Must be used after @require_api_key
    """
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            permissions = getattr(g, "api_key_permissions", {})
            if not permissions.get(permission, False):
                return jsonify({"error": f"Permission '{permission}' not granted for this API key"}), 403
            return f(*args, **kwargs)

        return decorated_function

    return decorator
