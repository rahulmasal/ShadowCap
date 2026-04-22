"""
Tests for authentication module
"""

import pytest
from unittest.mock import patch, MagicMock


class TestPasswordSecurity:
    """Test cases for PasswordSecurity class"""

    def test_hash_password_returns_hash(self):
        from auth import PasswordSecurity

        result = PasswordSecurity.hash_password("test_password_123")
        assert result.startswith(("pbkdf2:", "scrypt:", "bcrypt:"))

    def test_hash_password_different_each_time(self):
        from auth import PasswordSecurity

        h1 = PasswordSecurity.hash_password("same_password")
        h2 = PasswordSecurity.hash_password("same_password")
        assert h1 != h2  # Different salts

    def test_verify_password_correct(self):
        from auth import PasswordSecurity

        hashed = PasswordSecurity.hash_password("my_secure_password")
        assert PasswordSecurity.verify_password("my_secure_password", hashed) is True

    def test_verify_password_incorrect(self):
        from auth import PasswordSecurity

        hashed = PasswordSecurity.hash_password("my_secure_password")
        assert PasswordSecurity.verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_hash(self):
        from auth import PasswordSecurity

        assert PasswordSecurity.verify_password("password", "") is False

    def test_is_password_hashed_true(self):
        from auth import PasswordSecurity

        assert PasswordSecurity.is_password_hashed("scrypt:260000:salt$hash") is True
        assert PasswordSecurity.is_password_hashed("pbkdf2:sha256:260000$salt$hash") is True

    def test_is_password_hashed_false(self):
        from auth import PasswordSecurity

        assert PasswordSecurity.is_password_hashed("plaintext") is False
        assert PasswordSecurity.is_password_hashed("") is False
        assert PasswordSecurity.is_password_hashed("short") is False

    def test_validate_password_strength_valid(self):
        from auth import PasswordSecurity

        is_valid, msg = PasswordSecurity.validate_password_strength("secure_password_123")
        assert is_valid is True
        assert msg == ""

    def test_validate_password_strength_too_short(self):
        from auth import PasswordSecurity

        is_valid, msg = PasswordSecurity.validate_password_strength("short")
        assert is_valid is False
        assert "at least" in msg

    def test_validate_password_strength_empty(self):
        from auth import PasswordSecurity

        is_valid, msg = PasswordSecurity.validate_password_strength("")
        assert is_valid is False

    def test_validate_password_strength_weak(self):
        from auth import PasswordSecurity

        is_valid, msg = PasswordSecurity.validate_password_strength("password123456")
        assert is_valid is False
        assert "common" in msg.lower()


class TestAuthManager:
    """Test cases for AuthManager class"""

    def test_generate_token(self):
        from auth import AuthManager

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            token = am.generate_token("admin")
            assert isinstance(token, str)
            assert len(token) > 20

    def test_verify_valid_token(self):
        from auth import AuthManager

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            token = am.generate_token("admin")
            is_valid, result = am.verify_token(token)
            assert is_valid is True
            assert result["sub"] == "admin"

    def test_verify_expired_token(self):
        from auth import AuthManager

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            token = am.generate_token("admin", expires_in=-1)
            is_valid, result = am.verify_token(token)
            assert is_valid is False
            assert "expired" in result.get("error", "").lower()

    def test_verify_invalid_token(self):
        from auth import AuthManager

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            is_valid, result = am.verify_token("invalid.token.here")
            assert is_valid is False

    def test_generate_csrf_token(self):
        from auth import AuthManager

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            with patch("auth.session", {}):
                token = am.generate_csrf_token()
                assert isinstance(token, str)
                assert len(token) == 64  # hex of 32 bytes

    def test_auth_manager_delegates_hash_password(self):
        """Test that AuthManager.hash_password delegates to PasswordSecurity"""
        from auth import AuthManager, PasswordSecurity

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            result = am.hash_password("test_password_123")
            assert result.startswith(("pbkdf2:", "scrypt:", "bcrypt:"))

    def test_auth_manager_delegates_verify_password(self):
        """Test that AuthManager.verify_password delegates to PasswordSecurity"""
        from auth import AuthManager

        with patch("auth.settings") as mock_settings:
            mock_settings.secret_key = "test-secret-key-for-testing-only"
            mock_settings.session_timeout = 3600
            am = AuthManager()
            hashed = am.hash_password("test_password_123")
            assert am.verify_password("test_password_123", hashed) is True
            assert am.verify_password("wrong_password", hashed) is False
