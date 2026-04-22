"""
Video encryption at rest — optional AES encryption for stored video files

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the cryptography library,
which is already a project dependency.
"""

import logging
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Module-level encryption key (loaded once at startup)
_fernet: Optional[Fernet] = None


def init_encryption(key: Optional[str] = None) -> None:
    """Initialize the encryption module

    Args:
        key: Base64-encoded Fernet key. If None, encryption is disabled.
    """
    global _fernet
    if key:
        _fernet = Fernet(key.encode())
        logger.info("Video encryption at rest: ENABLED")
    else:
        _fernet = None
        logger.info("Video encryption at rest: disabled (no VIDEO_ENCRYPTION_KEY set)")


def is_encryption_enabled() -> bool:
    """Check if encryption is enabled"""
    return _fernet is not None


def encrypt_file(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """Encrypt a file using Fernet

    Args:
        input_path: Path to the file to encrypt
        output_path: Optional output path (defaults to input_path + .enc)

    Returns:
        Path to the encrypted file
    """
    if not _fernet:
        raise RuntimeError("Encryption not initialized — set VIDEO_ENCRYPTION_KEY")

    if output_path is None:
        output_path = Path(str(input_path) + ".enc")

    data = input_path.read_bytes()
    encrypted = _fernet.encrypt(data)
    output_path.write_bytes(encrypted)

    logger.debug("Encrypted %s -> %s", input_path.name, output_path.name)
    return output_path


def decrypt_file(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """Decrypt a file using Fernet

    Args:
        input_path: Path to the encrypted file
        output_path: Optional output path (defaults to input_path without .enc)

    Returns:
        Path to the decrypted file
    """
    if not _fernet:
        raise RuntimeError("Encryption not initialized — set VIDEO_ENCRYPTION_KEY")

    if output_path is None:
        # Remove .enc extension if present
        if str(input_path).endswith(".enc"):
            output_path = Path(str(input_path)[:-4])
        else:
            output_path = Path(str(input_path) + ".dec")

    data = input_path.read_bytes()
    decrypted = _fernet.decrypt(data)
    output_path.write_bytes(decrypted)

    logger.debug("Decrypted %s -> %s", input_path.name, output_path.name)
    return output_path


def decrypt_bytes(encrypted_data: bytes) -> bytes:
    """Decrypt bytes in memory (for streaming without temp files)

    Args:
        encrypted_data: Encrypted bytes

    Returns:
        Decrypted bytes
    """
    if not _fernet:
        raise RuntimeError("Encryption not initialized — set VIDEO_ENCRYPTION_KEY")
    return _fernet.decrypt(encrypted_data)


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt bytes in memory

    Args:
        data: Plain bytes

    Returns:
        Encrypted bytes
    """
    if not _fernet:
        raise RuntimeError("Encryption not initialized — set VIDEO_ENCRYPTION_KEY")
    return _fernet.encrypt(data)
