# ShadowCap — Server Installation Guide

Step-by-step guide to install the ShadowCap server on your Windows computer.

## Prerequisites

- Windows 10 or Windows 11 (or any Linux/macOS with Docker)
- Internet connection
- Administrator access to your computer

## Installation Methods

You can install the server using either **Docker** (recommended) or **manual installation**.

---

## Method 1: Docker Installation (Recommended)

### Step 1: Install Docker

1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Run the installer and follow the wizard
3. Restart your computer when prompted
4. Verify: open Command Prompt and run `docker --version`

### Step 2: Download ShadowCap

1. Clone the repository:

   ```bash
   git clone https://github.com/rahulmasal/ShadowCap.git
   cd ShadowCap
   ```

   Or download the ZIP from GitHub and extract it.

### Step 3: Configure Environment Variables

1. Create the environment file:

   ```bash
   cd server
   copy .env.example .env
   ```

2. Edit `.env` in Notepad — **you MUST set these**:

   ```ini
   # Required — server will NOT start without these
   SECRET_KEY=your-random-secret-key-at-least-32-characters
   ADMIN_PASSWORD=your-secure-admin-password-at-least-12-chars

   # Optional — private key encryption
   KEY_PASSPHRASE=passphrase-to-encrypt-private-key

   # Optional — PostgreSQL (defaults to SQLite)
   DATABASE_URL=postgresql://shadowcap:password@db:5432/shadowcap

   # Optional — Redis for rate limiting
   RATE_LIMIT_STORAGE_URI=redis://redis:6379/0

   # Optional — retention policies
   AUDIT_LOG_RETENTION_DAYS=90
   VIDEO_RETENTION_DAYS=0
   VIDEO_DISK_LIMIT_MB=0
   ```

3. Save the file

### Step 4: Start the Server

```bash
cd ..   # back to project root
docker-compose up -d
```

First time may take 2-3 minutes to download images. This starts:

- **ShadowCap server** on port 5000
- **PostgreSQL** database on port 5432 (optional)
- **Redis** on port 6379 (optional)

### Step 5: Access the Admin Dashboard

1. Open your web browser
2. Go to: `http://localhost:5000/admin`
3. Enter the password you set in Step 3
4. Click **"Login"**

**Docker Management Commands:**

```bash
# Start the server
docker-compose up -d

# Stop the server
docker-compose down

# View logs
docker-compose logs -f server

# Restart the server
docker-compose restart

# Check status
docker-compose ps

# Rebuild after code changes
docker-compose up -d --build
```

---

## Method 2: Manual Installation

### Step 1: Install Python

1. Download Python from https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT:** Check **"Add Python to PATH"** ✅
4. Click **"Install Now"**
5. Verify: open Command Prompt, type `python --version`

### Step 2: Download ShadowCap

1. Clone the repository:

   ```bash
   git clone https://github.com/rahulmasal/ShadowCap.git
   cd ShadowCap
   ```

   Or download the ZIP from GitHub and extract it.

### Step 3: Install the Server

1. Open the `server` folder
2. Create a virtual environment:

   ```batch
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:

   ```batch
   pip install -r requirements.txt
   ```

4. Or install with optional dependencies:

   ```batch
   pip install -r requirements.txt
   pip install psycopg2-binary redis pyotp qrcode
   ```

### Step 4: Configure the Server

1. Create the `.env` file:

   ```batch
   copy .env.example .env
   ```

2. Edit `.env` — set at minimum:

   ```ini
   SECRET_KEY=your-random-secret-key-at-least-32-characters
   ADMIN_PASSWORD=your-secure-admin-password-at-least-12-chars
   ```

3. Initialize the database:

   ```batch
   python -c "from app import app, db; app.app_context().__enter__(); db.create_all()"
   ```

   Or use Flask-Migrate:

   ```batch
   flask db upgrade
   ```

### Step 5: Run the Server

**Development mode:**

```batch
python app.py
```

**Production with Gunicorn (Linux/macOS):**

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

**As a Windows Service:**

1. Right-click `install_server_service.bat`
2. Select **"Run as administrator"**
3. Wait for installation to complete

### Step 6: Access the Admin Dashboard

1. Open your web browser
2. Go to: `http://localhost:5000/admin`
3. Enter the password you set in Step 4
4. Click **"Login"**

---

## Server Configuration Reference

All settings can be configured via environment variables or the `.env` file:

| Variable                   | Required | Default    | Description                                 |
| -------------------------- | -------- | ---------- | ------------------------------------------- |
| `SECRET_KEY`               | ✅ Yes   | —          | Flask secret key (min 32 chars)             |
| `ADMIN_PASSWORD`           | ✅ Yes   | —          | Admin dashboard password (min 12 chars)     |
| `DATABASE_URL`             | No       | SQLite     | PostgreSQL or SQLite connection string      |
| `KEY_PASSPHRASE`           | No       | None       | Passphrase to encrypt the RSA private key   |
| `RATE_LIMIT_STORAGE_URI`   | No       | Memory     | Redis URI for rate limit storage            |
| `AUDIT_LOG_RETENTION_DAYS` | No       | 90         | Days to keep audit logs (0=forever)         |
| `VIDEO_RETENTION_DAYS`     | No       | 0          | Days to keep videos (0=forever)             |
| `VIDEO_DISK_LIMIT_MB`      | No       | 0          | Max total video storage in MB (0=unlimited) |
| `FLASK_ENV`                | No       | production | `development` or `production`               |
| `LOG_LEVEL`                | No       | INFO       | Logging level                               |

---

## Troubleshooting

### Docker Issues

**"docker: command not found"**

- Make sure Docker Desktop is installed and running
- Restart your computer after installing Docker

**"Cannot connect to the Docker daemon"**

- Open Docker Desktop and wait for it to start

**Port 5000 already in use**

- Stop any existing server: `docker-compose down`
- Or change the port in `docker-compose.yml` (e.g., `"5001:5000"`)

**Container keeps restarting**

- Check logs: `docker-compose logs -f server`
- Make sure `.env` file exists with `SECRET_KEY` and `ADMIN_PASSWORD` set

### Manual Installation Issues

**"Python is not recognized"**

- Restart your computer
- Reinstall Python and check "Add Python to PATH"

**"Access denied"**

- Right-click and select "Run as administrator"

**Server won't start**

- Check if port 5000 is in use: `netstat -ano | findstr :5000`
- Check logs for errors

**Can't access admin dashboard**

- Make sure the server is running: `sc query ScreenRecorderServer`
- Try `http://127.0.0.1:5000/admin`

---

## Managing the Server

### Docker

```bash
docker-compose up -d        # Start
docker-compose down          # Stop
docker-compose logs -f server  # View logs
docker-compose restart       # Restart
docker-compose ps            # Check status
```

### Windows Service

```batch
sc start ScreenRecorderServer   :: Start
sc stop ScreenRecorderServer    :: Stop
sc query ScreenRecorderServer   :: Check status
uninstall_server_service.bat    :: Uninstall
```

---

## Next Steps

Now that your server is running:

1. Generate licenses for client computers
2. Monitor uploaded videos in the admin dashboard
3. Configure retention policies if needed
4. Set up health alerting webhooks for monitoring

See the [Client Installation Guide](CLIENT_INSTALLATION_GUIDE.md) for installing the client.
