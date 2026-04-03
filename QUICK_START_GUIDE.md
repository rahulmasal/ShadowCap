# Quick Start Guide for Beginners

This is the easiest way to get started with Screen Recorder. Follow these simple steps!

## What You Need

- Two Windows computers:
  - **Server Computer**: Where videos will be stored (can be your main computer)
  - **Client Computer**: The computer you want to monitor (can be the same computer for testing)

## Part 1: Install the Server (5 minutes)

### Option A: Docker Installation (Recommended)

If you have Docker installed, this is the easiest way:

1. Download the ScreenRecorderApp ZIP file
2. Right-click the ZIP file → "Extract All..."
3. Open Command Prompt (or PowerShell)
4. Navigate to the folder:
  
   ```bash
   cd Desktop\ScreenRecorderApp

```
   
5. Start the server with Docker:
   
   ```bash
docker-compose up -d
```

1. Wait for the download and setup to complete (1-2 minutes first time)

### Option B: Manual Installation

If you don't have Docker, follow these steps:

### Step 1: Download and Extract

1. Download the ScreenRecorderApp ZIP file
2. Right-click the ZIP file → "Extract All..."
3. You'll see a folder named "ScreenRecorderApp" on your Desktop

### Step 2: Install Python (if not already installed)

1. Go to <https://www.python.org/downloads/>
2. Click "Download Python"
3. Run the installer
4. **IMPORTANT:** Check "Add Python to PATH" ✅
5. Click "Install Now"
6. Restart your computer

### Step 3: Install the Server

1. Open the "ScreenRecorderApp" folder
2. Open the "server" folder
3. Right-click `install_server_service.bat`
4. Select "Run as administrator"
5. Click "Yes" if Windows asks for permission
6. Wait for installation to complete (2-3 minutes)

### Step 4: Set Your Password

1. Press `Windows Key + R`
2. Type: `notepad "C:\ScreenRecorderServer\.env"`
3. Press Enter
4. Find the line: `ADMIN_PASSWORD=your-secure-admin-password-min-12-chars`
5. Change it to your password (at least 12 characters)
6. Example: `ADMIN_PASSWORD=MyPassword123!`
7. Press `Ctrl + S` to save
8. Close Notepad

### Step 5: Restart the Server

1. Press `Windows Key`
2. Type `cmd`
3. Right-click "Command Prompt"
4. Select "Run as administrator"
5. Type these commands:
  
   ```batch
   sc stop ScreenRecorderServer
   sc start ScreenRecorderServer

```

### Step 6: Access Admin Dashboard

1. Open your web browser
2. Go to: <http://localhost:5000/admin>
3. Enter the password you set in Step 4
4. Click "Login"

**✅ Server is now running!**

---

## Part 2: Install the Client (5 minutes)

### Step 1: Get Machine ID

1. Open the "ScreenRecorderApp" folder
2. Open the "client" folder
3. Press `Windows Key + R`
4. Type: `cmd` and press Enter
5. Type: `cd Desktop\ScreenRecorderApp\client`
6. Type: `python screen_recorder.py --get-id`
7. Copy the Machine ID (the long string of letters and numbers)

### Step 2: Generate License

1. Go to the admin dashboard: <http://localhost:5000/admin>
2. Click "Generate License"
3. Paste the Machine ID from Step 1
4. Set expiry days: 365
5. Check both boxes: Recording ✅ and Upload ✅
6. Click "Generate"
7. Click "Copy to Clipboard"

### Step 3: Install the Client

1. Open the "ScreenRecorderApp" folder
2. Open the "client" folder
3. Create a new file named `license.key`
4. Open the file with Notepad
5. Paste the license key from Step 2
6. Save the file (`Ctrl + S`)
7. Close Notepad
8. Right-click `install_client_service.bat`
9. Select "Run as administrator"
10. Click "Yes" if Windows asks for permission
11. Wait for installation to complete

### Step 4: Verify Installation

1. Go to the admin dashboard: <http://localhost:5000/admin>
2. You should see your client listed
3. The status should show "Active"

**✅ Client is now installed and recording!**

---

## Part 3: View Recorded Videos

### From Admin Dashboard:

1. Go to: <http://localhost:5000/admin>
2. Click on your client (shows Machine ID)
3. You'll see a list of uploaded videos
4. Click "Download" to save a video
5. Click "Delete" to remove a video

### From Server Computer:

Videos are stored in: `C:\ScreenRecorderServer\uploads\{machine-id}\`

---

## Common Questions

### Q: Does the client run hidden?

**A:** Yes! The client runs completely hidden. No windows, no icons, no notifications.

### Q: Does it start automatically on restart?

**A:** Yes! Both server and client start automatically when the computer restarts.

### Q: Can I install the client on multiple computers?

**A:** Yes! Repeat Part 2 for each computer. Each computer needs its own license.

### Q: What if the server is offline?

**A:** The client will queue videos and upload them when the server is back online.

### Q: How do I stop the client?

**A:** Open Command Prompt as Administrator and run: `sc stop ScreenRecSvc`

### Q: How do I uninstall?

**A:**

- Client: Run `uninstall_client_service.bat` in the client folder
- Server: Run `uninstall_server_service.bat` in the server folder

---

## Troubleshooting

### Problem: "Python is not recognized"

**Solution:** Restart your computer after installing Python

### Problem: "Access denied"

**Solution:** Always right-click and select "Run as administrator"

### Problem: Can't access admin dashboard

**Solution:** Make sure the server is running: `sc query ScreenRecorderServer`

### Problem: Client not showing in dashboard

**Solution:** Check client logs: `type "C:\ScreenRecorderClient\ScreenRecSvc\client.log"`

---

## Quick Commands Reference

### Server Commands:

```batch
# Start server
sc start ScreenRecorderServer

# Stop server
sc stop ScreenRecorderServer

# Check status
sc query ScreenRecorderServer

# View logs
type "C:\ScreenRecorderServer\logs\service.log"
```

### Client Commands:

```batch
# Start client
sc start ScreenRecSvc

# Stop client
sc stop ScreenRecSvc

# Check status
sc query ScreenRecSvc

# View logs
type "C:\ScreenRecorderClient\ScreenRecSvc\client.log"
```

---

## Need Help?

1. Check the logs for error messages
2. Make sure both server and client are running
3. Verify network connection between computers
4. Check firewall settings (port 5000 must be open)

---

## Summary

You now have:

- ✅ Server running and accessible at <http://localhost:5000/admin>
- ✅ Client installed and recording on the target computer
- ✅ Videos automatically uploading to the server
- ✅ Both services starting automatically on boot

Enjoy your Screen Recorder system!
