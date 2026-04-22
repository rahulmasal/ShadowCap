# ShadowCap - Complete Workflow

## How the System Works

### Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐                 ┌──────────────────────────────┐
│       CLIENT PC              │                 │       SERVER PC              │
│                              │                 │                              │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   1. ShadowCap Client  │  │                 │  │   1. Flask Server      │  │
│  │      (Hidden)          │  │                 │  │      (app.py)          │  │
│  │                        │  │                 │  │                        │  │
│  │  • Captures screen     │  │                 │  │  • Receives videos     │  │
│  │  • Multi-monitor       │  │                 │  │  • Validates licenses  │  │
│  │  • Region selection    │  │                 │  │  • Serves dashboard    │  │
│  │  • Audio recording     │  │                 │  │  • Video streaming     │  │
│  │  • Pause/Resume        │  │                 │  │  • Thumbnails          │  │
│  │  • Video compression   │  │                 │  │  • WebSocket support   │  │
│  │  • Offline queue       │  │                 │  │  • Rate limiting       │  │
│  │  • Heartbeat           │  │                 │  │  • CSRF protection     │  │
│  │  • Retry logic         │  │                 │  │                        │  │
│  └──────────┬─────────────┘  │                 │  └──────────┬─────────────┘  │
│             │                │                 │             │                │
│             ▼                │                 │             ▼                │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   2. Local Storage     │  │   HTTP POST     │  │   2. Database          │  │
│  │   %APPDATA%/           │  │  ──────────────►│  │   (SQLite)             │  │
│  │   ScreenRecSvc/        │  │                 │  │                        │  │
│  │   recordings/          │  │                 │  │   • Clients            │  │
│  │   offline_queue/       │  │                 │  │   • Licenses           │  │
│  │   thumbnails/          │  │                 │  │   • Videos             │  │
│  │   • rec_001.mp4        │  │                 │  │   • AuditLogs          │  │
│  │   • rec_002.mp4        │  │                 │  │                        │  │
│  └────────────────────────┘  │                 │  └────────────────────────┘  │
│                              │                 │                              │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   3. License File      │  │                 │  │   3. Upload Storage    │  │
│  │   license.key          │  │                 │  │   server/uploads/      │  │
│  │   (Validates client)   │  │                 │  │   {machine_id}/        │  │
│  └────────────────────────┘  │                 │  │   thumbnails/          │  │
│                              │                 │  └────────────────────────┘  │
│                              │                 │                              │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   4. Heartbeat Thread  │  │                 │  │   4. Admin Dashboard   │  │
│  │   (Monitors server)    │  │◄────────────────│  │   <http://server:5000>   │  │
│  └────────────────────────┘  │   Heartbeat OK  │  │   /admin               │  │
│                              │                 │  │                        │  │
│                              │                 │  │   • View all clients   │  │
│                              │                 │  │   • Generate licenses  │  │
│                              │                 │  │   • Stream videos      │  │
│                              │                 │  │   • View thumbnails    │  │
│                              │                 │  │   • Real-time status   │  │
│                              │                 │  └────────────────────────┘  │
└──────────────────────────────┘                 └──────────────────────────────┘
```

---

## Step-by-Step Flow

### PHASE 1: Server Setup (One-time)

```
Step 1: Start the Server
────────────────────────
$ cd ShadowCap
$ start_server.bat

This will:
├── Create virtual environment
├── Install dependencies (Flask, SQLAlchemy, cryptography, etc.)
├── Generate RSA key pair (private_key.pem, public_key.pem)
│   └── Keys stored in: server/keys/
├── Initialize SQLite database
│   └── Tables: clients, licenses, videos, audit_logs
├── Create directories:
│   ├── uploads/     (for video storage)
│   ├── thumbnails/  (for video thumbnails)
│   ├── licenses/    (for license storage)
│   └── keys/        (for RSA keys)
└── Start Flask server on port 5000

Access Admin Dashboard:
URL: <http://localhost:5000/admin>
Password: (set in .env file as ADMIN_PASSWORD)
```

### PHASE 2: Client Setup

```
Step 2: Get Machine ID from Client PC
──────────────────────────────────────
$ python get_machine_id.py

Output:
Your Machine ID: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

