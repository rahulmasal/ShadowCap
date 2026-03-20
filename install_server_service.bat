@echo off

:: ---------------------------------------------------------------
:: Re-launch inside a persistent cmd window so the console does
:: NOT close automatically when the script finishes or errors out.
:: The _KEEP_OPEN flag prevents infinite re-launch loops.
:: ---------------------------------------------------------------
if not defined _KEEP_OPEN (
    set _KEEP_OPEN=1
    cmd /k ""%~f0""
    exit /b
)

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
set INSTALL_DIR=C:\ScreenRecorderServer
set SCRIPT_DIR=%~dp0
set SERVER_DIR=%SCRIPT_DIR%server
set SHARED_DIR=%SCRIPT_DIR%shared
set NSSM=%SCRIPT_DIR%nssm.exe

echo Step 1: Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\uploads" mkdir "%INSTALL_DIR%\uploads"
if not exist "%INSTALL_DIR%\clients" mkdir "%INSTALL_DIR%\clients"
if not exist "%INSTALL_DIR%\keys" mkdir "%INSTALL_DIR%\keys"
if not exist "%INSTALL_DIR%\licenses" mkdir "%INSTALL_DIR%\licenses"
if not exist "%INSTALL_DIR%\instance" mkdir "%INSTALL_DIR%\instance"
echo Done.
pause

echo Step 2: Copying server files...
xcopy /E /I /Y "%SERVER_DIR%\*" "%INSTALL_DIR%\"
echo Step 2b: Copying shared files...
xcopy /E /I /Y "%SHARED_DIR%\*" "%INSTALL_DIR%\shared\"
echo Done.
pause

