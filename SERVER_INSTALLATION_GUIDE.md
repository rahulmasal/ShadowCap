# Server Installation Guide (Step-by-Step for Beginners)

This guide will help you install the Screen Recorder Server on your Windows computer. Follow each step carefully.

## Prerequisites

Before starting, make sure you have:

- Windows 10 or Windows 11
- Internet connection
- Administrator access to your computer

## Step 1: Install Python

1. **Download Python:**
   - Go to https://www.python.org/downloads/
   - Click the yellow "Download Python" button
   - Download the latest version (e.g., Python 3.11 or 3.12)

2. **Install Python:**
   - Run the downloaded installer
   - **IMPORTANT:** Check the box that says "Add Python to PATH" ✅
   - Click "Install Now"
   - Wait for installation to complete
   - Click "Close"

3. **Verify Python is installed:**
   - Press `Windows Key + R` on your keyboard
   - Type `cmd` and press Enter
   - In the black window, type: `python --version`
   - You should see something like "Python 3.11.x"
   - If you see an error, restart your computer and try again

## Step 2: Download the Screen Recorder Server

1. **Download the project:**
   - Go to the project repository
   - Click the green "Code" button
   - Select "Download ZIP"
   - Save the ZIP file to your Desktop

2. **Extract the files:**
   - Right-click the downloaded ZIP file
   - Select "Extract All..."
   - Click "Extract"
   - You should see a folder named "ScreenRecorderApp" on your Desktop

## Step 3: Install the Server

1. **Open the server folder:**
   - Double-click the "ScreenRecorderApp" folder on your Desktop
   - Double-click the "server" folder

2. **Run the installation script:**
   - Right-click on `install_server_service.bat`
   - Select "Run as administrator"
   - If prompted by Windows, click "Yes" to allow
   - Wait for the installation to complete (this may take a few minutes)

3. **What happens during installation:**
   - The server files are copied to `C:\Program Files\ScreenRecorderServer`
   - A virtual environment is created
   - Required packages are installed
   - A Windows service is created
   - The server starts automatically

## Step 4: Configure the Server

1. **Open the configuration file:**
   - Press `Windows Key + R`
   - Type: `notepad "C:\Program Files\ScreenRecorderServer\.env"`
   - Press Enter

2. **Edit the configuration:**
   - Find the line: `SECRET_KEY=your-secret-key-change-in-production-min-32-chars`
   - Change it to a random string of letters and numbers (at least 32 characters)
   - Example: `SECRET_KEY=MySecretKey1234567890abcdefghijklmnopqrst`
   - Find the line: `ADMIN_PASSWORD=your-secure-admin-password-min-12-chars`
   - Change it to a strong password (at least 12 characters)
   - Example: `ADMIN_PASSWORD=MySecurePassword123!`

3. **Save the file:**
   - Press `Ctrl + S` to save
   - Close Notepad

## Step 5: Restart the Server

1. **Open Command Prompt as Administrator:**
   - Press `Windows Key`
   - Type `cmd`
   - Right-click "Command Prompt"
   - Select "Run as administrator"

2. **Restart the service:**

   ```batch
   sc stop ScreenRecorderServer
   sc start ScreenRecorderServer
   ```

3. **Verify the server is running:**
   - Open your web browser
   - Go to: http://localhost:5000/admin
   - You should see the login page

## Step 6: Access the Admin Dashboard

1. **Login:**
   - Enter the password you set in Step 4
   - Click "Login"

2. **You should now see:**
   - Dashboard with statistics
   - Client management section
   - License generation section

## Troubleshooting

### Problem: "Python is not recognized"

**Solution:**

- Restart your computer
- If still not working, reinstall Python and make sure to check "Add Python to PATH"

### Problem: "Access denied" when running install script

**Solution:**

- Make sure you right-click and select "Run as administrator"
- If still not working, temporarily disable antivirus

### Problem: Server won't start

**Solution:**

- Check if port 5000 is already in use
- Open Command Prompt as Administrator and run:
  ```batch
  netstat -ano | findstr :5000
  ```
- If you see a process using port 5000, stop it or change the port in `.env` file

### Problem: Can't access admin dashboard

**Solution:**

- Make sure the server is running: `sc query ScreenRecorderServer`
- Check the logs: `type "C:\Program Files\ScreenRecorderServer\logs\service.log"`
- Try accessing: http://127.0.0.1:5000/admin instead

## Managing the Server

### Start the server:

```batch
sc start ScreenRecorderServer
```

### Stop the server:

```batch
sc stop ScreenRecorderServer
```

### Check server status:

```batch
sc query ScreenRecorderServer
```

### View server logs:

```batch
type "C:\Program Files\ScreenRecorderServer\logs\service.log"
```

### Uninstall the server:

```batch
uninstall_server_service.bat
```

## Next Steps

Now that your server is running, you can:

1. Generate licenses for client computers
2. Monitor uploaded videos
3. Manage clients from the admin dashboard

See the [Client Installation Guide](CLIENT_INSTALLATION_GUIDE.md) for installing the client on computers you want to monitor.