Copy this ID - you'll need it to generate a license.
```

```
Step 3: Generate License (on Server Dashboard)
──────────────────────────────────────────────
1. Go to: <http://server-ip:5000/admin>
2. Login with admin password
3. Click "Generate License"
4. Enter Machine ID from client
5. Set expiry days (e.g., 365)
6. Select features (Recording, Upload)
7. Click "Generate"

Output: License key string (RSA-2048 signed)

Save this as "license.key" file on client PC.
```

```
Step 4: Configure Client
────────────────────────
Create config.json on client:

{
    "server_url": "<http://YOUR_SERVER_IP:5000",>
    "upload_interval": 300,
    "recording_fps": 10,
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
    "enable_audio": false,
    "enable_compression": true,
    "use_websocket": false
}
```

### PHASE 3: Recording & Upload

```
Step 5: Client Recording Process
─────────────────────────────────

When client starts (screen_recorder.py):

1. INITIALIZATION PHASE
   ├── Load configuration from config.json
   ├── Initialize logging to %APPDATA%/ScreenRecSvc/
   ├── Initialize offline queue manager
   ├── Initialize retry handler
   ├── Initialize monitor manager (detect monitors)
   └── Initialize audio recorder (if enabled)

2. VALIDATION PHASE
   ├── Load license.key from disk
   ├── Load public_key.pem (embedded in exe)
   ├── Validate license signature (RSA-2048)
   ├── Check license expiration date
   ├── Verify machine ID matches
   └── If invalid → Exit silently

3. MONITOR DETECTION PHASE
   ├── Detect all connected monitors
   ├── Validate monitor_selection config
   ├── Get capture region dimensions
   │   ├── Apply region_x, region_y offsets
   │   ├── Apply region_width, region_height
   │   └── Validate bounds within monitor
   └── Log capture configuration

4. RECORDING PHASE (if license valid)
   ├── Initialize screen capture (mss library)
   ├── Get monitor resolution
   ├── Create video writer (OpenCV)
   │   └── Format: MP4 (mp4v codec)
   ├── Start recording loop:
   │   ├── Check pause state
   │   │   └── If paused → Wait, track paused time
   │   ├── Capture screen frame from selected monitor
   │   ├── Convert BGRA → BGR
   │   ├── Write frame to video
   │   ├── Check chunk duration
   │   │   └── If chunk complete → Save & start new
   │   └── Sleep (1/fps seconds)
   └── Continue until stopped

5. AUDIO RECORDING PHASE (if enabled)
   ├── Initialize PyAudio
   ├── Open audio stream
   │   └── Sample rate: 44100 Hz, Channels: 2
   ├── Record audio in separate thread
   ├── On chunk complete:
   │   ├── Save audio to WAV file
   │   └── Merge with video (optional)
   └── Continue until stopped

6. HEARTBEAT PHASE (background thread)
   ├── Every 60 seconds (configurable)
   ├── POST to: <http://server:5000/api/v1/heartbeat>
   ├── Include: license key, machine ID
   ├── Update server_reachable flag
   └── Log connection status

7. STORAGE PHASE
   ├── Save videos to: %APPDATA%/ScreenRecSvc/recordings/
   │   ├── rec_20260312_210000_a1b2c3d4.mp4
   │   ├── rec_20260312_210100_a1b2c3d4.mp4
   │   └── ...
   ├── Save thumbnails to: %APPDATA%/ScreenRecSvc/thumbnails/
   └── Videos stored locally before upload

8. UPLOAD PHASE (background thread)
   ├── Every 5 minutes (configurable)
   ├── First, process offline queue:
   │   ├── Get next pending video
   │   ├── Attempt upload with retry
   │   └── On success → Remove from queue
   ├── Then, upload current chunks:
   │   ├── POST to: <http://server:5000/api/v1/upload>
   │   ├── Headers: X-License-Key, X-Machine-ID
   │   └── Server validates & saves
   ├── On success → Delete local copy
   └── On failure → Add to offline queue

9. RETRY LOGIC
   ├── Exponential backoff with jitter
   ├── Base delay: 1 second
   ├── Max delay: 300 seconds (5 minutes)
   ├── Max retries: 5
   └── Retryable errors:
       ├── ConnectionError
       ├── Timeout
       └── HTTP 5xx errors

10. VIDEO COMPRESSION (if enabled)
    ├── Check for FFmpeg availability
    ├── Compress video with CRF quality
    │   └── Default CRF: 23 (configurable)
    ├── Fallback to OpenCV if FFmpeg unavailable
    └── Save compressed video for upload