echo Step 3: Creating virtual environment...
if not exist "%INSTALL_DIR%\venv" (
    python -m venv "%INSTALL_DIR%\venv"
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
pause

echo Step 4: Installing dependencies...
"%INSTALL_DIR%\venv\Scripts\pip.exe" install -r "%INSTALL_DIR%\requirements.txt"
echo Done.
pause

echo Step 5: Creating .env file...
if not exist "%INSTALL_DIR%\.env" (
    copy "%INSTALL_DIR%\.env.example" "%INSTALL_DIR%\.env"
    echo .env file created.
    echo IMPORTANT: Edit %INSTALL_DIR%\.env to set your SECRET_KEY and ADMIN_PASSWORD
) else (
    echo .env file already exists.
)
pause

echo Step 6: Downloading NSSM...
if not exist "%NSSM%" (
    echo NSSM not found. Attempting to download...
    curl -L --max-time 30 -o "%SCRIPT_DIR%nssm.zip" https://nssm.cc/release/nssm-2.24.zip
    if not exist "%SCRIPT_DIR%nssm.zip" (
        echo ERROR: Failed to download NSSM.
        echo.
        echo Please download NSSM manually:
        echo 1. Go to https://nssm.cc/download
        echo 2. Download nssm-2.24.zip
        echo 3. Extract nssm.exe from the win64 folder
        echo 4. Place nssm.exe in: %SCRIPT_DIR%
        echo 5. Run this script again
        pause
        exit /b 1
    )
    echo Extracting NSSM...
    tar -xf "%SCRIPT_DIR%nssm.zip" -C "%SCRIPT_DIR%"
    if not exist "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" (
        echo ERROR: Failed to extract NSSM properly.
        echo.
        echo Please download NSSM manually:
        echo 1. Go to https://nssm.cc/download
        echo 2. Download nssm-2.24.zip
        echo 3. Extract nssm.exe from the win64 folder
        echo 4. Place nssm.exe in: %SCRIPT_DIR%
        echo 5. Run this script again
        if exist "%SCRIPT_DIR%nssm.zip" del "%SCRIPT_DIR%nssm.zip"
        pause
        exit /b 1
    )
    copy "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" "%SCRIPT_DIR%nssm.exe"
    rmdir /s /q "%SCRIPT_DIR%nssm-2.24"
    del "%SCRIPT_DIR%nssm.zip"
    echo NSSM downloaded and extracted successfully.
) else (
    echo NSSM already exists, skipping download.
)

echo Copying nssm.exe to installation directory...
copy /Y "%SCRIPT_DIR%nssm.exe" "%INSTALL_DIR%\nssm.exe"
set NSSM=%INSTALL_DIR%\nssm.exe
echo NSSM will run from: %NSSM%
pause

echo Step 7: Removing any existing service before installing...
echo Stopping existing service (errors are normal if service does not exist)...
"%NSSM%" stop ScreenRecorderServer
timeout /t 2 /nobreak >nul
echo Removing existing service (errors are normal if service does not exist)...
"%NSSM%" remove ScreenRecorderServer confirm
timeout /t 3 /nobreak >nul

echo Ensuring directories exist and granting write permissions to all users...
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
icacls "%INSTALL_DIR%\logs" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\uploads" mkdir "%INSTALL_DIR%\uploads"
icacls "%INSTALL_DIR%\uploads" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\clients" mkdir "%INSTALL_DIR%\clients"
icacls "%INSTALL_DIR%\clients" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\keys" mkdir "%INSTALL_DIR%\keys"
icacls "%INSTALL_DIR%\keys" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\licenses" mkdir "%INSTALL_DIR%\licenses"
icacls "%INSTALL_DIR%\licenses" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\instance" mkdir "%INSTALL_DIR%\instance"
icacls "%INSTALL_DIR%\instance" /grant "Users:(OI)(CI)F" /T >nul 2>&1

echo Creating empty log files if they don't exist...
if not exist "%INSTALL_DIR%\logs\server.log" type nul > "%INSTALL_DIR%\logs\server.log"
if not exist "%INSTALL_DIR%\logs\crash.log" type nul > "%INSTALL_DIR%\logs\crash.log"
icacls "%INSTALL_DIR%\logs\server.log" /grant "Users:(OI)(CI)F" >nul 2>&1
icacls "%INSTALL_DIR%\logs\crash.log" /grant "Users:(OI)(CI)F" >nul 2>&1
echo Step 7 complete.
pause

echo Step 8: Installing Windows service...
echo NSSM path used: %NSSM%
echo Python path:   %INSTALL_DIR%\venv\Scripts\python.exe
echo Script path:   %INSTALL_DIR%\app.py
echo.

echo Installing NSSM service...
"%NSSM%" install ScreenRecorderServer "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\app.py"
if errorlevel 1 (
    echo ERROR: NSSM install failed.
    echo Make sure nssm.exe is present at: %NSSM%
    echo Make sure you are running this script as Administrator.
    pause
    exit /b 1
)
echo NSSM service registered OK.

echo Configuring service settings...
"%NSSM%" set ScreenRecorderServer AppDirectory "%INSTALL_DIR%"
"%NSSM%" set ScreenRecorderServer DisplayName "Screen Recorder Server"
"%NSSM%" set ScreenRecorderServer Description "Screen Recorder Server Application"
"%NSSM%" set ScreenRecorderServer Start SERVICE_AUTO_START
"%NSSM%" set ScreenRecorderServer AppStdout "%INSTALL_DIR%\logs\service.log"
"%NSSM%" set ScreenRecorderServer AppStderr "%INSTALL_DIR%\logs\service_error.log"
"%NSSM%" set ScreenRecorderServer AppRotateFiles 1
"%NSSM%" set ScreenRecorderServer AppRotateOnline 1
"%NSSM%" set ScreenRecorderServer AppRotateSeconds 86400
"%NSSM%" set ScreenRecorderServer AppRotateBytes 1048576
"%NSSM%" set ScreenRecorderServer AppExit Default Restart
"%NSSM%" set ScreenRecorderServer AppExit 0 Exit
echo Service settings applied.
echo Step 8 complete - Service installed.
pause

echo Step 9: Starting service...
"%NSSM%" start ScreenRecorderServer
if %errorLevel% neq 0 (
    echo ERROR: Failed to start service. Error code: %errorLevel%
    echo Check the service logs at: %INSTALL_DIR%\logs\
    pause
    exit /b 1
)
echo Service started.
pause

echo.
echo ================================================
echo   Installation Complete!
echo ================================================
echo.
echo Service Name: ScreenRecorderServer
echo Installation Directory: %INSTALL_DIR%
echo.
echo Log Files:
echo   - Service stdout: %INSTALL_DIR%\logs\service.log
echo   - Service stderr: %INSTALL_DIR%\logs\service_error.log
echo   - Server log:     %INSTALL_DIR%\logs\server.log
echo   - Crash log:      %INSTALL_DIR%\logs\crash.log
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
echo To view logs:
echo   - type "%INSTALL_DIR%\logs\service.log"
echo   - type "%INSTALL_DIR%\logs\server.log"
echo.
echo To uninstall, run: uninstall_server_service.bat
echo ================================================
echo.
pause