# Screen Recorder - Complete Workflow

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
│  │   1. Screen Recorder   │  │                 │  │   1. Flask Server      │  │
│  │      (Hidden)          │  │                 │  │      (app.py)          │  │
│  │                        │  │                 │  │                        │  │
│  │  • Captures screen     │  │                 │  │  • Receives videos     │  │
│  │  • Records to MP4      │  │                 │  │  • Validates licenses  │  │
│  │  • Validates license   │  │                 │  │  • Serves dashboard    │  │
│  │  • Offline queue       │  │                 │  │  • Rate limiting       │  │
│  │  • Heartbeat           │  │                 │  │  • CSRF protection     │  │
│  │  • Retry logic         │  │                 │  │                        │  │
│  └──────────┬─────────────┘  │                 │  └──────────┬─────────────┘  │
│             │                │                 │             │                │
│             ▼                │                 │             ▼                │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   2. Local Storage     │  │                 │  │   2. Database          │  │
│  │   %APPDATA%/           │  │   HTTP POST     │  │   (SQLite)             │  │
│  │   ScreenRecSvc/        │  │  ──────────────►│  │                        │  │
│  │   recordings/          │  │                 │  │   • Clients            │  │
│  │   offline_queue/       │  │                 │  │   • Licenses           │  │
│  │   • rec_001.mp4        │  │                 │  │   • Videos             │  │
│  │   • rec_002.mp4        │  │                 │  │   • AuditLogs          │  │
│  └────────────────────────┘  │                 │  └────────────────────────┘  │
│                              │                 │                              │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   3. License File      │  │                 │  │   3. Upload Storage    │  │
│  │   license.key          │  │                 │  │   server/uploads/      │  │
│  │   (Validates client)   │  │                 │  │   {machine_id}/        │  │
│  └────────────────────────┘  │                 │  └────────────────────────┘  │
│                              │                 │                              │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │   4. Heartbeat Thread  │  │                 │  │   4. Admin Dashboard   │  │
│  │   (Monitors server)    │  │◄────────────────│  │   http://server:5000   │  │
│  └────────────────────────┘  │   Heartbeat OK  │  │   /admin               │  │
│                              │                 │  │                        │  │
│                              │                 │  │   • View all clients   │  │
│                              │                 │  │   • Generate licenses  │  │
│                              │                 │  │   • Download videos    │  │
│                              │                 │  │   • Delete videos      │  │
│                              │                 │  └────────────────────────┘  │
└──────────────────────────────┘                 └──────────────────────────────┘
```

---

## Step-by-Step Flow

### PHASE 1: Server Setup (One-time)

```
Step 1: Start the Server
────────────────────────
$ cd ScreenRecorderApp
$ start_server.bat

Or with Docker:
$ docker-compose up -d

This will:
├── Create virtual environment
├── Install dependencies (Flask, SQLAlchemy, cryptography, etc.)
├── Generate RSA key pair (private_key.pem, public_key.pem)
│   └── Keys stored in: server/keys/
├── Initialize SQLite database
│   └── Tables: clients, licenses, videos, audit_logs
├── Create directories:
│   ├── uploads/     (for video storage)
│   ├── licenses/    (for license storage)
│   └── keys/        (for RSA keys)
└── Start Flask server on port 5000

Access Admin Dashboard:
URL: http://localhost:5000/admin
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
1. Go to: http://server-ip:5000/admin
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
    "server_url": "http://YOUR_SERVER_IP:5000",
    "upload_interval": 300,
    "recording_fps": 10,
    "chunk_duration": 60,
    "heartbeat_interval": 60,
    "max_offline_storage_mb": 1000,
    "retry_base_delay": 1.0,
    "retry_max_delay": 300.0
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
   └── Initialize retry handler

2. VALIDATION PHASE
   ├── Load license.key from disk
   ├── Load public_key.pem (embedded in exe)
   ├── Validate license signature (RSA-2048)
   ├── Check license expiration date
   ├── Verify machine ID matches
   └── If invalid → Exit silently

3. RECORDING PHASE (if license valid)
   ├── Initialize screen capture (mss library)
   ├── Get monitor resolution
   ├── Create video writer (OpenCV)
   ├── Start recording loop:
   │   ├── Capture screen frame
   │   ├── Convert BGRA → BGR
   │   ├── Write frame to video
   │   ├── Check chunk duration
   │   │   └── If chunk complete → Save & start new
   │   └── Sleep (1/fps seconds)
   └── Continue until stopped

4. HEARTBEAT PHASE (background thread)
   ├── Every 60 seconds (configurable)
   ├── POST to: http://server:5000/api/v1/heartbeat
   ├── Include: license key, machine ID
   ├── Update server_reachable flag
   └── Log connection status