```

### PHASE 4: Server Processing

```
Step 6: Server Request Processing
─────────────────────────────────

When server receives a request:

1. RATE LIMITING CHECK
   ├── Check client IP against rate limits
   ├── Upload: 30 requests per 60 seconds
   ├── Validate-license: 10 requests per 60 seconds
   ├── Heartbeat: 60 requests per 60 seconds
   └── If exceeded → Return 429 Too Many Requests

2. AUTHENTICATION
   ├── Extract X-License-Key header
   ├── Extract X-Machine-ID header
   ├── Load public key from keys/public_key.pem
   ├── Validate license signature
   ├── Check expiration
   └── Verify machine ID matches

3. INPUT VALIDATION
   ├── Validate filename (no path traversal)
   ├── Validate file extension (mp4, avi, mov, mkv)
   ├── Validate file size (max 500MB)
   └── Validate machine ID format

4. PROCESSING
   ├── Save video to uploads/{machine_id}/
   ├── Create database record
   ├── Generate thumbnail (async)
   │   ├── Extract frame at 10% duration
   │   ├── Resize to 320x240
   │   └── Save as JPEG
   ├── Log audit entry
   └── Return success response
```

### PHASE 5: Server Storage

```
Step 7: Server Video Storage
────────────────────────────

Videos stored on server at:
server/uploads/{machine_id}/

Thumbnails stored at:
server/uploads/thumbnails/

Database (SQLite):
├── clients
│   ├── id, machine_id, last_seen, is_active
│   └── created_at, updated_at
├── licenses
│   ├── id, machine_id, license_key
│   ├── expires_at, is_active, features
│   └── created_at, updated_at
├── videos
│   ├── id, filename, original_filename
│   ├── file_path, file_size, client_id
│   ├── upload_time, client_timestamp
│   └── created_at
└── audit_logs
    ├── id, action, entity_type, entity_id
    ├── details, ip_address, user_agent
    └── created_at

Example structure:
uploads/
├── a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6/
│   ├── 20260312_210000_rec_001.mp4
│   ├── 20260312_210500_rec_002.mp4
│   └── ...
├── thumbnails/
│   ├── 20260312_210000_rec_001_thumb.jpg
│   └── ...
└── ...
```

---

## New Features Workflow

### Multi-Monitor Recording

```
Monitor Selection Process:
─────────────────────────

1. Client starts
2. Monitor Manager initializes
3. Detect all connected monitors:
   ├── Monitor 0: Virtual (all monitors combined)
   ├── Monitor 1: Primary (1920x1080)
   ├── Monitor 2: Secondary (2560x1440)
   └── ...
4. Read monitor_selection from config
5. Validate selection:
   ├── If valid → Use selected monitor
   └── If invalid → Fall back to primary (1)
6. Apply region settings:
   ├── region_x, region_y: Offset from top-left
   ├── region_width, region_height: Capture dimensions
   └── If 0 → Use full monitor dimensions
7. Start capture from selected region
```

### Pause/Resume Recording

```
Pause/Resume Flow:
──────────────────

1. Recording active (state: RECORDING)
2. User/API requests pause
3. Set _pause_event
4. State changes to PAUSED
5. Recording thread:
   ├── Detects pause event
   ├── Stops capturing frames
   └── Waits in loop (100ms intervals)
6. User/API requests resume
7. Clear _pause_event
8. State changes to RECORDING
9. Recording thread:
   ├── Detects resume
   ├── Logs paused duration
   └── Resumes frame capture
```

### Video Streaming

```
Video Streaming Flow:
─────────────────────

1. Client requests: GET /api/v1/stream/{machine_id}/{filename}
2. Server validates machine_id and filename
3. Check if video exists
4. Parse Range header (if present)
5. If Range header:
   ├── Extract start, end bytes
   ├── Seek to start position
   ├── Stream requested range
   └── Return 206 Partial Content
6. If no Range header:
   ├── Stream entire file
   └── Return 200 OK
7. Response includes:
   ├── Content-Type: video/mp4
   ├── Accept-Ranges: bytes
   ├── Content-Length: file/range size
   └── Content-Range: bytes start-end/total
```

### Thumbnail Generation

```
Thumbnail Generation Flow:
──────────────────────────

