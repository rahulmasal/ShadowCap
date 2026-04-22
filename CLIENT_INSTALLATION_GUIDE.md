# ShadowCap — Client Installation Guide

Step-by-step guide to install the ShadowCap client on a Windows computer you want to monitor.

## Prerequisites

- Windows 10 or Windows 11
- Internet connection
- Administrator access to the computer
- The ShadowCap server is already running (see [Server Installation Guide](SERVER_INSTALLATION_GUIDE.md))

## Step 1: Get Your Machine ID

1. **Open Command Prompt:**
   - Press `Windows Key + R`
   - Type `cmd` and press Enter

2. **Navigate to the client folder:**

   ```batch
   cd Desktop\ScreenRecorderApp\client
   ```

3. **Install dependencies (first time only):**

   ```batch
   pip install -r requirements.txt
   ```

4. **Get your machine ID:**

   ```batch
   python screen_recorder.py --get-id
   ```

5. **Copy the machine ID** — you'll see output like:
   ```
   Your Machine ID: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
   ```

## Step 2: Generate a License

1. **Go to the ShadowCap admin dashboard:**
   - Open your web browser
   - Go to: `http://server-ip:5000/admin`
   - Login with your admin password

2. **Generate a license:**
   - Click **"Generate License"** in the navbar
   - Paste the machine ID from Step 1
   - Set expiry days (e.g., 365 for 1 year)
   - Check the features you want: ✅ Recording ✅ Upload
   - Click **"Generate"**

3. **Copy the license key** — click **"Copy to Clipboard"** and save it

## Step 3: Install the Client

### Option A: Using Pre-built Executable

1. **Build the client executable:**
   - On the server computer: `python build_client.py`
   - The executable and files will be created in the `dist` folder

