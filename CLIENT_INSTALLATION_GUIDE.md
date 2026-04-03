# Client Installation Guide (Step-by-Step for Beginners)

This guide will help you install the Screen Recorder Client on a Windows computer you want to monitor. Follow each step carefully.

## Prerequisites

Before starting, make sure you have:

- Windows 10 or Windows 11
- Internet connection
- Administrator access to the computer
- The server is already installed and running (see [Server Installation Guide](SERVER_INSTALLATION_GUIDE.md))

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

5. **Copy the machine ID:**
   - You'll see output like: `Your Machine ID: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
   - Write down or copy this ID (you'll need it for the next step)

## Step 2: Generate a License

1. **Go to the server admin dashboard:**
   - Open your web browser
   - Go to: <http://server-ip:5000/admin>
   - (Replace "server-ip" with your server's IP address)
   - Login with your admin password

2. **Generate a license:**
   - Click "Generate License" button
   - Paste the machine ID from Step 1
   - Set expiry days (e.g., 365 for 1 year)
   - Check the features you want:
     - ✅ Recording
     - ✅ Upload
   - Click "Generate"

3. **Copy the license key:**
   - You'll see a long string of characters
   - Click "Copy to Clipboard" button
   - Save this license key (you'll need it for installation)

## Step 3: Install the Client

### Option A: Using Pre-built Executable

1. **Build the client executable:**
   - On the server computer, navigate to the ScreenRecorderApp folder
   - Run: `python build_client.py`
   - The executable and files will be created in the `dist` folder

2. **Copy files to client computer:**
   - Copy all files from `dist` folder to a USB drive or network share
   - Required files:
     - `ScreenRecorderClient.exe` (or `client\` folder with all files)
     - `install_client_service.bat`
     - `public_key.pem` (from `server/keys/` folder on server)

3. **Prepare the installation:**
   - Create a new folder: `C:\ScreenRecorderClient`
   - Copy all client files to this folder (screen_recorder.py, requirements.txt, shared/, etc.)
   - Copy `public_key.pem` to `C:\ScreenRecorderClient\`
   - Create a new file named `license.key` in `C:\ScreenRecorderClient\`
   - Paste the license key from Step 2 into this file
   - Save the file

4. **Run the installation script:**
   - Right-click on `install_client_service.bat`
   - Select "Run as administrator"
   - If prompted by Windows, click "Yes" to allow
   - Enter the server IP address when prompted
   - Enter your Windows username and password when prompted (so the service can capture the screen)
   - Wait for installation to complete

5. **What happens during installation:**
   - Creates virtual environment at `C:\ScreenRecorderClient\venv`
   - Installs Python dependencies
   - Creates config.json at `C:\ScreenRecorderClient\ScreenRecSvc\config.json`
   - Copies license.key and public_key.pem to installation directory
   - Installs Windows service (ScreenRecSvc) using NSSM
   - Configures service to run under your user account (required for screen capture)
   - Starts the service automatically

### Option B: Running Python Script Directly

If you prefer to run the client as a Python script:

1. **Install Python:**
   - Download from <https://www.python.org/downloads/>
   - Check "Add Python to PATH" during installation

2. **Install dependencies:**

   ```batch
   cd Desktop\ScreenRecorderApp\client
   pip install -r requirements.txt
   ```

3. **Prepare the license:**
   - Create `license.key` file in the client folder
   - Paste the license key from Step 2
   - Save the file

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
   - Open Command Prompt as Administrator
   - Run: `sc query ScreenRecSvc`
   - You should see "STATE: RUNNING"

2. **Check the logs:**

   There are multiple log files to check:

   ```batch
   :: Main client log (most detailed)
   type "C:\ScreenRecorderClient\ScreenRecSvc\client.log"

   :: Crash log (if the client crashes unexpectedly)
   type "C:\ScreenRecorderClient\ScreenRecSvc\crash.log"

   :: Service stdout (captured by NSSM)
   type "C:\ScreenRecorderClient\logs\service.log"

   :: Service stderr (errors captured by NSSM)
   type "C:\ScreenRecorderClient\logs\service_error.log"
   ```

- You should see messages like "License validated successfully" and "Recording started"

1. **Verify on server:**
   - Go to the server admin dashboard
   - You should see your client listed
   - The client should show as "Active"

## Step 5: Configure the Client (Optional)

1. **Edit the configuration file:**
   - Press `Windows Key + R`
   - Type: `notepad "C:\ScreenRecorderClient\ScreenRecSvc\config.json"`
   - Press Enter

2. **Available settings:**

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

3. **Common settings to change:**
   - `server_url`: Change to your server's IP address
   - `recording_fps`: Lower for less CPU usage (e.g., 5)
   - `video_quality`: Lower for smaller files (e.g., 60)
   - `chunk_duration`: Longer for fewer files (e.g., 300 for 5 minutes)
   - `monitor_selection`: Which monitor to record (1=primary, 2=secondary)
   - `region_x`, `region_y`: Offset for recording a specific region
   - `region_width`, `region_height`: Dimensions of recording region (0=full screen)
   - `enable_audio`: Set to `true` to record audio (requires PyAudio)
   - `enable_compression`: Set to `true` for smaller video files
   - `compression_quality`: FFmpeg CRF value (lower=better quality, 18-28 recommended)

4. **Save the file:**
   - Press `Ctrl + S`
   - Close Notepad

5. **Restart the service:**
  
   ```batch
   sc stop ScreenRecSvc
   sc start ScreenRecSvc

```

## Troubleshooting

### Problem: "License validation failed"

**Solution:**

- Make sure the `license.key` file exists in `C:\ScreenRecorderClient`
- Check that the license key is correct (no extra spaces or characters)
- Verify the license hasn't expired on the server

### Problem: "No license file found"

**Solution:**

- Create the `license.key` file manually
- Paste the license key from the server
- Save the file and restart the service

### Problem: Service won't start

**Solution:**

- Check the logs:

  ```batch
  type "C:\ScreenRecorderClient\ScreenRecSvc\client.log"
  type "C:\ScreenRecorderClient\ScreenRecSvc\crash.log"
  type "C:\ScreenRecorderClient\logs\service.log"
  ```

- Make sure Python is installed
- Try running the client manually: `python screen_recorder.py`

### Problem: Client crashes or no logs visible

**Solution:**

- Check ALL log files in order (crash log first for uncaught exceptions):

  ```batch
  :: 1. Crash log (uncaught exceptions - check this FIRST if client crashes immediately)
  type "C:\ScreenRecorderClient\ScreenRecSvc\crash.log"

  :: 2. Client log (detailed runtime logging)
  type "C:\ScreenRecorderClient\ScreenRecSvc\client.log"

  :: 3. Service stdout (captured by NSSM)
  type "C:\ScreenRecorderClient\logs\service.log"

  :: 4. Service stderr (errors captured by NSSM)
  type "C:\ScreenRecorderClient\logs\service_error.log"
  ```

- Common causes:
  - Missing dependencies: Run `pip install -r requirements.txt` in the installation directory
  - Permission issues: The installer now grants write access to all users for logs/, ScreenRecSvc/, recordings/, and offline_queue/ directories
  - License issues: Verify `license.key` and `public_key.pem` exist in `C:\ScreenRecorderClient\`
  - Service account: Ensure the service is configured to log on as a user account (not LocalSystem) for screen capture to work

### Problem: Client doesn't shut down gracefully

**Solution:**

- The client now supports graceful shutdown with signal handlers (SIGINT, SIGTERM, SIGHUP)
- When stopping the service, the client will:
  - Finish recording the current video chunk
  - Wait for upload threads to complete
  - Clean up resources properly
- If the client doesn't stop gracefully:
  - Check logs for shutdown messages
  - Force stop: `sc stop ScreenRecSvc` (Windows will force stop after timeout)
  - Check for hung processes: `tasklist | findstr python`

### Problem: License validation errors

**Solution:**

The client uses a comprehensive exception system for better error handling:

- **LicenseExpiredError**: License has expired - generate a new license
- **LicenseInvalidError**: License signature is invalid - regenerate license
- **LicenseMachineMismatchError**: License is for a different machine - generate license with correct machine ID

Check the client log for specific error messages:

```batch
type "C:\ScreenRecorderClient\ScreenRecSvc\client.log" | findstr "License"
```

### Problem: Videos not uploading

**Solution:**

- Check server is running: `sc query ScreenRecorderServer`
- Verify network connection to server
- Check server logs for errors

### Problem: Can't access admin dashboard

**Solution:**

- Make sure you're using the correct server IP address
- Check if the server is running
- Try accessing: <http://localhost:5000/admin> (if on same computer)

## Managing the Client

### Start the client:

```batch
sc start ScreenRecSvc
```

### Stop the client:

```batch
sc stop ScreenRecSvc
```

### Check client status:

```batch
sc query ScreenRecSvc
```

### View client logs:

```batch
type "C:\ScreenRecorderClient\logs\service.log"
```

### Uninstall the client:

```batch
uninstall_client_service.bat
```

## What Happens After Installation

1. **Automatic Recording:**
   - The client starts recording immediately
   - Records screen in chunks (default: 1 minute each)
   - Saves videos to `C:\ScreenRecorderClient\ScreenRecSvc\recordings\`

2. **Automatic Upload:**
   - Videos are uploaded to the server every 5 minutes
   - If server is unreachable, videos are queued
   - When server is available, queued videos are uploaded

3. **Heartbeat:**
   - Client sends heartbeat to server every 60 seconds
   - Server tracks client status
   - You can see active clients in admin dashboard

4. **Autostart:**
   - The client service starts automatically on system boot
   - No user interaction required
   - Runs hidden in the background

## Security Notes

- The client runs hidden (no visible window)
- Videos are stored locally before upload
- License is machine-specific (can't be used on other computers)
- All communication with server is authenticated

## Recent Improvements

### Graceful Shutdown

The client now handles shutdown signals properly:

- **SIGINT** (Ctrl+C): Graceful shutdown when running manually
- **SIGTERM**: Service stop signal
- **SIGHUP**: Terminal close signal

When shutting down, the client will:

1. Finish recording the current video chunk
2. Wait for upload threads to complete
3. Clean up resources properly
4. Log shutdown completion

### Custom Exception Handling

The client uses a comprehensive exception system for better error reporting:

| Exception                   | Description                        |
| --------------------------- | ---------------------------------- |
| LicenseExpiredError         | License has expired                |
| LicenseInvalidError         | License signature is invalid       |
| LicenseMachineMismatchError | License is for a different machine |
| UploadFailedError           | Video upload failed                |
| RecordingStartError         | Failed to start recording          |
| RecordingStopError          | Failed to stop recording           |

Check the client log for specific error messages when troubleshooting.

### Configuration Options

New configuration options available:

| Option              | Description                   | Default         |
| ------------------- | ----------------------------- | --------------- |
| enable_audio        | Record audio with video       | false           |
| audio_sample_rate   | Audio sample rate (Hz)        | 44100           |
| enable_compression  | Compress videos before upload | true            |
| compression_quality | FFmpeg CRF value (18-28)      | 23              |
| monitor_selection   | Which monitor to record       | 1 (primary)     |
| region_x            | Recording region X offset     | 0               |
| region_y            | Recording region Y offset     | 0               |
| region_width        | Recording region width        | 0 (full screen) |
| region_height       | Recording region height       | 0 (full screen) |

## Next Steps

Now that your client is installed:

1. Monitor the client in the server admin dashboard
2. View uploaded videos
3. Download or delete videos as needed
4. Generate licenses for additional computers

See the [Server Installation Guide](SERVER_INSTALLATION_GUIDE.md) for server management.