1. Video uploaded to server
2. Thumbnail request received
3. Check for existing thumbnail
4. If exists → Return cached thumbnail
5. If not exists:
   ├── Initialize VideoProcessor
   ├── Check FFmpeg availability
   ├── If FFmpeg available:
   │   ├── Get video duration
   │   ├── Calculate timestamp (10% of duration)
   │   ├── Extract frame at timestamp
   │   └── Resize to 320x240
   ├── Else (OpenCV fallback):
   │   ├── Open video with cv2.VideoCapture
   │   ├── Seek to target frame
   │   ├── Read frame
   │   └── Resize
   ├── Save as JPEG
   └── Return thumbnail
```

### Graceful Shutdown

```
Graceful Shutdown Flow:
───────────────────────

When client receives shutdown signal (SIGINT, SIGTERM, SIGHUP):

1. SIGNAL HANDLING
   ├── Signal handler registered in __init__
   ├── SIGINT (Ctrl+C)
   ├── SIGTERM (service stop)
   └── SIGHUP (terminal close)

2. SHUTDOWN SEQUENCE
   ├── Set _running = False
   ├── Set _upload_running = False
   ├── Stop recording:
   │   ├── Set _recording = False
   │   ├── Wait for recording thread (timeout: 5s)
   │   ├── Save current video chunk
   │   └── Close video writer
   ├── Stop heartbeat:
   │   ├── Set _heartbeat_running = False
   │   └── Wait for heartbeat thread (timeout: 5s)
   ├── Stop upload:
   │   ├── Set _upload_running = False
   │   └── Wait for upload thread (timeout: 5s)
   └── Log shutdown completion

3. RESPONSIVE SHUTDOWN
   ├── Main loop increments in 0.1s steps
   ├── Checks _running flag frequently
   ├── Responds to signals within 0.1s
   └── Ensures no data loss during shutdown
```

### Custom Exceptions

```
Exception Hierarchy:
────────────────────

ScreenRecorderError (Base)
├── LicenseError
│   ├── LicenseExpiredError
│   ├── LicenseInvalidError
│   └── LicenseMachineMismatchError
├── UploadError
│   ├── UploadFailedError
│   └── UploadSizeExceededError
├── SessionError
│   ├── SessionZeroError
│   └── SessionRelaunchError
├── RecordingError
│   ├── RecordingStartError
│   ├── RecordingStopError
│   └── VideoWriterError
├── AudioError
├── ConfigurationError
├── NetworkError
├── DatabaseError
├── ValidationError
├── CompressionError
└── MonitorError

Usage Example:
─────────────
try:
    validate_license(license_key)
except LicenseExpiredError as e:
    log.error(f"License expired: {e}")
    handle_expiry()
except LicenseInvalidError as e:
    log.error(f"Invalid license: {e}")
    handle_invalid()
except LicenseMachineMismatchError as e:
    log.error(f"Machine mismatch: {e}")
    handle_mismatch()
```

### Security Enhancements

```
Timing Attack Protection:
─────────────────────────

Before (Vulnerable):
├── Password comparison with == operator
├── Different response times for:
│   ├── Wrong first character: ~1ms
│   ├── Wrong last character: ~10ms
│   └── Correct password: ~50ms
└── Attacker can determine password character by character

After (Secure):
├── Uses werkzeug.security.check_password_hash
├── Constant-time comparison
├── Same response time regardless of:
│   ├── How many characters match
│   ├── Which characters match
│   └── Whether password is correct
└── Prevents timing-based attacks

Code Change:
────────────
# Before (vulnerable)
if password == stored_hash:
    return True

# After (secure)
from werkzeug.security import check_password_hash
if check_password_hash(stored_hash, password):
    return True
```

### Testing Infrastructure

```
Test Structure:
───────────────

tests/
├── __init__.py
├── conftest.py              # Pytest configuration
├── test_license_manager.py  # License tests
└── test_validators.py       # Validator tests

Running Tests:
──────────────
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_license_manager.py

# Run with coverage
pytest --cov=shared --cov=server

Test Fixtures:
──────────────
project_root_path    # Project root directory
temp_dir            # Temporary directory
temp_file           # Temporary file
test_machine_id     # Test machine ID
test_license_key    # Test license key
mock_config         # Mock configuration

Test Markers:
─────────────
@pytest.mark.screen_capture  # Screen capture tests
@pytest.mark.audio          # Audio tests
@pytest.mark.network        # Network tests
@pytest.mark.slow           # Slow tests
```

### Docker Deployment

```
Docker Architecture:
────────────────────

