"""
Simple test script to check if the screen recorder system will work
"""

import os
import sys
import subprocess


def check_python_version():
    """Check Python version"""
    print("Checking Python version...")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    if version.major == 3 and version.minor >= 8:
        print("[OK] Python version OK")
        return True
    else:
        print("[FAIL] Python 3.8+ required")
        return False


def check_imports():
    """Check if basic imports work"""
    print("\nChecking basic imports...")

    modules_to_check = [
        "mss",  # Screen capture
        "cv2",  # OpenCV
        "numpy",  # Numerical operations
        "PIL",  # Pillow for images
        "requests",  # HTTP requests
        "cryptography",  # License encryption
        "flask",  # Web server
    ]

    all_ok = True
    for module in modules_to_check:
        try:
            __import__(module)
            print(f"[OK] {module} import successful")
        except ImportError as e:
            print(f"[FAIL] {module} import failed: {e}")
            all_ok = False

    return all_ok


def check_shared_modules():
    """Check if shared modules can be imported"""
    print("\nChecking shared modules...")

    # Add shared to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))

    try:
        from license_manager import LicenseManager, MachineIdentifier

        print("[OK] license_manager import successful")

        # Test machine ID generation
        machine_id = MachineIdentifier.get_machine_id()
        print(f"[OK] Machine ID generated: {machine_id[:16]}...")

        return True
    except Exception as e:
        print(f"[FAIL] Shared module import failed: {e}")
        return False


def check_directory_structure():
    """Check if required directories exist"""
    print("\nChecking directory structure...")

    required_dirs = [
        "client",
        "server",
        "shared",
        "server/templates",
    ]

    all_ok = True
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"[OK] Directory exists: {dir_path}")
        else:
            print(f"[FAIL] Missing directory: {dir_path}")
            all_ok = False

    return all_ok


def check_requirements_files():
    """Check if requirements files exist"""
    print("\nChecking requirements files...")

    required_files = [
        "client/requirements.txt",
        "server/requirements.txt",
    ]

    all_ok = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"[OK] File exists: {file_path}")
            # Check if file has content
            with open(file_path, "r") as f:
                content = f.read().strip()
                if content:
                    print(f"  Contains {len(content.splitlines())} lines")
                else:
                    print(f"  Warning: File is empty")
        else:
            print(f"[FAIL] Missing file: {file_path}")
            all_ok = False

    return all_ok


def main():
    """Run all checks"""
    print("=" * 60)
    print("SCREEN RECORDER SYSTEM CHECK")
    print("=" * 60)

    results = {}

    results["python_version"] = check_python_version()
    results["imports"] = check_imports()
    results["shared_modules"] = check_shared_modules()
    results["directory_structure"] = check_directory_structure()
    results["requirements_files"] = check_requirements_files()

    print("\n" + "=" * 60)
    print("CHECK SUMMARY")
    print("=" * 60)

    all_passed = True
    for test, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        symbol = "[OK]" if passed else "[FAIL]"
        print(f"{symbol} {test.replace('_', ' ').title()}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("SYSTEM CHECK: PASSED")
        print("The screen recorder system should work.")
        print("\nNext steps:")
        print("1. Run the server: python start_server.bat")
        print("2. Generate a license from the admin dashboard")
        print("3. Build the client: python build_client.py")
        print("4. Test the client on another machine")
    else:
        print("SYSTEM CHECK: FAILED")
        print("\nIssues found:")
        if not results["python_version"]:
            print("- Python version may be incompatible")
        if not results["imports"]:
            print("- Missing Python dependencies")
            print("  Install with: pip install -r client/requirements.txt")
            print("  Install with: pip install -r server/requirements.txt")
        if not results["shared_modules"]:
            print("- Shared modules have issues")
        if not results["directory_structure"]:
            print("- Directory structure incomplete")
        if not results["requirements_files"]:
            print("- Requirements files missing")

    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
