"""
Pytest configuration and fixtures for Screen Recorder tests
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "shared"))
sys.path.insert(0, str(project_root / "server"))


@pytest.fixture(scope="session")
def project_root_path() -> Path:
    """Return the project root directory"""
    return project_root


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary file for test data"""
    temp_file = temp_dir / "test_file.txt"
    temp_file.write_text("test content")
    yield temp_file


@pytest.fixture(scope="session")
def test_machine_id() -> str:
    """Return a test machine ID (valid hex string matching validator pattern ^[a-fA-F0-9]{32,64}$)"""
    return "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


@pytest.fixture(scope="session")
def test_license_key() -> str:
    """Return a test license key (not valid, just for format testing)"""
    return "test_license_key_1234567890abcdef1234567890abcdef"


@pytest.fixture(scope="function")
def mock_config(temp_dir: Path) -> dict:
    """Return a mock configuration dictionary"""
    return {
        "server_url": "http://localhost:5000",
        "upload_interval": 300,
        "recording_fps": 10,
        "video_quality": 80,
        "chunk_duration": 60,
        "heartbeat_interval": 60,
        "max_offline_storage_mb": 1000,
        "retry_base_delay": 1.0,
        "retry_max_delay": 300.0,
        "monitor_selection": 1,
        "region_x": 0,
        "region_y": 0,
        "region_width": 0,
        "region_height": 0,
        "enable_audio": False,
        "audio_sample_rate": 44100,
        "audio_channels": 2,
        "enable_compression": True,
        "compression_quality": 23,
        "generate_thumbnails": True,
        "thumbnail_pct": 0.1,
        "ffmpeg_path": "ffmpeg",
        "use_websocket": False,
        "websocket_url": "http://localhost:5000",
    }


# Skip tests that require actual hardware
def pytest_collection_modifyitems(config, items):
    """Add custom markers to tests"""
    for item in items:
        # Mark tests that require actual screen capture
        if "screen_capture" in item.nodeid.lower():
            item.add_marker(pytest.mark.screen_capture)
        # Mark tests that require audio hardware
        if "audio" in item.nodeid.lower():
            item.add_marker(pytest.mark.audio)
        # Mark tests that require network
        if "network" in item.nodeid.lower() or "upload" in item.nodeid.lower():
            item.add_marker(pytest.mark.network)


# Configure pytest markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "screen_capture: mark test as requiring screen capture hardware"
    )
    config.addinivalue_line("markers", "audio: mark test as requiring audio hardware")
    config.addinivalue_line("markers", "network: mark test as requiring network access")
    config.addinivalue_line("markers", "slow: mark test as slow running")