docker-compose.yml
├── server service
│   ├── Build from server/Dockerfile
│   ├── Port mapping: 5000:5000
│   ├── Volume mounts:
│   │   ├── ./server/data:/app/data
│   │   ├── ./server/uploads:/app/uploads
│   │   ├── ./server/licenses:/app/licenses
│   │   └── ./server/keys:/app/keys
│   └── Environment variables:
│       ├── SECRET_KEY
│       ├── ADMIN_PASSWORD
│       └── DATABASE_URL
└── nginx service (optional)
    ├── Port mapping: 80:80, 443:443
    └── Config: nginx.conf

Dockerfile Features:
────────────────────
├── Multi-stage build
├── Non-root user for security
├── Health check endpoint
├── Minimal image size
└── Production-ready

Docker Commands:
────────────────
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f server

# Stop services
docker-compose down

# Restart
docker-compose restart

# Check status
docker-compose ps

# Rebuild after changes
docker-compose up -d --build
```

## File Locations Summary

### Client PC

| File/Folder        | Location                                        | Purpose                   |
| ------------------ | ----------------------------------------------- | ------------------------- |
| screen_recorder.py | C:\ShadowCapClient\                             | Main client script        |
| license.key        | C:\ShadowCapClient\                             | License file              |
| public_key.pem     | C:\ShadowCapClient\                             | Public key for validation |
| config.json        | C:\ShadowCapClient\ScreenRecSvc\                | Configuration             |
| Recordings (temp)  | C:\ShadowCapClient\ScreenRecSvc\recordings\     | Local video storage       |
| Offline Queue      | C:\ShadowCapClient\ScreenRecSvc\offline_queue\  | Pending uploads           |
| Thumbnails         | C:\ShadowCapClient\ScreenRecSvc\thumbnails\     | Generated thumbnails      |
| Client log         | C:\ShadowCapClient\ScreenRecSvc\client.log      | Debug logs                |
| Crash log          | C:\ShadowCapClient\ScreenRecSvc\crash.log       | Crash logs                |
| Service stdout     | C:\ShadowCapClient\logs\service.log             | Service output            |
| Service stderr     | C:\ShadowCapClient\logs\service_error.log       | Service errors            |

### Server PC

| File/Folder          | Location                                  | Purpose                       |
| -------------------- | ----------------------------------------- | ----------------------------- |
| app.py               | C:\ShadowCapServer\                       | Main server script            |
| config.py            | C:\ShadowCapServer\                       | Configuration management      |
| models.py            | C:\ShadowCapServer\                       | Database models               |
| auth.py              | C:\ShadowCapServer\                       | Authentication & CSRF         |
| validators.py        | C:\ShadowCapServer\                       | Input validation              |
| video_processor.py   | C:\ShadowCapServer\                       | Thumbnail generation          |
| websocket_manager.py | C:\ShadowCapServer\                       | WebSocket support             |
| routes/api.py        | C:\ShadowCapServer\routes\                | API endpoints                 |
| routes/admin.py      | C:\ShadowCapServer\routes\                | Admin dashboard routes        |
| api_key_auth.py      | C:\ShadowCapServer\                       | API key authentication        |
| two_factor.py        | C:\ShadowCapServer\                       | TOTP 2FA support              |
| video_encryption.py  | C:\ShadowCapServer\                       | Video encryption at rest      |
| health_alerting.py   | C:\ShadowCapServer\                       | Health webhook/email alerts   |
| private_key.pem      | C:\ShadowCapServer\keys\                  | License signing key (SECRET!) |
| public_key.pem       | C:\ShadowCapServer\keys\                  | License validation key        |
| .env                 | C:\ShadowCapServer\                       | Environment configuration     |
| Database (SQLite)    | C:\ShadowCapServer\instance\              | SQLite database               |
| Uploaded Videos      | C:\ShadowCapServer\uploads\{machine_id}\  | Video storage                 |
| Thumbnails           | C:\ShadowCapServer\uploads\thumbnails\    | Video thumbnails              |
| Server log           | C:\ShadowCapServer\logs\server.log        | Server logs                   |
| Service stdout       | C:\ShadowCapServer\logs\service.log       | Service output                |
| Service stderr       | C:\ShadowCapServer\logs\service_error.log | Service errors                |

---

## API Endpoints

### Client → Server Communication

```
POST /api/v1/upload
─────────────────
Purpose: Upload recorded video
Headers:
  - X-License-Key: License key
  - X-Machine-ID: Client machine ID
