"""
Test script to verify the Screen Recorder system
Run this script to test all components
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))

from license_manager import LicenseManager, MachineIdentifier


def test_license_system():
    """Test the license generation and validation system"""
    print("\n" + "=" * 50)
    print("Testing License System")
    print("=" * 50)

    # Generate keys
    print("\n1. Generating RSA key pair...")
    private_key, public_key = LicenseManager.generate_key_pair()
    print("   ✓ Keys generated successfully")

    # Create license manager with private key
    lm_server = LicenseManager()
    lm_server.load_private_key(private_key)

    # Get machine ID
    print("\n2. Getting machine ID...")
    machine_id = MachineIdentifier.get_machine_id()
    print(f"   ✓ Machine ID: {machine_id}")

    # Generate license
    print("\n3. Generating license...")
    license_key = lm_server.generate_license(
        machine_id, expiry_days=365, features={"recording": True, "upload": True}
    )
    print(f"   ✓ License generated (length: {len(license_key)} chars)")

    # Validate license
    print("\n4. Validating license...")
    lm_client = LicenseManager()
    lm_client.load_public_key(public_key)

    is_valid, result = lm_client.validate_license(license_key, machine_id)
    if is_valid:
        print("   ✓ License is valid")
        print(f"   Expires: {result['expires_at']}")
        print(f"   Features: {result['features']}")
    else:
        print(f"   ✗ License validation failed: {result}")
        return False

    # Test with wrong machine ID
    print("\n5. Testing with wrong machine ID...")
    is_valid, result = lm_client.validate_license(license_key, "wrong_machine_id")
    if not is_valid:
        print("   ✓ Correctly rejected wrong machine ID")
    else:
        print("   ✗ Should have rejected wrong machine ID")
        return False

    # Test tampered license
    print("\n6. Testing tampered license...")
    tampered_license = license_key[:-10] + "XXXXXXXXX"
    is_valid, result = lm_client.validate_license(tampered_license, machine_id)
    if not is_valid:
        print("   ✓ Correctly rejected tampered license")
    else:
        print("   ✗ Should have rejected tampered license")
        return False

    print("\n" + "=" * 50)
    print("License System Tests: PASSED")
    print("=" * 50)
    return True


def test_screen_capture():
    """Test screen capture functionality"""
    print("\n" + "=" * 50)
    print("Testing Screen Capture")
    print("=" * 50)

    try:
        import mss
        import numpy as np
        from PIL import Image

        print("\n1. Initializing screen capture...")
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            print(f"   ✓ Monitor detected: {monitor['width']}x{monitor['height']}")

            print("\n2. Capturing screenshot...")
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            print(f"   ✓ Screenshot captured: {img.size}")

            # Save test screenshot
            test_dir = Path(tempfile.gettempdir()) / "screen_recorder_test"
            test_dir.mkdir(exist_ok=True)
            test_file = test_dir / "test_screenshot.png"
            img.save(test_file)
            print(f"   ✓ Saved to: {test_file}")

        print("\n" + "=" * 50)
        print("Screen Capture Tests: PASSED")
        print("=" * 50)
        return True

    except ImportError as e:
        print(f"   ✗ Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_video_recording():
    """Test video recording functionality"""
    print("\n" + "=" * 50)
    print("Testing Video Recording")
    print("=" * 50)

    try:
        import cv2
        import mss
        import numpy as np

        print("\n1. Initializing video writer...")
        test_dir = Path(tempfile.gettempdir()) / "screen_recorder_test"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "test_video.mp4"

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            width, height = monitor["width"], monitor["height"]

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(str(test_file), fourcc, 10.0, (width, height))
            print(f"   ✓ Video writer initialized: {width}x{height}")

            print("\n2. Recording 10 frames...")
            for i in range(10):
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                out.write(frame)

            out.release()
            print(f"   ✓ Video recorded: {test_file}")
            print(f"   File size: {test_file.stat().st_size} bytes")

        print("\n" + "=" * 50)
        print("Video Recording Tests: PASSED")
        print("=" * 50)
        return True

    except ImportError as e:
        print(f"   ✗ Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_server_imports():
    """Test server module imports"""
    print("\n" + "=" * 50)
    print("Testing Server Imports")
    print("=" * 50)

    try:
        print("\n1. Testing Flask import...")
        from flask import Flask

        print("   ✓ Flask imported successfully")

        print("\n2. Testing Flask-CORS import...")
        from flask_cors import CORS

        print("   ✓ Flask-CORS imported successfully")

        print("\n3. Testing cryptography import...")
        from cryptography.hazmat.primitives import hashes

        print("   ✓ Cryptography imported successfully")

        print("\n" + "=" * 50)
        print("Server Import Tests: PASSED")
        print("=" * 50)
        return True

    except ImportError as e:
        print(f"   ✗ Missing dependency: {e}")
        return False


def check_dependencies():
    """Check all required dependencies"""
    print("\n" + "=" * 50)
    print("Checking Dependencies")
    print("=" * 50)

    dependencies = {
        "client": [
            ("mss", "Screen capture"),
            ("cv2", "Video recording (opencv-python)"),
            ("numpy", "Array operations"),
            ("PIL", "Image processing (Pillow)"),
            ("requests", "HTTP requests"),
            ("cryptography", "License validation"),
        ],
        "server": [
            ("flask", "Web server"),
            ("flask_cors", "CORS support"),
            ("cryptography", "License signing"),
            ("dotenv", "Environment variables (python-dotenv)"),
        ],
    }

    all_ok = True

    print("\nClient Dependencies:")
    for module, name in dependencies["client"]:
        try:
            __import__(module)
            print(f"   ✓ {name} ({module})")
        except ImportError:
            print(f"   ✗ {name} ({module}) - NOT INSTALLED")
            all_ok = False

    print("\nServer Dependencies:")
    for module, name in dependencies["server"]:
        try:
            __import__(module)
            print(f"   ✓ {name} ({module})")
        except ImportError:
            print(f"   ✗ {name} ({module}) - NOT INSTALLED")
            all_ok = False

    return all_ok


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  SCREEN RECORDER SYSTEM TEST")
    print("=" * 60)

    results = {}

    # Check dependencies
    results["dependencies"] = check_dependencies()

    # Test license system
    results["license"] = test_license_system()

    # Test screen capture
    results["capture"] = test_screen_capture()

    # Test video recording
    results["video"] = test_video_recording()

    # Test server imports
    results["server"] = test_server_imports()

    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        symbol = "✓" if passed else "✗"
        print(f"   {symbol} {test.capitalize()}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("  ALL TESTS PASSED!")
        print("  The system is ready to use.")
    else:
        print("  SOME TESTS FAILED!")
        print("  Please install missing dependencies:")
        print("    cd client && pip install -r requirements.txt")
        print("    cd server && pip install -r requirements.txt")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
