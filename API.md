# Screen Recorder API Documentation

## Overview

The Screen Recorder Server provides a RESTful API for video uploads, license management, and client communication.

**Base URL:** `http://your-server:5000`

**API Version:** v1

---

## Authentication

### License-Based Authentication

Most API endpoints require a valid license key. Include the license in requests using one of these methods:

**Header (Preferred):**

```
X-License-Key: <your-license-key>
X-Machine-ID: <your-machine-id>
```

**Form Data:**

```
license: <your-license-key>
machine_id: <your-machine-id>
```

---

## API Endpoints

### Health Check

```http
GET /api/v1/health
```

Check server health status.

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0"
}
```

---

### Upload Video

```http
POST /api/v1/upload
```

Upload a recorded video to the server.

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| X-License-Key | Yes | Valid license key |
| X-Machine-ID | Yes | Client machine ID |

**Form Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| video | File | Yes | Video file (mp4, avi, mov, mkv) |
| timestamp | String | No | ISO 8601 timestamp of recording |

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Video uploaded successfully",
  "filename": "20240115_103000_rec_2024.mp4",
  "video_id": 123
}
```

**Error Responses:**

- `400 Bad Request` - Invalid file or missing data
- `401 Unauthorized` - Invalid or expired license
- `413 Payload Too Large` - File exceeds size limit (500MB)
- `429 Too Many Requests` - Rate limit exceeded

---

### Validate License

```http
POST /api/v1/validate-license
```

Validate a license key.

**Request Body:**

```json
{
  "license": "<license-key>",
  "machine_id": "<machine-id>"
}
```

**Response (Valid):**

```json
{
  "valid": true,
  "data": {
    "machine_id": "abc123...",
    "issued_at": "2024-01-01T00:00:00.000Z",
    "expires_at": "2025-01-01T00:00:00.000Z",
    "features": {
      "recording": true,
      "upload": true
    }
  },
  "error": null
}
```

**Response (Invalid):**

```json
{
  "valid": false,
  "data": null,
  "error": "License has expired"
}
```

---

### Heartbeat

```http
POST /api/v1/heartbeat
```

Send a heartbeat to indicate client is active.

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| X-License-Key | Yes | Valid license key |
| X-Machine-ID | Yes | Client machine ID |

**Response:**

```json
{
  "success": true,
  "message": "Heartbeat received",
  "server_time": "2024-01-15T10:30:00.000Z"
}
```

---

### Get Machine ID

```http
GET /api/v1/get-machine-id
```

Get the machine ID for the requesting client.

**Response:**

```json
{
  "machine_id": "abc123def456..."
}
```

---

### Get Public Key

```http
GET /api/v1/get-public-key
```

Get the server's public key for license validation.

**Response:**

```json
{
  "public_key": "-----BEGIN PUBLIC KEY-----\n..."
}
```

---

## Admin API

Admin endpoints require session-based authentication.

### Admin Login

```http
POST /admin/login
```

**Form Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| password | String | Yes | Admin password |

**Response:** Redirects to admin dashboard on success.

---

### Generate License (Admin)

```http
POST /admin/generate-license
```

**Form Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| machine_id | String | Yes | Target machine ID |
| expiry_days | Integer | No | Days until expiration (default: 365) |
| features | List | No | Enabled features |

**Response:** Renders license result page with generated license key.

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "Error type",
  "details": "Detailed error message"
}
```

### HTTP Status Codes

| Code | Description                             |
| ---- | --------------------------------------- |
| 200  | Success                                 |
| 400  | Bad Request - Invalid input             |
| 401  | Unauthorized - Invalid/expired license  |
| 403  | Forbidden - CSRF token invalid          |
| 404  | Not Found                               |
| 429  | Too Many Requests - Rate limit exceeded |
| 500  | Internal Server Error                   |

---

## Rate Limiting

API endpoints have rate limits to prevent abuse:

| Endpoint          | Limit       | Window     |
| ----------------- | ----------- | ---------- |
| /upload           | 30 requests | 60 seconds |
| /validate-license | 10 requests | 60 seconds |
| /heartbeat        | 60 requests | 60 seconds |

When rate limited, the API returns `429 Too Many Requests`.

---

## File Upload Limits

- **Maximum file size:** 500 MB
- **Allowed extensions:** mp4, avi, mov, mkv

---

## Legacy API

For backward compatibility, legacy endpoints are available without version prefix:

- `POST /api/upload` → `POST /api/v1/upload`
- `POST /api/validate-license` → `POST /api/v1/validate-license`
- `GET /api/get-machine-id` → `GET /api/v1/get-machine-id`
- `GET /api/get-public-key` → `GET /api/v1/get-public-key`

---

## Client Implementation Example

```python
import requests

# Configuration
SERVER_URL = "http://your-server:5000"
LICENSE_KEY = "your-license-key"
MACHINE_ID = "your-machine-id"

# Upload video
def upload_video(video_path):
    url = f"{SERVER_URL}/api/v1/upload"
    headers = {
        "X-License-Key": LICENSE_KEY,
        "X-Machine-ID": MACHINE_ID
    }

    with open(video_path, "rb") as f:
        files = {"video": (video_path.name, f, "video/mp4")}
        data = {"timestamp": datetime.utcnow().isoformat()}

        response = requests.post(url, files=files, data=data, headers=headers)

    return response.json()

# Send heartbeat
def send_heartbeat():
    url = f"{SERVER_URL}/api/v1/heartbeat"
    headers = {
        "X-License-Key": LICENSE_KEY,
        "X-Machine-ID": MACHINE_ID,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json={})
    return response.json()
```

---

## WebSocket Support (Future)

Planned WebSocket support for real-time notifications:

```
ws://your-server:5000/ws
```

Events:

- `client_connected` - New client connected
- `video_uploaded` - Video upload completed
- `license_expired` - License expiration warning
  </task_progress>
- [x] Security fixes
  - [x] Add proper authentication with JWT
  - [x] Add CSRF protection
  - [x] Add rate limiting
  - [x] Secure license key transmission
- [x] Code quality improvements
  - [x] Fix bare except clauses
  - [x] Add input validation
  - [x] Add type hints throughout
- [x] Architecture improvements
  - [x] Add database support with SQLAlchemy
  - [x] Restructure server code with blueprints
  - [x] Add API versioning
- [x] Add unit tests
- [x] Add API documentation
- [x] Client improvements
  - [x] Add retry logic
  - [x] Add offline queue
  - [x] Add heartbeat
        </task_progress>
        </write_to_file>
