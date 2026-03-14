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

3. **Get your machine ID:**

   ```batch
   python screen_recorder.py --get-id
   ```

4. **Copy the machine ID:**
   - You'll see output like: `Your Machine ID: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
   - Write down or copy this ID (you'll need it for the next step)

## Step 2: Generate a License

1. **Go to the server admin dashboard:**
   - Open your web browser
   - Go to: http://server-ip:5000/admin
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

1. **Download the client files:**
   - Go to the server admin dashboard
   - Click on the client with your machine ID
   - Download the client executable

2. **Prepare the installation:**
   - Create a new folder on the Desktop named "ScreenRecorderClient"
   - Copy the downloaded executable to this folder
   - Create a new file named `license.key` in this folder
   - Paste the license key from Step 2 into this file
   - Save the file

3. **Run the installation script:**
   - Right-click on `install.bat`
   - Select "Run as administrator"
   - If prompted by Windows, click "Yes" to allow
   - Wait for installation to complete

4. **What happens during installation:**
   - The client is installed to `C:\Program Files\ScreenRecSvc`
   - A Windows service is created
   - The service starts automatically
   - Recording begins immediately

## Step 4: Verify Installation

1. **Check if the service is running:**
   - Open Command Prompt as Administrator
   - Run: `sc query ScreenRecSvc`
   - You should see "STATE: RUNNING"

2. **Check the logs:**

   ```batch
   type "%APPDATA%\ScreenRecSvc\service.log"
   ```

   - You should see messages like "License validated successfully" and "Recording started"

3. **Verify on server:**
   - Go to the server admin dashboard
   - You should see your client listed
   - The client should show as "Active"

## Step 5: Configure the Client (Optional)

1. **Edit the configuration file:**
   - Press `Windows Key + R`
   - Type: `notepad "%APPDATA%\ScreenRecSvc\config.json"`
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
     "retry_max_delay": 300.0
   }
   ```

3. **Common settings to change:**
   - `server_url`: Change to your server's IP address
   - `recording_fps`: Lower for less CPU usage (e.g., 5)
   - `video_quality`: Lower for smaller files (e.g., 60)
   - `chunk_duration`: Longer for fewer files (e.g., 300 for 5 minutes)

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

- Make sure the `license.key` file exists in `C:\Program Files\ScreenRecSvc`
- Check that the license key is correct (no extra spaces or characters)
- Verify the license hasn't expired on the server

### Problem: "No license file found"

**Solution:**

- Create the `license.key` file manually
- Paste the license key from the server
- Save the file and restart the service

### Problem: Service won't start

**Solution:**

- Check the logs: `type "%APPDATA%\ScreenRecSvc\service.log"`
- Make sure Python is installed
- Try running the client manually: `python screen_recorder.py`

### Problem: Videos not uploading

**Solution:**

- Check server is running: `sc query ScreenRecorderServer`
- Verify network connection to server
- Check server logs for errors

### Problem: Can't access admin dashboard

**Solution:**

- Make sure you're using the correct server IP address
- Check if the server is running
- Try accessing: http://localhost:5000/admin (if on same computer)

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
type "%APPDATA%\ScreenRecSvc\service.log"
```

### Uninstall the client:

```batch
uninstall.bat
```

## What Happens After Installation

1. **Automatic Recording:**
   - The client starts recording immediately
   - Records screen in chunks (default: 1 minute each)
   - Saves videos to `%APPDATA%\ScreenRecSvc\recordings\`

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

## Next Steps

Now that your client is installed:

1. Monitor the client in the server admin dashboard
2. View uploaded videos
3. Download or delete videos as needed
4. Generate licenses for additional computers

See the [Server Installation Guide](SERVER_INSTALLATION_GUIDE.md) for server management.
