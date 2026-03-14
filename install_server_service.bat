@echo off
echo ================================================
echo   Screen Recorder Server - Windows Service Installer
echo ================================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Set paths
set INSTALL_DIR=%ProgramFiles%\ScreenRecorderServer
set SCRIPT_DIR=%~dp0
set SERVER_DIR=%SCRIPT_DIR%server

:: Create installation directory
echo Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

:: Copy server files
echo Copying server files...
xcopy /E /I /Y "%SERVER_DIR%\*" "%INSTALL_DIR%\"

:: Create virtual environment if it doesn't exist
if not exist "%INSTALL_DIR%\venv" (
    echo Creating virtual environment...
    python -m venv "%INSTALL_DIR%\venv"
)

:: Activate virtual environment and install dependencies
echo Installing dependencies...
call "%INSTALL_DIR%\venv\Scripts\activate.bat"
pip install -r "%INSTALL_DIR%\requirements.txt" -q

:: Create .env file if it doesn't exist
if not exist "%INSTALL_DIR%\.env" (
    echo Creating default .env file...
    copy "%INSTALL_DIR%\.env.example" "%INSTALL_DIR%\.env"
    echo.
    echo IMPORTANT: Edit %INSTALL_DIR%\.env to set your SECRET_KEY and ADMIN_PASSWORD
    echo.
)

:: Download NSSM if not present
if not exist "%SCRIPT_DIR%nssm.exe" (
    echo Downloading NSSM (Non-Sucking Service Manager)...
    curl -L -o "%SCRIPT_DIR%nssm.zip" https://nssm.cc/release/nssm-2.24.zip 2>nul
    if exist "%SCRIPT_DIR%nssm.zip" (
        tar -xf "%SCRIPT_DIR%nssm.zip" -C "%SCRIPT_DIR%" 2>nul
        copy "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" "%SCRIPT_DIR%nssm.exe" 2>nul
        rmdir /s /q "%SCRIPT_DIR%nssm-2.24" 2>nul
        del "%SCRIPT_DIR%nssm.zip" 2>nul
    ) else (
        echo WARNING: Could not download NSSM. Please download manually from https://nssm.cc
        echo Place nssm.exe in %SCRIPT_DIR% and run this script again.
        pause
        exit /b 1
    )
)

:: Install Windows service
echo Installing Windows service...
"%SCRIPT_DIR%nssm.exe" install ScreenRecorderServer "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\app.py"
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppDirectory "%INSTALL_DIR%"
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer DisplayName "Screen Recorder Server"
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer Description "Screen Recorder Server Application"
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer Start SERVICE_AUTO_START
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppStdout "%INSTALL_DIR%\logs\service.log"
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppStderr "%INSTALL_DIR%\logs\service_error.log"
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppRotateFiles 1
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppRotateOnline 1
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppRotateSeconds 86400
"%SCRIPT_DIR%nssm.exe" set ScreenRecorderServer AppRotateBytes 1048576

:: Start service
echo Starting service...
"%SCRIPT_DIR%nssm.exe" start ScreenRecorderServer

echo.
echo ================================================
echo   Installation Complete!
echo ================================================
echo.
echo Service Name: ScreenRecorderServer
echo Installation Directory: %INSTALL_DIR%
echo Logs Directory: %INSTALL_DIR%\logs
echo.
echo The server will start automatically on system boot.
echo.
echo Admin Dashboard: http://localhost:5000/admin
echo.
echo To manage the service:
echo   - Start:   sc start ScreenRecorderServer
echo   - Stop:    sc stop ScreenRecorderServer
echo   - Status:  sc query ScreenRecorderServer
echo.
echo To uninstall, run: uninstall_server_service.bat
echo ================================================
pause
