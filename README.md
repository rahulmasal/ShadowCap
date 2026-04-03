# Screen Recorder Application

A comprehensive auto screen recording application for Windows with client-server architecture, hidden recording functionality, and license-based activation.

## 📚 Documentation

- **[Quick Start Guide](QUICK_START_GUIDE.md)** - Get started in 10 minutes (recommended for beginners)
- **[Server Installation Guide](SERVER_INSTALLATION_GUIDE.md)** - Detailed server setup instructions
- **[Client Installation Guide](CLIENT_INSTALLATION_GUIDE.md)** - Detailed client setup instructions
- **[API Documentation](API.md)** - Complete API reference
- **[Workflow Documentation](WORKFLOW.md)** - How the system works
- **[Docker Deployment](#docker-deployment)** - Deploy with Docker and Docker Compose
- **[Testing](#testing)** - Unit tests and test coverage

## Features

### Core Features

- **Hidden Recording**: Client runs silently in the background without visible windows
- **License-Based**: Only valid licenses can activate recording (RSA-2048 signed)
- **Automatic Upload**: Recorded videos are automatically uploaded to the server
- **Chunked Recording**: Videos are recorded in configurable chunks (default: 1 minute)
- **Admin Dashboard**: Web-based dashboard to manage clients, licenses, and videos
- **Secure License System**: RSA-signed licenses with machine ID binding
- **Offline Queue**: Videos are queued when server is unreachable and uploaded later
- **Retry Logic**: Exponential backoff retry mechanism for failed uploads
- **Heartbeat**: Client heartbeat for connection monitoring
- **Rate Limiting**: API rate limiting to prevent abuse
- **CSRF Protection**: Secure forms with CSRF tokens

### New Features ✨

#### Multi-Monitor Support

- Select which monitor to record (primary, secondary, etc.)
- Automatic monitor detection and validation
- Fallback to primary monitor on invalid selection

#### Configurable Recording Region

- Record specific regions of the screen
- Set custom width, height, and position
- Automatic bounds validation

#### Audio Recording (Optional)

- Record system audio or microphone
- Configurable sample rate and channels
- WAV output format
- Requires PyAudio installation

#### Video Compression (Optional)

- FFmpeg-based video compression
- Configurable quality levels (CRF-based)
- Automatic bandwidth savings
- OpenCV fallback available

#### Pause/Resume Recording

- Pause and resume recording without stopping
- State management (RECORDING ↔ PAUSED)
- Thread-safe event handling

#### Video Streaming

- Stream videos directly from server
- HTTP Range request support (partial content)
- Chunked streaming for large files

#### Thumbnail Generation

- Automatic thumbnail extraction from videos
- FFmpeg or OpenCV based
- Configurable timestamp percentage

#### WebSocket Real-Time Updates (Optional)

- Real-time client status notifications
- Admin dashboard live updates
- Event-based communication

### Recent Improvements ✅

#### Security Enhancements

- **Timing Attack Protection**: Fixed timing attack vulnerability in password validation using constant-time comparison
- **User Enumeration Prevention**: Added protection against user enumeration attacks
- **Custom Exceptions**: Comprehensive exception hierarchy for better error handling

#### Client Improvements

- **Graceful Shutdown**: Added signal handlers (SIGINT, SIGTERM, SIGHUP) for graceful shutdown
- **Thread Management**: Improved thread cleanup with configurable timeouts
- **Responsive Shutdown**: 0.1s increments for faster signal response

#### Testing Infrastructure

- **Unit Tests**: Comprehensive test suite with pytest
- **Test Coverage**: Tests for license manager, validators, and authentication
- **Test Fixtures**: Reusable test fixtures and configuration
- **Custom Markers**: Markers for screen capture, audio, network, and slow tests

#### Docker Support

- **Dockerfile**: Multi-stage build with security best practices
- **Docker Compose**: Complete orchestration with volume mounts
- **Non-Root User**: Container runs as non-root for security
- **Health Checks**: Built-in health check endpoint

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   Client PC     │         │   Server PC     │
│                 │         │                 │
│ ┌─────────────┐ │  HTTP   │ ┌─────────────┐ │
│ │  Screen     │ │ Upload  │ │   Flask     │ │
│ │  Recorder   │ ├────────►│ │   Server    │ │
│ │  (Hidden)   │ │         │ │             │ │
│ └─────────────┘ │         │ └─────────────┘ │
│        │        │         │        │        │
│        ▼        │         │        ▼        │
│ ┌─────────────┐ │         │ ┌─────────────┐ │
│ │  License    │ │         │ │   Admin     │ │
│ │  Validator  │ │         │ │  Dashboard  │ │
│ └─────────────┘ │         │ └─────────────┘ │
│        │        │         │        │        │
│        ▼        │         │        ▼        │
│ ┌─────────────┐ │         │ ┌─────────────┐ │
│ │  Offline    │ │         │ │  Database   │ │
│ │  Queue      │ │         │ │ (SQLite)    │ │
│ └─────────────┘ │         │ └─────────────┘ │
└─────────────────┘         └─────────────────┘
```

## Project Structure

```
ScreenRecorderApp/
├── client/                    # Client application
│   ├── screen_recorder.py     # Main client script
│   ├── audio_recorder.py      # Audio recording module
│   ├── video_compressor.py    # Video compression module
│   ├── monitor_manager.py     # Multi-monitor support
│   └── requirements.txt       # Python dependencies
├── server/                    # Server application
│   ├── app.py                 # Flask server (main)
│   ├── config.py              # Configuration management
│   ├── models.py              # Database models (SQLAlchemy)
│   ├── auth.py                # Authentication & CSRF
│   ├── validators.py          # Input validation
│   ├── video_processor.py     # Thumbnail generation
│   ├── websocket_manager.py   # WebSocket support
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Docker image definition
│   ├── routes/                # API routes (blueprints)
│   │   ├── __init__.py
│   │   └── api.py             # API v1 endpoints
│   └── templates/             # HTML templates
├── shared/                    # Shared modules
│   ├── __init__.py
│   ├── license_manager.py     # License generation/validation
│   └── exceptions.py          # Custom exception classes
├── tests/                     # Unit tests
│   ├── __init__.py
│   ├── conftest.py            # Pytest configuration
│   ├── test_license_manager.py
│   └── test_validators.py
├── API.md                     # API documentation
├── WORKFLOW.md                # Workflow documentation
├── QUICK_START_GUIDE.md       # Quick start guide
├── SERVER_INSTALLATION_GUIDE.md # Server installation guide
├── CLIENT_INSTALLATION_GUIDE.md # Client installation guide
├── build_client.py            # Build script for client
├── start_server.bat           # Server startup script
├── docker-compose.yml         # Docker Compose configuration
├── .dockerignore              # Docker ignore rules
├── pytest.ini                 # Pytest configuration
└── README.md                  # This file
```

## Installation

### Server Setup

#### Option 1: Direct Installation

1. **Install Python dependencies:**

   ```bash
   cd server
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   Copy the example environment file and update it:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` file with your settings:

   ```env
   SECRET_KEY=your-secret-key-change-in-production-min-32-chars
   ADMIN_PASSWORD=your-secure-admin-password-min-12-chars
   PORT=5000
   DATABASE_URL=sqlite:///screenrecorder.db
   ```

3. **Run the server:**

   ```bash
   python app.py
   ```

#### Option 2: Docker Deployment

Deploy the server using Docker for easy setup and isolation:

1. **Build and run with Docker Compose:**

   ```bash
   # Build and start the server
   docker-compose up -d

   # View logs
   docker-compose logs -f server

   # Stop services
   docker-compose down
   ```

2. **Or build manually with Docker:**

   ```bash
   cd server
   docker build -t screenrecorder-server .
   docker run -d \
     --name screenrecorder-server \
     -p 5000:5000 \
     -v ./data:/app/data \
     -v ./uploads:/app/uploads \
     -v ./licenses:/app/licenses \
     -v ./keys:/app/keys \
     -e SECRET_KEY=your-secret-key \
     -e ADMIN_PASSWORD=your-admin-password \
     screenrecorder-server
   ```

3. **Access the admin dashboard:**
   Open `<http://localhost:5000/admin`> in your browser

**Docker Security Features:**

- Non-root user execution
- Multi-stage build for smaller image size
- Health checks for container monitoring
- Volume mounts for persistent data

#### Option 3: Windows Service

For production deployment, install as a Windows service:

1. **Run as administrator:**

   ```batch
   install_server_service.bat
   ```

2. **The service will:**
   - Install to `C:\Program Files\ScreenRecorderServer`
   - Register as Windows service "ScreenRecorderServer"
   - Start automatically on system boot
   - Run in the background

3. **Access the admin dashboard:**
   Open `<http://localhost:5000/admin`> in your browser

4. **Manage the service:**

   ```batch
   # Start service
   sc start ScreenRecorderServer

   # Stop service
   sc stop ScreenRecorderServer

   # Check status
   sc query ScreenRecorderServer

   # Uninstall
   uninstall_server_service.bat
   ```

### Database Migrations

For production deployments, use Alembic for database migrations:

```bash
cd server
pip install alembic

# Initialize migrations (first time only)
alembic init migrations

# Generate a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

See [`server/migrations/README.md`](server/migrations/README.md) for detailed migration instructions.

### Client Setup

1. **Install Python dependencies:**

   ```bash
   cd client
   pip install -r requirements.txt
   ```

2. **Get the machine ID:**

   ```bash
   python screen_recorder.py --get-id
   ```

3. **Generate a license:**
   - Go to the admin dashboard
   - Click "Generate License"
   - Enter the machine ID
   - Copy the generated license key

4. **Save the license:**
   Save the license key to `license.key` file in the client directory

5. **Run the client:**
  
   ```bash
   python screen_recorder.py

```

### Building the Client Executable

1. **First, run the server to generate keys:**

   ```bash
   cd server
   python app.py
   ```

1. **Build the client:**

   ```bash
   cd ..
   python build_client.py
   ```

2. **The built files will be in the `dist` directory:**
   - `ScreenRecorderClient.exe` - The client executable
   - `install_client_service.bat` - Installation script
   - `uninstall_client_service.bat` - Uninstallation script

## Usage

### Admin Dashboard

1. **Login:**
   - Navigate to `<http://server-ip:5000/admin/login`>
   - Enter the admin password

2. **Generate License:**
   - Click "Generate License"
   - Enter the client's machine ID
   - Set expiration days
   - Select features
   - Click "Generate"
   - Copy the license key

3. **View Clients:**
   - See all connected clients
   - View uploaded videos
   - Download or delete videos

4. **Manage Licenses:**
   - View all active licenses
   - Delete licenses to revoke access

### Client Deployment

1. **Copy files to client machine:**
   - `ScreenRecorderClient.exe`
   - `license.key`
   - `install_client_service.bat`

2. **Edit `install_client_service.bat`:**
   - Change `YOUR_SERVER_IP` to your server's IP address

3. **Run as administrator:**
   - Right-click `install_client_service.bat`
   - Select "Run as administrator"

4. **The service will:**
   - Install to `C:\ScreenRecorderClient`
   - Register as a Windows service
   - Start automatically on boot
   - Run hidden in the background

## Configuration

### Client Configuration

Edit the `config.json` file:

```json
{
  "server_url": "<http://your-server-ip:5000",>
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
  "enable_audio": false,
  "audio_sample_rate": 44100,
  "enable_compression": true,
  "compression_quality": 23,
  "use_websocket": false
}
```

| Setting                | Description                      | Default               |
| ---------------------- | -------------------------------- | --------------------- |
| server_url             | Server URL for uploads           | <http://localhost:5000> |
| upload_interval        | Seconds between uploads          | 300                   |
| recording_fps          | Frames per second                | 10                    |
| video_quality          | Video quality (1-100)            | 80                    |
| chunk_duration         | Seconds per video chunk          | 60                    |
| heartbeat_interval     | Seconds between heartbeats       | 60                    |
| max_offline_storage_mb | Max offline storage in MB        | 1000                  |
| retry_base_delay       | Base delay for retry (seconds)   | 1.0                   |
| retry_max_delay        | Max delay for retry (seconds)    | 300.0                 |
| monitor_selection      | Monitor to record (1=primary)    | 1                     |
| region_x               | Recording region X offset        | 0                     |
| region_y               | Recording region Y offset        | 0                     |
| region_width           | Recording region width (0=full)  | 0                     |
| region_height          | Recording region height (0=full) | 0                     |
| enable_audio           | Enable audio recording           | false                 |
| audio_sample_rate      | Audio sample rate in Hz          | 44100                 |
| enable_compression     | Enable video compression         | true                  |
| compression_quality    | FFmpeg CRF value (lower=better)  | 23                    |
| use_websocket          | Enable WebSocket connection      | false                 |

### Server Configuration

Environment variables:

| Variable         | Description                | Default           |
| ---------------- | -------------------------- | ----------------- |
| SECRET_KEY       | Flask secret key           | (auto-generated)  |
| ADMIN_PASSWORD   | Admin dashboard password   | (required)        |
| PORT             | Server port                | 5000              |
| HOST             | Server host                | 0.0.0.0           |
| DATABASE_URL     | Database connection string | sqlite:///data.db |
| UPLOAD_FOLDER    | Video storage path         | uploads           |
| LICENSE_FOLDER   | License storage path       | licenses          |
| KEYS_FOLDER      | RSA keys storage path      | keys              |
| MAX_CONTENT_SIZE | Max upload size (bytes)    | 524288000 (500MB) |
| RATE_LIMIT       | Enable rate limiting       | true              |
| LOG_LEVEL        | Logging level              | INFO              |

## API Documentation

See [API.md](API.md) for complete API documentation.

### Quick Reference

| Endpoint                       | Method | Description         |
| ------------------------------ | ------ | ------------------- |
| /api/v1/health                 | GET    | Health check        |
| /api/v1/upload                 | POST   | Upload video        |
| /api/v1/validate-license       | POST   | Validate license    |
| /api/v1/heartbeat              | POST   | Client heartbeat    |
| /api/v1/get-machine-id         | GET    | Get machine ID      |
| /api/v1/get-public-key         | GET    | Get public key      |
| /api/v1/stream/<id>/<file>     | GET    | Stream video        |
| /api/v1/thumbnail/<id>/<file>  | GET    | Get video thumbnail |
| /api/v1/video-info/<id>/<file> | GET    | Get video info      |

## Security Features

### Authentication & Authorization

- **JWT Tokens**: Session-based authentication with JWT tokens
- **CSRF Protection**: All forms protected with CSRF tokens
- **Rate Limiting**: API endpoints protected against abuse
- **Secure Password Hashing**: Uses werkzeug's scrypt for password hashing

### License Security

- **RSA-2048 Signing**: Licenses signed with RSA-2048
- **Machine Binding**: Each license bound to specific machine ID
- **Expiration**: Licenses have configurable expiration dates
- **Feature Flags**: Licenses can enable/disable features

### Input Validation

- **Filename Validation**: Prevents path traversal attacks
- **File Extension Check**: Only allowed file types accepted
- **Machine ID Validation**: Validates format and characters
- **License Key Validation**: Validates format before processing

### Best Practices

1. **Change default passwords:**
   - Set a strong `ADMIN_PASSWORD`
   - Set a unique `SECRET_KEY`

2. **Protect the private key:**
   - The `keys/private_key.pem` file should be kept secure
   - Never share the private key

3. **Use HTTPS in production:**
   - Deploy behind a reverse proxy (nginx, Apache)
   - Configure SSL/TLS certificates

4. **Regular updates:**
   - Keep dependencies updated
   - Monitor security advisories

## Troubleshooting

### Client won't start

- Check if `license.key` exists
- Verify the license is valid and not expired
- Check the server URL in config
- Check logs at `C:\ScreenRecorderClient\ScreenRecSvc\client.log`

### Videos not uploading

- Verify server is running
- Check network connectivity
- Verify license has upload feature enabled
- Check offline queue status

### Service won't install

- Run `install_client_service.bat` as administrator
- Check if antivirus is blocking
- Verify Python is installed

### Hidden window not working

- The executable must be built with `--windowed` flag
- Check PyInstaller build settings

### Database errors

- Check DATABASE_URL environment variable
- Ensure database directory exists
- Check file permissions

## Development

### Running in Development Mode

**Server:**

```bash
cd server
FLASK_DEBUG=true python app.py
```

**Client:**

```bash
cd client
python screen_recorder.py
```

### Production Deployment Checklist

Before deploying to production:

1. **Change default passwords:**
   - Set a strong `ADMIN_PASSWORD` (minimum 12 characters)
   - Set a unique `SECRET_KEY` (minimum 32 characters)

2. **Configure HTTPS:**
   - Use nginx reverse proxy with SSL certificates
   - Uncomment HTTPS server block in `nginx.conf`

3. **Set up database migrations:**
   - Initialize Alembic: `alembic init migrations`
   - Run initial migration: `alembic upgrade head`

4. **Configure rate limiting:**
   - Adjust rate limits in `nginx.conf` as needed
   - Monitor for abuse patterns

5. **Set up monitoring:**
   - Configure log rotation
   - Set up health check monitoring
   - Monitor disk space for uploads

6. **Backup strategy:**
   - Regular database backups
   - Video storage backups
   - Configuration backups

### Adding Features

1. **New API endpoints:**
   - Add route in `server/routes/api.py`
   - Add validation in `server/validators.py`
   - Update `API.md` documentation

2. **New license features:**
   - Edit `shared/license_manager.py`
   - Add feature flags to license generation
   - Implement feature checks in client

3. **Database changes:**
   - Add model in `server/models.py`
   - Create migration if needed
   - Update admin dashboard

## License

This project is for educational and authorized use only. Ensure compliance with local privacy laws before deployment.

## Disclaimer

This software is provided as-is. Users are responsible for ensuring legal compliance when recording screens. The authors are not responsible for any misuse of this software.
