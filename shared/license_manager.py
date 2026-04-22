"""
License Management System
Handles license generation, validation, and encryption
"""

import hashlib
import base64
import json
import os
from typing import Optional
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import secrets


class LicenseManager:
    """Manages license generation and validation"""

    def __init__(self, private_key=None, public_key=None, passphrase: str = None):
        """
        Initialize the license manager

        Args:
            private_key: RSA private key for signing (server side)
            public_key: RSA public key for verification (client side)
            passphrase: Optional passphrase to decrypt an encrypted private key
        """
        self.private_key = private_key
        self.public_key = public_key
        self.fernet_key = None
        self._passphrase = passphrase

    @staticmethod
    def generate_key_pair(passphrase: Optional[str] = None):
        """Generate RSA key pair for license signing

        Args:
            passphrase: Optional passphrase to encrypt the private key.
                        If provided, the private key is encrypted with
                        BestAvailableEncryption (AES-256-CBC).
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        public_key = private_key.public_key()

        # Serialize keys — encrypt private key if passphrase is provided
        if passphrase:
            encryption = serialization.BestAvailableEncryption(passphrase.encode())
        else:
            encryption = serialization.NoEncryption()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem.decode(), public_pem.decode()

    @staticmethod
    def generate_fernet_key() -> str:
        """Generate a Fernet key for symmetric encryption

        Returns:
            str: Base64-encoded Fernet key as a string
        """
        return Fernet.generate_key().decode("utf-8")

    def load_private_key(self, private_key_pem, passphrase: str = None):
        """Load private key from PEM string

        Args:
            private_key_pem: PEM-encoded private key string or bytes
            passphrase: Optional passphrase to decrypt the key.
                        Falls back to the passphrase provided at init time.
        """
        pwd = passphrase or self._passphrase or None
        if pwd:
            pwd = pwd.encode()
        self.private_key = serialization.load_pem_private_key(
            (
                private_key_pem.encode()
                if isinstance(private_key_pem, str)
                else private_key_pem
            ),
            password=pwd,
            backend=default_backend(),
        )

    def load_public_key(self, public_key_pem):
        """Load public key from PEM string"""
        self.public_key = serialization.load_pem_public_key(
            (
                public_key_pem.encode()
                if isinstance(public_key_pem, str)
                else public_key_pem
            ),
            backend=default_backend(),
        )

    def generate_license(self, machine_id, expiry_days=365, features=None):
        """
        Generate a license for a specific machine

        Args:
            machine_id: Unique identifier for the machine
            expiry_days: Number of days until license expires
            features: Dict of features enabled for this license

        Returns:
            License string (base64 encoded and signed)
        """
        if not self.private_key:
            raise ValueError("Private key required for license generation")

        # Create license data
        license_data = {
            "machine_id": machine_id,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(days=expiry_days)
            ).isoformat(),
            "features": features or {"recording": True, "upload": True},
            "nonce": secrets.token_hex(16),
        }

        # Serialize and sign
        license_json = json.dumps(license_data, sort_keys=True)
        signature = self.private_key.sign(
            license_json.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )

        # Create final license object
        final_license = {
            "data": license_data,
            "signature": base64.b64encode(signature).decode(),
        }

        # Encode to base64
        license_str = base64.b64encode(json.dumps(final_license).encode()).decode()

        return license_str

    def validate_license(self, license_str, machine_id=None):
        """
        Validate a license

        Args:
            license_str: License string to validate
            machine_id: Optional machine ID to verify against

        Returns:
            Tuple of (is_valid, license_data or error_message)
        """
        if not self.public_key:
            raise ValueError("Public key required for license validation")

        try:
            # Decode license
            license_bytes = base64.b64decode(license_str)
            license_obj = json.loads(license_bytes.decode())

            license_data = license_obj["data"]
            signature = base64.b64decode(license_obj["signature"])

            # Verify signature
            license_json = json.dumps(license_data, sort_keys=True)

            try:
                self.public_key.verify(
                    signature,
                    license_json.encode(),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            except Exception:
                return False, "Invalid license signature"

            # Check expiration
            expires_at = datetime.fromisoformat(license_data["expires_at"])
            # Handle offset-naive datetimes from older licenses by assuming UTC
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return False, "License has expired"

            # Verify machine ID if provided
            if machine_id and license_data["machine_id"] != machine_id:
                return False, "License not valid for this machine"

            return True, license_data

        except Exception as e:
            return False, f"License validation error: {str(e)}"

    def get_license_info(self, license_str):
        """Get license information without full validation"""
        try:
            license_bytes = base64.b64decode(license_str)
            license_obj = json.loads(license_bytes.decode())
            return license_obj["data"]
        except Exception:
            return None


class MachineIdentifier:
    """Generates unique machine identifiers"""

    @staticmethod
    def get_machine_id():
        """
        Generate a unique machine identifier based on hardware info
        """
        import platform
        import uuid

        # Gather machine-specific information
        machine_info = [
            platform.node(),  # Computer name
            platform.machine(),  # Machine type
            str(uuid.getnode()),  # MAC address based UUID
        ]

        # Try to get more specific info on Windows
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as key:
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                machine_info.append(machine_guid)
        except Exception:
            pass

        # Create hash
        combined = "|".join(machine_info)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    @staticmethod
    def get_system_info():
        """Get detailed system information"""
        import platform
        import psutil

        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "computer_name": platform.node(),
            "username": os.environ.get("USERNAME", "unknown"),
            "cpu": platform.processor(),
            "ram": f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB",
        }


if __name__ == "__main__":
    # Demo: Generate keys and a test license
    print("Generating RSA key pair...")
    private_key, public_key = LicenseManager.generate_key_pair()

    print("\nPrivate Key:")
    print(private_key)

    print("\nPublic Key:")
    print(public_key)

    # Save keys to files
    os.makedirs("keys", exist_ok=True)
    with open("keys/private_key.pem", "w") as f:
        f.write(private_key)
    with open("keys/public_key.pem", "w") as f:
        f.write(public_key)

    print("\nKeys saved to 'keys' directory")

    # Generate test license
    lm = LicenseManager()
    lm.load_private_key(private_key)

    test_machine_id = MachineIdentifier.get_machine_id()
    print(f"\nMachine ID: {test_machine_id}")

    license_str = lm.generate_license(test_machine_id, expiry_days=365)
    print(f"\nGenerated License:\n{license_str}")

    # Validate license
    lm2 = LicenseManager()
    lm2.load_public_key(public_key)

    is_valid, result = lm2.validate_license(license_str, test_machine_id)
    print(f"\nLicense Valid: {is_valid}")
    if is_valid:
        print(f"License Data: {json.dumps(result, indent=2)}")
    else:
        print(f"Error: {result}")
