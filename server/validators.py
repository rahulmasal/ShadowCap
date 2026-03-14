"""
Input validation utilities for the Screen Recorder Server
"""

import re
from typing import Tuple, Optional
from pathlib import Path


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class InputValidator:
    """Input validation utilities"""

    # Regex patterns
    MACHINE_ID_PATTERN = re.compile(r'^[a-fA-F0-9]{32,64}$')
    LICENSE_KEY_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{100,2000}$')  # Base64 encoded
    FILENAME_PATTERN = re.compile(r'^[\w\-. ]+$')
    SAFE_PATH_PATTERN = re.compile(r'^[\w\-./\\]+$')

    @staticmethod
    def validate_machine_id(machine_id: str) -> Tuple[bool, Optional[str]]:
        """Validate a machine ID"""
        if not machine_id:
            return False, "Machine ID is required"
        
        if not isinstance(machine_id, str):
            return False, "Machine ID must be a string"
        
        if len(machine_id) < 32 or len(machine_id) > 64:
            return False, "Machine ID must be between 32 and 64 characters"
        
        if not InputValidator.MACHINE_ID_PATTERN.match(machine_id):
            return False, "Machine ID must be a valid hexadecimal string"
        
        return True, None

    @staticmethod
    def validate_license_key(license_key: str) -> Tuple[bool, Optional[str]]:
        """Validate a license key format"""
        if not license_key:
            return False, "License key is required"
        
        if not isinstance(license_key, str):
            return False, "License key must be a string"
        
        if len(license_key) < 100:
            return False, "License key is too short"
        
        if len(license_key) > 2000:
            return False, "License key is too long"
        
        # Check if it's valid base64
        try:
            import base64
            base64.b64decode(license_key)
        except Exception:
            return False, "License key must be valid base64 encoded"
        
        return True, None

    @staticmethod
    def validate_filename(filename: str, max_length: int = 255) -> Tuple[bool, Optional[str]]:
        """Validate a filename"""
        if not filename:
            return False, "Filename is required"
        
        if not isinstance(filename, str):
            return False, "Filename must be a string"
        
        if len(filename) > max_length:
            return False, f"Filename must be less than {max_length} characters"
        
        # Check for path traversal
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            return False, "Invalid filename: path traversal detected"
        
        # Check for valid characters
        if not InputValidator.FILENAME_PATTERN.match(filename):
            return False, "Filename contains invalid characters"
        
        return True, None

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: set) -> Tuple[bool, Optional[str]]:
        """Validate file extension"""
        if '.' not in filename:
            return False, "Filename must have an extension"
        
        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in allowed_extensions:
            return False, f"File extension '{ext}' is not allowed. Allowed: {', '.join(allowed_extensions)}"
        
        return True, None

    @staticmethod
    def validate_path(path: str, base_dir: Path = None) -> Tuple[bool, Optional[str]]:
        """Validate a file path for security"""
        if not path:
            return False, "Path is required"
        
        if not isinstance(path, str):
            return False, "Path must be a string"
        
        # Check for path traversal
        if '..' in path:
            return False, "Path traversal detected"
        
        # If base_dir provided, ensure path is within it
        if base_dir:
            try:
                resolved_path = (base_dir / path).resolve()
                if not str(resolved_path).startswith(str(base_dir.resolve())):
                    return False, "Path is outside allowed directory"
            except Exception as e:
                return False, f"Invalid path: {str(e)}"
        
        return True, None

    @staticmethod
    def validate_expiry_days(expiry_days: int) -> Tuple[bool, Optional[str]]:
        """Validate expiry days"""
        if not isinstance(expiry_days, int):
            try:
                expiry_days = int(expiry_days)
            except (ValueError, TypeError):
                return False, "Expiry days must be an integer"
        
        if expiry_days < 1:
            return False, "Expiry days must be at least 1"
        
        if expiry_days > 3650:  # Max 10 years
            return False, "Expiry days cannot exceed 3650 (10 years)"
        
        return True, None

    @staticmethod
    def validate_features(features: dict) -> Tuple[bool, Optional[str]]:
        """Validate license features"""
        if not isinstance(features, dict):
            return False, "Features must be a dictionary"
        
        allowed_features = {'recording', 'upload', 'streaming', 'download'}
        
        for key in features.keys():
            if key not in allowed_features:
                return False, f"Unknown feature: {key}. Allowed: {', '.join(allowed_features)}"
            
            if not isinstance(features[key], bool):
                return False, f"Feature '{key}' must be a boolean"
        
        return True, None

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize a string input"""
        if not value:
            return ""
        
        # Strip whitespace
        value = str(value).strip()
        
        # Truncate to max length
        if len(value) > max_length:
            value = value[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        return value

    @staticmethod
    def validate_json_size(data: dict, max_size_kb: int = 100) -> Tuple[bool, Optional[str]]:
        """Validate JSON data size"""
        import json
        
        try:
            json_str = json.dumps(data)
            size_kb = len(json_str.encode('utf-8')) / 1024
            
            if size_kb > max_size_kb:
                return False, f"JSON data too large: {size_kb:.2f}KB (max: {max_size_kb}KB)"
            
            return True, None
        except Exception as e:
            return False, f"Invalid JSON: {str(e)}"


def validate_request_data(data: dict, required_fields: list, optional_fields: list = None) -> Tuple[bool, Optional[str]]:
    """Validate request data has required fields"""
    if not isinstance(data, dict):
        return False, "Request data must be a JSON object"
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
        
        if data[field] is None or data[field] == '':
            return False, f"Field '{field}' cannot be empty"
    
    # Check for unknown fields
    if optional_fields is not None:
        all_fields = set(required_fields) | set(optional_fields)
        unknown_fields = set(data.keys()) - all_fields
        if unknown_fields:
            return False, f"Unknown fields: {', '.join(unknown_fields)}"
    
    return True, None
</task_progress>
- [ ] Security fixes
  - [x] Add proper authentication with JWT
  - [x] Add CSRF protection
  - [x] Add rate limiting
  - [ ] Secure license key transmission
- [ ] Code quality improvements
  - [x] Fix bare except clauses
  - [x] Add input validation
  - [ ] Add type hints
- [ ] Architecture improvements
  - [x] Add database support with SQLAlchemy
  - [ ] Restructure server code
  - [ ] Add API versioning
- [ ] Add unit tests
- [ ] Add Docker support
- [ ] Add API documentation
- [ ] Client improvements
  - [ ] Add retry logic
  - [ ] Add offline queue
  - [ ] Add heartbeat
</task_progress>
</write_to_file>