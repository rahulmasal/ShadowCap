"""
Key management module — extracted from app.py

Handles RSA key generation, loading, and encrypted storage.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from license_manager import LicenseManager

logger = logging.getLogger(__name__)


def init_keys(
    keys_folder: Path,
    passphrase: Optional[str] = None,
) -> Tuple[str, str]:
    """Initialize RSA keys for license signing

    If a passphrase is provided, the private key is encrypted at rest
    using AES-256-CBC (BestAvailableEncryption).

    Args:
        keys_folder: Directory where keys are stored
        passphrase: Optional passphrase to encrypt the private key

    Returns:
        Tuple of (private_key_pem, public_key_pem)
    """
    private_key_path = keys_folder / "private_key.pem"
    public_key_path = keys_folder / "public_key.pem"

    if private_key_path.exists() and public_key_path.exists():
        with open(private_key_path, "r") as f:
            private_key = f.read()
        with open(public_key_path, "r") as f:
            public_key = f.read()
        logger.info("Loaded existing keys%s", " (encrypted)" if passphrase else "")
    else:
        private_key, public_key = LicenseManager.generate_key_pair(passphrase=passphrase)
        keys_folder.mkdir(parents=True, exist_ok=True)
        with open(private_key_path, "w") as f:
            f.write(private_key)
        with open(public_key_path, "w") as f:
            f.write(public_key)
        logger.info("Generated new keys%s", " (encrypted)" if passphrase else "")

    return private_key, public_key
