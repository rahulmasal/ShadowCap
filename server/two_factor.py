"""
Two-Factor Authentication (2FA) module for admin login

Implements TOTP (Time-based One-Time Password) using pyotp.
Provides setup, verification, and QR code generation.
"""

import logging
import os
import secrets
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import pyotp (optional dependency)
try:
    import pyotp
    import qrcode
    import io
    import base64

    TOTP_AVAILABLE = True
except ImportError:
    TOTP_AVAILABLE = False
    logger.info("pyotp not installed — 2FA disabled. Install with: pip install pyotp qrcode")


def is_2fa_available() -> bool:
    """Check if 2FA dependencies are available"""
    return TOTP_AVAILABLE


def generate_2fa_secret() -> str:
    """Generate a new TOTP secret for 2FA setup"""
    if not TOTP_AVAILABLE:
        raise RuntimeError("pyotp not installed — cannot generate 2FA secret")
    return pyotp.random_base32()


def get_totp(secret: str):
    """Get a TOTP instance from a secret"""
    if not TOTP_AVAILABLE:
        raise RuntimeError("pyotp not installed")
    return pyotp.TOTP(secret)


def verify_2fa_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a TOTP code

    Args:
        secret: The TOTP secret
        code: The 6-digit code from the authenticator app
        valid_window: Number of time steps to check (allows clock drift)

    Returns:
        True if the code is valid
    """
    if not TOTP_AVAILABLE:
        logger.error("2FA verification attempted but pyotp not installed")
        return False

    totp = get_totp(secret)
    return totp.verify(code, valid_window=valid_window)


def generate_qr_code_data_uri(secret: str, issuer: str = "ShadowCap", account: str = "admin") -> str:
    """Generate a QR code as a data URI for embedding in HTML

    Args:
        secret: The TOTP secret
        issuer: Name of the issuer (shown in authenticator app)
        account: Account name (shown in authenticator app)

    Returns:
        Base64-encoded data URI of the QR code PNG image
    """
    if not TOTP_AVAILABLE:
        raise RuntimeError("pyotp/qrcode not installed")

    totp = get_totp(secret)
    provisioning_uri = totp.provisioning_uri(name=account, issuer_name=issuer)

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


def generate_backup_codes(count: int = 10) -> list:
    """Generate one-time backup codes for 2FA recovery

    Args:
        count: Number of backup codes to generate

    Returns:
        List of backup code strings
    """
    return [secrets.token_hex(4).upper() for _ in range(count)]


class TwoFactorManager:
    """Manages 2FA state for the admin account

    Stores the 2FA secret and backup codes in the server's data directory.
    In production, this should be stored in the database or a secrets manager.
    """

    def __init__(self, data_dir: str = "data"):
        self._data_dir = data_dir
        self._secret_file = os.path.join(data_dir, ".2fa_secret")
        self._backup_codes_file = os.path.join(data_dir, ".2fa_backup_codes")

    @property
    def is_enabled(self) -> bool:
        """Check if 2FA is enabled"""
        return os.path.exists(self._secret_file)

    def setup(self) -> Tuple[str, str, list]:
        """Set up 2FA for the first time

        Returns:
            Tuple of (secret, qr_data_uri, backup_codes)
        """
        if not TOTP_AVAILABLE:
            raise RuntimeError("pyotp not installed — cannot set up 2FA")

        secret = generate_2fa_secret()
        qr_uri = generate_qr_code_data_uri(secret)
        backup_codes = generate_backup_codes()

        # Store secret
        os.makedirs(self._data_dir, exist_ok=True)
        with open(self._secret_file, "w") as f:
            f.write(secret)

        # Store backup codes (hashed for security)
        from werkzeug.security import generate_password_hash

        with open(self._backup_codes_file, "w") as f:
            for code in backup_codes:
                f.write(generate_password_hash(code) + "\n")

        logger.info("2FA setup completed — secret stored")
        return secret, qr_uri, backup_codes

    def verify(self, code: str) -> bool:
        """Verify a 2FA code (TOTP or backup code)

        Args:
            code: 6-digit TOTP code or 8-character backup code

        Returns:
            True if valid
        """
        if not self.is_enabled:
            return True  # 2FA not enabled, skip verification

        # Read secret
        with open(self._secret_file, "r") as f:
            secret = f.read().strip()

        # Try TOTP verification first
        if len(code) == 6 and code.isdigit():
            return verify_2fa_code(secret, code)

        # Try backup code
        if len(code) == 8:
            return self._verify_backup_code(code)

        return False

    def _verify_backup_code(self, code: str) -> bool:
        """Verify and consume a backup code"""
        from werkzeug.security import check_password_hash

        if not os.path.exists(self._backup_codes_file):
            return False

        with open(self._backup_codes_file, "r") as f:
            lines = f.readlines()

        remaining = []
        found = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not found and check_password_hash(line, code):
                found = True
                # Don't add to remaining (consume the code)
            else:
                remaining.append(line)

        if found:
            # Write back remaining codes
            with open(self._backup_codes_file, "w") as f:
                for line in remaining:
                    f.write(line + "\n")
            logger.info("Backup code used — %d remaining", len(remaining))

        return found

    def disable(self) -> None:
        """Disable 2FA by removing secret and backup codes"""
        for path in [self._secret_file, self._backup_codes_file]:
            if os.path.exists(path):
                os.remove(path)
        logger.info("2FA disabled")
