#!/usr/bin/env python3
"""
Test the license system
"""
import sys
import os

# Add shared to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))

from license_manager import LicenseManager, MachineIdentifier


def test_license_system():
    print("Testing license system...")

    # Generate keys
    print("1. Generating RSA key pair...")
    private_key, public_key = LicenseManager.generate_key_pair()
    print("   Keys generated successfully")

    # Create license manager with private key
    lm_server = LicenseManager()
    lm_server.load_private_key(private_key)

    # Get machine ID
    print("2. Getting machine ID...")
    machine_id = MachineIdentifier.get_machine_id()
    print(f"   Machine ID: {machine_id}")

    # Generate license
    print("3. Generating license...")
    license_key = lm_server.generate_license(
        machine_id, expiry_days=365, features={"recording": True, "upload": True}
    )
    print(f"   License generated (length: {len(license_key)} chars)")

    # Validate license
    print("4. Validating license...")
    lm_client = LicenseManager()
    lm_client.load_public_key(public_key)

    is_valid, result = lm_client.validate_license(license_key, machine_id)
    if is_valid:
        print("   License is valid")
        print(f"   Expires: {result['expires_at']}")
        print(f"   Features: {result['features']}")
    else:
        print(f"   License validation failed: {result}")
        return False

    # Test with wrong machine ID
    print("5. Testing with wrong machine ID...")
    is_valid, result = lm_client.validate_license(license_key, "wrong_machine_id")
    if not is_valid:
        print("   Correctly rejected wrong machine ID")
    else:
        print("   Should have rejected wrong machine ID")
        return False

    # Test tampered license
    print("6. Testing tampered license...")
    tampered_license = license_key[:-10] + "XXXXXXXXX"
    is_valid, result = lm_client.validate_license(tampered_license, machine_id)
    if not is_valid:
        print("   Correctly rejected tampered license")
    else:
        print("   Should have rejected tampered license")
        return False

    print("\nLicense System Tests: PASSED")
    return True


if __name__ == "__main__":
    try:
        success = test_license_system()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