Request:
  - video: MP4 file
  - timestamp: ISO 8601 timestamp
Response:
  - success: true/false
  - filename: Saved filename
  - video_id: Database ID
Rate Limit: 30 requests per 60 seconds

POST /api/v1/validate-license
─────────────────────────
Purpose: Validate license key
Request:
  - license: License key string
  - machine_id: Client machine ID
Response:
  - valid: true/false
  - data: License data (if valid)
  - error: Error message (if invalid)
Rate Limit: 10 requests per 60 seconds

POST /api/v1/heartbeat
──────────────────────
Purpose: Client heartbeat
Headers:
  - X-License-Key: License key
  - X-Machine-ID: Client machine ID
Response:
  - success: true/false
  - server_time: Server timestamp
Rate Limit: 60 requests per 60 seconds

GET /api/v1/health
──────────────────
Purpose: Health check
Response:
  - status: "healthy"
  - timestamp: Server time
  - version: API version

GET /api/v1/stream/<machine_id>/<filename>
──────────────────────────────────────────
Purpose: Stream video with Range support
Parameters:
  - machine_id: Client machine ID
  - filename: Video filename
Headers (optional):
  - Range: Byte range (e.g., bytes=0-1023)
Response:
  - 200: Full video stream
  - 206: Partial content stream
  - 404: Video not found

GET /api/v1/thumbnail/<machine_id>/<filename>
─────────────────────────────────────────────
Purpose: Get video thumbnail
Parameters:
  - machine_id: Client machine ID
  - filename: Video filename
Response:
  - JPEG image data
  - 404: Thumbnail not available

GET /api/v1/video-info/<machine_id>/<filename>
──────────────────────────────────────────────
Purpose: Get video metadata
Parameters:
  - machine_id: Client machine ID
  - filename: Video filename
Response:
  - exists: boolean
  - size: file size in bytes
  - duration: video length in seconds
  - width, height: video dimensions
  - fps: frames per second
```

---

## Security Features

### Authentication Flow

```
1. CSRF Protection
   ├── Server generates CSRF token
   ├── Token included in forms
   ├── Token validated on POST/PUT/DELETE
   └── Prevents cross-site request forgery

2. Rate Limiting
   ├── Tracked per IP address
   ├── Configurable limits per endpoint
   ├── Returns 429 when exceeded
   └── Prevents API abuse

3. License Validation
   ├── RSA-2048 signature verification
   ├── Machine ID binding
   ├── Expiration date check
   └── Feature flags enforcement

4. Input Validation
   ├── Filename sanitization
   ├── Path traversal prevention
   ├── File extension whitelist
   └── Size limits enforcement
```

---

## Utilities Used

### Screen Capture

- **Library**: `mss` (Multi-Screen Shot)
- **Purpose**: Captures screen frames
- **Speed**: Very fast, optimized for screen capture
- **Multi-monitor**: Supports all connected monitors

### Video Recording

- **Library**: `opencv-python` (cv2)
- **Purpose**: Video encoding and writing
- **Format**: MP4 (mp4v codec)
- **Features**: Frame capture, color conversion

### Audio Recording

- **Library**: `pyaudio` (optional)
- **Purpose**: Audio capture from microphone
- **Format**: WAV (16-bit PCM)
- **Features**: Configurable sample rate, channels

### Video Compression

- **Library**: `ffmpeg` (external) or OpenCV
- **Purpose**: Video compression for bandwidth savings
- **Quality**: CRF-based (configurable)
- **Features**: Automatic quality adjustment

### License System

- **Library**: `cryptography`
- **Purpose**: RSA-2048 signing and validation
- **Security**: Private key on server, public key embedded in client

### HTTP Communication

- **Library**: `requests`
- **Purpose**: Upload videos to server
- **Features**: Timeout handling, retry logic, heartbeat

### Database

- **Library**: `SQLAlchemy` with Flask-SQLAlchemy
- **Purpose**: Data persistence
- **Features**: ORM, migrations, relationships

### WebSocket

- **Library**: `flask-socketio` (optional)
- **Purpose**: Real-time communication
- **Features**: Client status, live updates

### Hidden Execution

- **Method**: Windows API (ctypes)
- **Purpose**: Hide console window
- **Code**: `ShowWindow(GetConsoleWindow(), 0)`

---

## Error Handling

### Client Error Handling

```
1. License Errors
   ├── Invalid license → Exit silently
   ├── Expired license → Exit silently
   └── Wrong machine ID → Exit silently

