"""
Tests for database models
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestClientModel:
    """Test cases for Client model"""

    def test_client_repr(self):
        from models import Client

        client = Client(machine_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")
        assert "a1b2c3d4e5f6" in repr(client)

    def test_client_defaults(self):
        from models import Client

        client = Client(machine_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")
        assert client.is_active is True


class TestLicenseModel:
    """Test cases for License model"""

    def test_license_not_expired(self):
        from models import License

        future = datetime.now(timezone.utc) + timedelta(days=30)
        license_obj = License(
            machine_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            license_key="test_key",
            expires_at=future,
        )
        assert license_obj.is_expired is False

    def test_license_expired(self):
        from models import License

        past = datetime.now(timezone.utc) - timedelta(days=1)
        license_obj = License(
            machine_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            license_key="test_key",
            expires_at=past,
        )
        assert license_obj.is_expired is True

    def test_license_days_remaining(self):
        from models import License

        future = datetime.now(timezone.utc) + timedelta(days=30)
        license_obj = License(
            machine_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            license_key="test_key",
            expires_at=future,
        )
        assert 29 <= license_obj.days_remaining <= 31

    def test_license_days_remaining_expired(self):
        from models import License

        past = datetime.now(timezone.utc) - timedelta(days=10)
        license_obj = License(
            machine_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            license_key="test_key",
            expires_at=past,
        )
        assert license_obj.days_remaining == 0


class TestVideoModel:
    """Test cases for Video model"""

    def test_file_size_mb(self):
        from models import Video

        video = Video(
            filename="test.mp4",
            original_filename="test.mp4",
            file_path="/uploads/test.mp4",
            file_size=1024 * 1024 * 5,  # 5 MB
            client_id=1,
        )
        assert video.file_size_mb == 5.0

    def test_file_size_gb(self):
        from models import Video

        video = Video(
            filename="test.mp4",
            original_filename="test.mp4",
            file_path="/uploads/test.mp4",
            file_size=1024 * 1024 * 1024 * 2,  # 2 GB
            client_id=1,
        )
        assert video.file_size_gb == 2.0

    def test_video_repr(self):
        from models import Video

        video = Video(filename="test.mp4", original_filename="test.mp4", file_path="/uploads/test.mp4", client_id=1)
        assert "test.mp4" in repr(video)