2. **Copy files to client computer:**
   - Copy all files from `dist` folder to a USB drive or network share
   - Required files:
     - `ScreenRecorderClient.exe` (or `client\` folder with all files)
     - `install_client_service.bat`
     - `public_key.pem` (from `server/keys/` folder on server)

3. **Prepare the installation:**
   - Create a new folder: `C:\ShadowCapClient`
   - Copy all client files to this folder
   - Copy `public_key.pem` to `C:\ShadowCapClient\`
   - Create a new file named `license.key` in `C:\ShadowCapClient\`
   - Paste the license key from Step 2 into this file and save

4. **Run the installation script:**
   - Right-click on `install_client_service.bat`
   - Select **"Run as administrator"**
   - Enter the server IP address when prompted
   - Enter your Windows username and password when prompted
   - Wait for installation to complete

5. **What happens during installation:**
   - Creates virtual environment at `C:\ShadowCapClient\venv`
   - Installs Python dependencies
   - Creates `config.json` at `C:\ShadowCapClient\ScreenRecSvc\config.json`
   - Copies `license.key` and `public_key.pem` to installation directory
   - Installs Windows service (ScreenRecSvc) using NSSM
   - Configures service to run under your user account
   - Starts the service automatically

### Option B: Running Python Script Directly

1. **Install Python:**
   - Download from https://www.python.org/downloads/
   - Check **"Add Python to PATH"** during installation

2. **Install dependencies:**

   ```batch
   cd Desktop\ScreenRecorderApp\client
   pip install -r requirements.txt
   ```

3. **Prepare the license:**
   - Create `license.key` file in the client folder
   - Paste the license key from Step 2

4. **Run the client:**

   ```batch
   python screen_recorder.py
   ```

5. **Run as background process (optional):**

   ```batch
   pythonw screen_recorder.py
   ```

## Step 4: Verify Installation

1. **Check if the service is running:**

   ```batch
   sc query ScreenRecSvc
   ```

   You should see `STATE: RUNNING`

2. **Check the logs:**

   ```batch
   :: Main client log (most detailed)
   type "C:\ShadowCapClient\ScreenRecSvc\client.log"

   :: Crash log (if the client crashes unexpectedly)
   type "C:\ShadowCapClient\ScreenRecSvc\crash.log"
   ```

   You should see messages like "License validated successfully" and "Recording started"

3. **Verify on server:**
   - Go to the ShadowCap admin dashboard
   - You should see your client listed as "Active"

## Step 5: Configure the Client (Optional)

1. **Edit the configuration file:**
   - Press `Windows Key + R`
   - Type: `notepad "C:\ShadowCapClient\ScreenRecSvc\config.json"`
   - Press Enter

2. **Available settings:**

   ```json
   {
     "server_url": "http://your-server-ip:5000",
     "upload_interval": 300,
     "recording_fps": 10,
     "video_quality": 80,
     "chunk_duration": 60,
     "heartbeat_interval": 60,
     "max_offline_storage_mb": 1000,
     "retry_base_delay": 1.0,
     "retry_max_delay": 300.0,
     "upload_speed_limit_kbps": 0,
     "min_disk_space_mb": 500,
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

3. **Key settings:**

   | Setting                   | Description                         | Default                 |
   | ------------------------- | ----------------------------------- | ----------------------- |
   | `server_url`              | ShadowCap server URL                | `http://localhost:5000` |
   | `recording_fps`           | Frames per second                   | 10                      |
   | `chunk_duration`          | Seconds per video chunk             | 60                      |
   | `upload_speed_limit_kbps` | Upload throttle (0=unlimited)       | 0                       |
   | `min_disk_space_mb`       | Min free disk before recording      | 500                     |
   | `monitor_selection`       | Which monitor to record (1=primary) | 1                       |
   | `enable_audio`            | Record audio with video             | false                   |
   | `enable_compression`      | Compress videos before upload       | true                    |

4. **Restart the service after changes:**

   ```batch
   sc stop ScreenRecSvc
   sc start ScreenRecSvc
   ```

## Troubleshooting

### "License validation failed"

- Make sure `license.key` exists in `C:\ShadowCapClient`
- Check that the license key is correct (no extra spaces)
- Verify the license hasn't expired on the server

### Service won't start

- Check the logs:

  ```batch
  type "C:\ShadowCapClient\ScreenRecSvc\crash.log"
  type "C:\ShadowCapClient\ScreenRecSvc\client.log"
  ```

- Make sure Python is installed
- Try running manually: `python screen_recorder.py`

### Videos not uploading

- Check server is running: `sc query ScreenRecorderServer`
- Verify network connection to server
- Check server logs for errors

### Client doesn't shut down gracefully

The client supports graceful shutdown with signal handlers (SIGINT, SIGTERM, SIGHUP). When stopping:

- It finishes recording the current video chunk
- Waits for upload threads to complete
- Cleans up resources properly

If it doesn't stop:

- Force stop: `sc stop ScreenRecSvc`
- Check for hung processes: `tasklist | findstr python`

## Managing the Client

```batch
:: Start the client
sc start ScreenRecSvc

:: Stop the client
sc stop ScreenRecSvc

:: Check status
sc query ScreenRecSvc

:: View logs
type "C:\ShadowCapClient\ScreenRecSvc\client.log"

:: Uninstall
uninstall_client_service.bat
```

## What Happens After Installation

1. **Automatic Recording** — starts immediately, records in chunks (default: 1 minute each)
2. **Automatic Upload** — videos uploaded every 5 minutes; queued offline if server unreachable
3. **Heartbeat** — client sends heartbeat every 60 seconds; server tracks status
4. **Autostart** — service starts automatically on system boot, runs hidden

## Security Notes

- Client runs hidden (no visible window)
- Videos are stored locally before upload
- License is machine-specific (can't be used on other computers)
- All communication with server is authenticated
- Bandwidth throttling available via `upload_speed_limit_kbps`
- Disk space check prevents recording when storage is low