2. Network Errors
   ├── Connection failed → Add to offline queue
   ├── Timeout → Retry with backoff
   └── Server error (5xx) → Retry with backoff

3. Recording Errors
   ├── Capture failure → Log and retry
   ├── Write failure → Log and continue
   └── Disk full → Stop recording

4. Upload Errors
   ├── Client error (4xx) → Don't retry
   ├── Server error (5xx) → Retry
   └── Network error → Add to queue

5. Monitor Errors
   ├── Invalid monitor selection → Fall back to primary
   ├── Capture region out of bounds → Clamp to valid range
   └── Black frame detection → Try alternate monitors
```

### Server Error Handling

```
1. Validation Errors
   ├── Invalid input → Return 400
   ├── Missing fields → Return 400
   └── Invalid format → Return 400

2. Authentication Errors
   ├── Invalid license → Return 401
   ├── Expired license → Return 401
   └── Wrong machine ID → Return 401

3. Rate Limit Errors
   ├── Limit exceeded → Return 429
   └── Include Retry-After header

4. Server Errors
   ├── Unexpected error → Return 500
   ├── Log error details
   └── Don't expose internals

5. Video Processing Errors
   ├── FFmpeg unavailable → Fall back to OpenCV
   ├── Thumbnail generation failed → Return 404
   └── Video info unavailable → Return partial data
```

---

## Quick Reference Commands

```bash
# Start server
start_server.bat

# Get machine ID
python get_machine_id.py

# Build client executable
python build_client.py

# Install as Windows service (run as admin)
install.bat

# Uninstall service (run as admin)
uninstall.bat
```

---

## Monitoring

### Health Checks

```bash
# API health check
curl <http://localhost:5000/api/v1/health>
```

### Logs

```bash
# Server logs
tail -f server/logs/app.log

# Client logs (on client PC)
type %APPDATA%\ScreenRecSvc\service.log
```

### Database Queries

```sql
-- Count active clients
SELECT COUNT(*) FROM clients WHERE is_active = 1;

-- Recent uploads
SELECT * FROM videos ORDER BY upload_time DESC LIMIT 10;

-- License status
SELECT machine_id, expires_at FROM licenses WHERE is_active = 1;

-- Storage usage per client
SELECT c.machine_id, SUM(v.file_size) as total_bytes
FROM clients c
JOIN videos v ON c.id = v.client_id
GROUP BY c.machine_id;
```

---

## Configuration Reference

### Client Configuration Options

| Option                 | Type   | Default   | Description                    |
| ---------------------- | ------ | --------- | ------------------------------ |
| server_url             | string | localhost | Server URL for uploads         |
| upload_interval        | int    | 300       | Seconds between uploads        |
| recording_fps          | int    | 10        | Frames per second              |
| video_quality          | int    | 80        | Video quality (1-100)          |
| chunk_duration         | int    | 60        | Seconds per video chunk        |
| heartbeat_interval     | int    | 60        | Seconds between heartbeats     |
| max_offline_storage_mb | int    | 1000      | Max offline storage in MB      |
| retry_base_delay       | float  | 1.0       | Base retry delay (seconds)     |
| retry_max_delay        | float  | 300.0     | Max retry delay (seconds)      |
| monitor_selection      | int    | 1         | Monitor to record (1=primary)  |
| region_x               | int    | 0         | Capture region X offset        |
| region_y               | int    | 0         | Capture region Y offset        |
| region_width           | int    | 0         | Capture region width (0=full)  |
| region_height          | int    | 0         | Capture region height (0=full) |
| enable_audio           | bool   | false     | Enable audio recording         |
| audio_sample_rate      | int    | 44100     | Audio sample rate in Hz        |
| audio_channels         | int    | 2         | Number of audio channels       |
| enable_compression     | bool   | true      | Enable video compression       |
| compression_quality    | int    | 23        | FFmpeg CRF value               |
| generate_thumbnails    | bool   | true      | Generate video thumbnails      |
| use_websocket          | bool   | false     | Enable WebSocket connection    |
