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

Or alternatively:

```
X-License-Token: <your-license-key>
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

| Header          | Required | Description                    |
| --------------- | -------- | ------------------------------ |
| X-License-Key   | Yes\*    | Valid license key              |
| X-License-Token | Yes\*    | Alternative license key header |
| X-Machine-ID    | Yes      | Client machine ID              |

\*Either X-License-Key or X-License-Token is required

**Form Data:**

| Field     | Type   | Required | Description                     |
| --------- | ------ | -------- | ------------------------------- |
| video     | File   | Yes      | Video file (mp4, avi, mov, mkv) |
| timestamp | String | No       | ISO 8601 timestamp of recording |

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

| Header          | Required | Description                    |
| --------------- | -------- | ------------------------------ |
| X-License-Key   | Yes\*    | Valid license key              |
| X-License-Token | Yes\*    | Alternative license key header |
| X-Machine-ID    | Yes      | Client machine ID              |

\*Either X-License-Key or X-License-Token is required

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

## Video Streaming Endpoints

### Stream Video

```http
GET /api/v1/stream/<machine_id>/<filename>
```

Stream a video file with HTTP Range support for partial content.

**Parameters:**

| Parameter  | Type   | Description       |
| ---------- | ------ | ----------------- |
| machine_id | String | Client machine ID |
| filename   | String | Video filename    |

**Headers (Optional):**

| Header | Description                                           |
| ------ | ----------------------------------------------------- |
| Range  | Byte range for partial content (e.g., `bytes=0-1023`) |

**Response:**

- `200 OK` - Full video stream
- `206 Partial Content` - Partial video stream (when Range header is provided)
- `404 Not Found` - Video not found

**Response Headers:**

| Header         | Description                      |
| -------------- | -------------------------------- |
| Content-Type   | video/mp4                        |
| Content-Length | File size in bytes               |
| Accept-Ranges  | bytes                            |
| Content-Range  | Byte range (for partial content) |

**Example:**

```bash
# Stream full video
curl http://server:5000/api/v1/stream/abc123/video.mp4 -o video.mp4

# Stream partial video (for seeking)
curl -H "Range: bytes=0-1023" http://server:5000/api/v1/stream/abc123/video.mp4
```

---

### Get Video Thumbnail

```http
GET /api/v1/thumbnail/<machine_id>/<filename>
```

Get or generate a thumbnail for a video.

**Parameters:**

| Parameter  | Type   | Description       |
| ---------- | ------ | ----------------- |
| machine_id | String | Client machine ID |
| filename   | String | Video filename    |

**Response:**

- `200 OK` - JPEG thumbnail image
- `404 Not Found` - Video or thumbnail not available

**Response Headers:**

| Header       | Description |
| ------------ | ----------- |
| Content-Type | image/jpeg  |

**Notes:**

- Thumbnails are generated at 10% of video duration by default
- Default thumbnail size is 320x240 pixels
- Generated thumbnails are cached for future requests

---

### Get Video Info

```http
GET /api/v1/video-info/<machine_id>/<filename>
```

Get detailed information about a video file.

**Parameters:**

| Parameter  | Type   | Description       |
| ---------- | ------ | ----------------- |
| machine_id | String | Client machine ID |
| filename   | String | Video filename    |

**Response:**

```json
{
  "exists": true,
  "size": 10485760,
  "duration": 60.5,
  "width": 1920,
  "height": 1080,
  "fps": 30.0
}
```

**Fields:**

| Field    | Type    | Description                   |
| -------- | ------- | ----------------------------- |
| exists   | Boolean | Whether the video file exists |
| size     | Integer | File size in bytes            |
| duration | Float   | Video duration in seconds     |
| width    | Integer | Video width in pixels         |
| height   | Integer | Video height in pixels        |
| fps      | Float   | Frames per second             |

---

## Admin API

Admin endpoints require session-based authentication.

### Admin Login

```http
POST /admin/login
```

**Form Data:**

| Field    | Type   | Required | Description    |
| -------- | ------ | -------- | -------------- |
| password | String | Yes      | Admin password |

**Response:** Redirects to admin dashboard on success.

---

### Generate License (Admin)

```http
POST /admin/generate-license
```

**Form Data:**

| Field       | Type    | Required | Description                          |
| ----------- | ------- | -------- | ------------------------------------ |
| machine_id  | String  | Yes      | Target machine ID                    |
| expiry_days | Integer | No       | Days until expiration (default: 365) |
| features    | List    | No       | Enabled features                     |

**Response:** Renders license result page with generated license key.

---

## WebSocket Events

WebSocket support is available when `flask-socketio` is installed.

### Connection

```javascript
// Connect to WebSocket
const socket = io("http://your-server:5000");

// Register as admin
socket.emit("register_admin");

// Register as client
socket.emit("register_client", { machine_id: "your-machine-id" });
```

### Client Events

| Event             | Direction     | Description                  |
| ----------------- | ------------- | ---------------------------- |
| register_client   | Client→Server | Register as recording client |
| client_status     | Client→Server | Send status update           |
| recording_started | Client→Server | Notify recording started     |
| recording_stopped | Client→Server | Notify recording stopped     |
| video_uploaded    | Client→Server | Notify video upload complete |
| error_report      | Client→Server | Report an error              |

### Server Events (Admin)

| Event            | Description               |
| ---------------- | ------------------------- |
| client_list      | List of connected clients |
| client_status    | Client status update      |
| client_heartbeat | Client heartbeat received |
| video_uploaded   | Video upload notification |
| client_error     | Client error report       |

### Example Usage

```javascript
// Admin dashboard example
const socket = io("http://your-server:5000");

socket.on("connect", () => {
  socket.emit("register_admin");
});

socket.on("client_status", (data) => {
  console.log(`Client ${data.machine_id}: ${data.status}`);
});

socket.on("video_uploaded", (data) => {
  console.log(`Video uploaded: ${data.filename} from ${data.machine_id}`);
});
```

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
| 206  | Partial Content (video streaming)       |
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

# Stream video
def stream_video(machine_id, filename, output_path):
    url = f"{SERVER_URL}/api/v1/stream/{machine_id}/{filename}"

    response = requests.get(url, stream=True)

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path

# Get video info
def get_video_info(machine_id, filename):
    url = f"{SERVER_URL}/api/v1/video-info/{machine_id}/{filename}"
    response = requests.get(url)
    return response.json()
```

---

## Video Streaming with HTML5

```html
<video controls>
  <source
    src="http://server:5000/api/v1/stream/abc123/video.mp4"
    type="video/mp4"
  />
  Your browser does not support the video tag.
</video>
```

The streaming endpoint supports HTTP Range requests, enabling:

- Video seeking
- Partial content delivery
- Efficient bandwidth usage

---

## Recent Improvements

### Custom Exceptions

The API now uses a comprehensive exception hierarchy for better error handling:

```python
from shared.exceptions import (
    LicenseError,
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMachineMismatchError,
    UploadError,
    UploadFailedError,
    UploadSizeExceededError,
    RecordingError,
    RecordingStartError,
    RecordingStopError,
)
```

### Security Enhancements

- **Timing Attack Protection**: Password validation uses constant-time comparison
- **User Enumeration Prevention**: Generic error messages prevent user enumeration
- **Rate Limiting**: All endpoints protected against abuse

### Testing

Unit tests are available for critical modules:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=shared --cov=server

# Run specific tests
pytest tests/test_license_manager.py
pytest tests/test_validators.py
```

### Docker Support

The server can be deployed using Docker:

```bash
# Build and start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f server

# Stop services
docker-compose down
```

See [README.md](README.md) for detailed Docker deployment instructions.
