# Server Installation Guide (Step-by-Step for Beginners)

This guide will help you install the Screen Recorder Server on your Windows computer. Follow each step carefully.

## Prerequisites

Before starting, make sure you have:

- Windows 10 or Windows 11
- Internet connection
- Administrator access to your computer

## Installation Methods

You can install the server using either Docker (recommended for easy setup) or manual installation.

---

## Method 1: Docker Installation (Recommended)

Docker provides an easy way to run the server without installing Python or managing dependencies.

### Step 1: Install Docker

1. **Download Docker Desktop:**
   - Go to <https://www.docker.com/products/docker-desktop/>
   - Click "Download for Windows"
   - Run the installer
   - Follow the installation wizard
   - Restart your computer when prompted

2. **Verify Docker is installed:**
   - Open Command Prompt
   - Type: `docker --version`
   - You should see something like "Docker version 24.x.x"

### Step 2: Download the Screen Recorder Server

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

### Step 3: Start the Server with Docker

1. **Open Command Prompt:**
   - Press `Windows Key + R`
   - Type `cmd` and press Enter

2. **Navigate to the project folder:**

   ```bash
   cd Desktop\ScreenRecorderApp
   ```

3. **Start the server:**

   ```bash
   docker-compose up -d
   ```

4. **Wait for setup to complete:**
   - First time may take 2-3 minutes to download images
   - You'll see messages about downloading and starting containers

### Step 4: Configure the Server

1. **Create environment file:**

   ```bash
   cd server
   copy .env.example .env
   ```

2. **Edit the configuration:**
   - Open `.env` file in Notepad
   - Change `SECRET_KEY` to a random string (at least 32 characters)
   - Change `ADMIN_PASSWORD` to a strong password (at least 12 characters)
   - Save the file

3. **Restart the server:**
  
   ```bash
cd ..
   docker-compose restart

   ```

### Step 5: Access the Admin Dashboard

1. Open your web browser
2. Go to: <http://localhost:5000/admin>
3. Enter the password you set in Step 4
4. Click "Login"

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
```

---

## Method 2: Manual Installation

If you prefer not to use Docker, follow these steps:

## Step 1: Install Python

1. **Download Python:**
   - Go to <https://www.python.org/downloads/>
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
   - The server files are copied to `C:\ScreenRecorderServer`
   - A virtual environment is created
   - Required packages are installed
   - A Windows service is created
   - The server starts automatically

## Step 4: Configure the Server

1. **Open the configuration file:**
   - Press `Windows Key + R`
   - Type: `notepad "C:\ScreenRecorderServer\.env"`
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
   - Go to: <http://localhost:5000/admin>
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

### Docker Issues

#### Problem: "docker: command not found"

**Solution:**

- Make sure Docker Desktop is installed and running
- Restart your computer after installing Docker
- Check if Docker Desktop is running in your system tray

#### Problem: "Cannot connect to the Docker daemon"

**Solution:**

- Open Docker Desktop and wait for it to start
- Check if Docker Desktop shows "Docker Desktop is running"

#### Problem: Port 5000 already in use

**Solution:**

- Stop any existing server: `docker-compose down`
- Or change the port in `docker-compose.yml` (e.g., change "5000:5000" to "5001:5000")
- Then access via <http://localhost:5001/admin>

#### Problem: Container keeps restarting

**Solution:**

- Check logs: `docker-compose logs -f server`
- Make sure `.env` file exists and has correct values
- Check if volumes have correct permissions

### Manual Installation Issues

#### Problem: "Python is not recognized"

**Solution:**

- Restart your computer
- If still not working, reinstall Python and make sure to check "Add Python to PATH"

#### Problem: "Access denied" when running install script

**Solution:**

- Make sure you right-click and select "Run as administrator"
- If still not working, temporarily disable antivirus

#### Problem: Server won't start

**Solution:**

- Check if port 5000 is already in use
- Open Command Prompt as Administrator and run:
  
```batch
  netstat -ano | findstr :5000
  ```

- If you see a process using port 5000, stop it or change the port in `.env` file

#### Problem: Can't access admin dashboard

**Solution:**

- Make sure the server is running: `sc query ScreenRecorderServer`
- Check the logs: `type "C:\ScreenRecorderServer\logs\service.log"`
- Try accessing: <http://127.0.0.1:5000/admin> instead

## Managing the Server

### Docker Management

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
```

### Windows Service Management

```batch
# Start the server
sc start ScreenRecorderServer

# Stop the server
sc stop ScreenRecorderServer

# Check server status
sc query ScreenRecorderServer

# View server logs
type "C:\ScreenRecorderServer\logs\service.log"

# Uninstall the server
uninstall_server_service.bat
```

## Next Steps

Now that your server is running, you can:

1. Generate licenses for client computers
2. Monitor uploaded videos
3. Manage clients from the admin dashboard

See the [Client Installation Guide](CLIENT_INSTALLATION_GUIDE.md) for installing the client on computers you want to monitor.