5. STORAGE PHASE
   ├── Save videos to: %APPDATA%/ScreenRecSvc/recordings/
   │   ├── rec_20260312_210000_a1b2c3d4.mp4
   │   ├── rec_20260312_210100_a1b2c3d4.mp4
   │   └── ...
   └── Videos stored locally before upload

6. UPLOAD PHASE (background thread)
   ├── Every 5 minutes (configurable)
   ├── First, process offline queue:
   │   ├── Get next pending video
   │   ├── Attempt upload with retry
   │   └── On success → Remove from queue
   ├── Then, upload current chunks:
   │   ├── POST to: http://server:5000/api/v1/upload
   │   ├── Headers: X-License-Key, X-Machine-ID
   │   └── Server validates & saves
   ├── On success → Delete local copy
   └── On failure → Add to offline queue

7. RETRY LOGIC
   ├── Exponential backoff with jitter
   ├── Base delay: 1 second
   ├── Max delay: 300 seconds (5 minutes)
   ├── Max retries: 5
   └── Retryable errors:
       ├── ConnectionError
       ├── Timeout
       └── HTTP 5xx errors
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
   ├── Log audit entry
   └── Return success response
```

### PHASE 5: Server Storage

```
Step 7: Server Video Storage
────────────────────────────

Videos stored on server at:
server/uploads/{machine_id}/

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
├── b2c3d4e5f6g7h8i9j0k1l2m3n4o5p7/
│   └── ...
└── ...
```

---

## File Locations Summary

### Client PC

| File/Folder              | Location                               | Purpose             |
| ------------------------ | -------------------------------------- | ------------------- |
| ScreenRecorderClient.exe | C:\Program Files\ScreenRecSvc\         | Main executable     |
| license.key              | C:\Program Files\ScreenRecSvc\         | License file        |
| config.json              | C:\Program Files\ScreenRecSvc\         | Configuration       |
| Recordings (temp)        | %APPDATA%\ScreenRecSvc\recordings\     | Local video storage |
| Offline Queue            | %APPDATA%\ScreenRecSvc\offline_queue\  | Pending uploads     |
| Logs                     | %APPDATA%\ScreenRecSvc\service.log     | Debug logs          |

### Server PC

| File/Folder       | Location                     | Purpose                       |
| ----------------- | ---------------------------- | ----------------------------- |
| app.py            | server/                      | Main server script            |
| config.py         | server/                      | Configuration management      |
| models.py         | server/                      | Database models               |
| auth.py           | server/                      | Authentication & CSRF         |
| validators.py     | server/                      | Input validation              |
| routes/api.py     | server/routes/               | API endpoints                 |
| private_key.pem   | server/keys/                 | License signing key (SECRET!) |
| public_key.pem    | server/keys/                 | License validation key        |
| screenrecorder.db | server/data/                 | SQLite database               |
| Uploaded Videos   | server/uploads/{machine_id}/ | Video storage                 |

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

GET /api/v1/get-machine-id
──────────────────────────
Purpose: Get machine ID
Response:
  - machine_id: Client machine ID

GET /api/v1/get-public-key
──────────────────────────
Purpose: Get public key for client
Response:
  - public_key: PEM-formatted key
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

### Video Recording

- **Library**: `opencv-python` (cv2)
- **Purpose**: Video encoding and writing
- **Format**: MP4 (mp4v codec)

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
```

---

## Quick Reference Commands

```bash
# Start server
start_server.bat

# Or with Docker
docker-compose up -d

# Get machine ID
python get_machine_id.py

# Test system
python test_system.py

# Run unit tests
python -m pytest tests/test_server.py -v

# Build client executable
python build_client.py

# Install as Windows service (run as admin)
install.bat

# Uninstall service (run as admin)
uninstall.bat

# View Docker logs
docker-compose logs -f

# Stop Docker services
docker-compose down
```

---

## Monitoring

### Health Checks

```bash
# API health check
curl http://localhost:5000/api/v1/health

# Docker health check
docker inspect --format='{{.State.Health.Status}}' screenrecorder-server
```

### Logs

```bash
# Server logs
tail -f server/logs/app.log

# Client logs (on client PC)
type %APPDATA%\ScreenRecSvc\service.log

# Docker logs
docker-compose logs -f server
```

### Database Queries

```sql
-- Count active clients
SELECT COUNT(*) FROM clients WHERE is_active = 1;

-- Recent uploads
SELECT * FROM videos ORDER BY upload_time DESC LIMIT 10;

-- License status
SELECT machine_id, expires_at FROM licenses WHERE is_active = 1;
```

</task_progress>

- [x] All improvements implemented
- [x] Update README.md documentation
- [x] Update WORKFLOW.md documentation
      </task_progress>
      </write_to_file>
