"""
Build script for creating the client executable
Run this script to build the client application
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Configuration
PROJECT_DIR = Path(__file__).parent
CLIENT_DIR = PROJECT_DIR / "client"
SHARED_DIR = PROJECT_DIR / "shared"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"


def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build...")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("Clean complete.")


def copy_shared_files():
    """Copy shared files to client directory for building"""
    print("Copying shared files...")

    # Copy license_manager.py to client directory
    src = SHARED_DIR / "license_manager.py"
    dst = CLIENT_DIR / "license_manager.py"
    shutil.copy(src, dst)

    print("Shared files copied.")


def get_public_key():
    """Get public key from server keys directory"""
    keys_dir = PROJECT_DIR / "server" / "keys"
    public_key_path = keys_dir / "public_key.pem"

    if public_key_path.exists():
        dst = CLIENT_DIR / "public_key.pem"
        shutil.copy(public_key_path, dst)
        print(f"Public key copied to client directory.")
        return True
    else:
        print("WARNING: Public key not found. Run the server first to generate keys.")
        return False


def build_executable():
    """Build the client executable using PyInstaller"""
    print("Building executable...")

    # PyInstaller spec file content
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['screen_recorder.py'],
    pathex=[],
    binaries=[],
    datas=[('public_key.pem', '.'), ('license.key', '.') if os.path.exists('license.key') else None],
    hiddenimports=['win32timezone', 'win32service', 'win32serviceutil', 'win32event', 'servicemanager'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out None values from datas
a.datas = [(dest, src, type) for dest, src, type in a.datas if src is not None]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ScreenRecorderClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
"""

    # Write spec file
    spec_path = CLIENT_DIR / "client.spec"
    with open(spec_path, "w") as f:
        f.write(spec_content)

    # Run PyInstaller
    os.chdir(CLIENT_DIR)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--windowed",  # No console window
        "--name",
        "ScreenRecorderClient",
        "--hidden-import",
        "win32timezone",
        "--hidden-import",
        "win32service",
        "--hidden-import",
        "win32serviceutil",
        "--hidden-import",
        "win32event",
        "--hidden-import",
        "servicemanager",
        "--add-data",
        "public_key.pem;.",
        "screen_recorder.py",
    ]

    # Add license key if exists
    license_key = CLIENT_DIR / "license.key"
    if license_key.exists():
        cmd.extend(["--add-data", "license.key;."])

    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Build failed: {result.stderr}")
        return False

    # Move executable to project dist directory
    client_dist = CLIENT_DIR / "dist" / "ScreenRecorderClient.exe"
    if client_dist.exists():
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(client_dist, DIST_DIR / "ScreenRecorderClient.exe")
        print(f"Executable created: {DIST_DIR / 'ScreenRecorderClient.exe'}")
        return True
    else:
        print("Build failed: Executable not found")
        return False


def create_installer():
    """Create an installer script"""
    installer_content = """@echo off
echo Installing Screen Recorder Service...
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Create installation directory
set INSTALL_DIR=%ProgramFiles%\\ScreenRecSvc
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy files
echo Copying files...
copy /Y ScreenRecorderClient.exe "%INSTALL_DIR%\\"
copy /Y license.key "%INSTALL_DIR%\\" 2>nul

:: Create config
echo Creating configuration...
echo {"server_url": "http://YOUR_SERVER_IP:5000", "upload_interval": 300, "recording_fps": 10, "chunk_duration": 60} > "%INSTALL_DIR%\\config.json"

:: Install as service (requires pywin32)
echo Installing as Windows service...
sc create ScreenRecSvc binPath= "%INSTALL_DIR%\\ScreenRecorderClient.exe" start= auto DisplayName= "Screen Recording Service"

:: Start service
echo Starting service...
sc start ScreenRecSvc

echo.
echo Installation complete!
echo The service will start automatically on system boot.
pause
"""

    installer_path = DIST_DIR / "install.bat"
    with open(installer_path, "w") as f:
        f.write(installer_content)

    print(f"Installer created: {installer_path}")


def create_uninstaller():
    """Create an uninstaller script"""
    uninstaller_content = """@echo off
echo Uninstalling Screen Recorder Service...
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Stop service
echo Stopping service...
sc stop ScreenRecSvc 2>nul

:: Delete service
echo Removing service...
sc delete ScreenRecSvc

:: Remove files
echo Removing files...
set INSTALL_DIR=%ProgramFiles%\\ScreenRecSvc
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"

:: Remove AppData
set APPDATA_DIR=%APPDATA%\\ScreenRecSvc
if exist "%APPDATA_DIR%" rmdir /s /q "%APPDATA_DIR%"

echo.
echo Uninstallation complete!
pause
"""

    uninstaller_path = DIST_DIR / "uninstall.bat"
    with open(uninstaller_path, "w") as f:
        f.write(uninstaller_content)

    print(f"Uninstaller created: {uninstaller_path}")


def main():
    """Main build process"""
    print("=" * 50)
    print("Screen Recorder Client Build Script")
    print("=" * 50)
    print()

    # Clean previous build
    clean_build()

    # Copy shared files
    copy_shared_files()

    # Get public key
    if not get_public_key():
        print("\nWARNING: Building without public key.")
        print("The client will need the public key to validate licenses.")
        print("Run the server first to generate keys, then rebuild.")

    # Build executable
    if not build_executable():
        print("\nBuild failed!")
        return 1

    # Create installer scripts
    create_installer()
    create_uninstaller()

    print("\n" + "=" * 50)
    print("Build complete!")
    print(f"Output directory: {DIST_DIR}")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
