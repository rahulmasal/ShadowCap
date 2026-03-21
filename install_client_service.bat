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
echo   Screen Recorder Client - Windows Service Installer
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
set INSTALL_DIR=C:\ScreenRecorderClient
set SCRIPT_DIR=%~dp0
set CLIENT_DIR=%SCRIPT_DIR%client
set SHARED_DIR=%SCRIPT_DIR%shared
set NSSM=%SCRIPT_DIR%nssm.exe

echo Step 1: Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\ScreenRecSvc" mkdir "%INSTALL_DIR%\ScreenRecSvc"
if not exist "%INSTALL_DIR%\ScreenRecSvc\recordings" mkdir "%INSTALL_DIR%\ScreenRecSvc\recordings"
if not exist "%INSTALL_DIR%\ScreenRecSvc\offline_queue" mkdir "%INSTALL_DIR%\ScreenRecSvc\offline_queue"
echo Done.
pause

echo Step 2: Copying client files...
xcopy /E /I /Y "%CLIENT_DIR%\*" "%INSTALL_DIR%\"
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

echo Step 5: Configuring Server IP...
set /p SERVER_IP="Enter Server IP address (e.g., 192.168.1.100): "
if "%SERVER_IP%"=="" (
    set SERVER_IP=localhost
)
echo Creating config file with server URL: http://%SERVER_IP%:5000
set CONFIG_DIR=%INSTALL_DIR%\ScreenRecSvc
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
(
    echo {"server_url": "http://%SERVER_IP%:5000"}
) > "%CONFIG_DIR%\config.json"
type "%CONFIG_DIR%\config.json"
echo Config file written to: %CONFIG_DIR%\config.json
echo Done.
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

echo Step 7: Copying license and public key if present...
if exist "%SCRIPT_DIR%license.key" (
    copy /Y "%SCRIPT_DIR%license.key" "%INSTALL_DIR%\license.key"
    echo license.key copied to %INSTALL_DIR%.
) else (
    echo WARNING: license.key not found in %SCRIPT_DIR%
    echo Place license.key at %INSTALL_DIR%\license.key before starting the service.
)
if exist "%SCRIPT_DIR%public_key.pem" (
    copy /Y "%SCRIPT_DIR%public_key.pem" "%INSTALL_DIR%\public_key.pem"
    echo public_key.pem copied to %INSTALL_DIR%.
) else (
    echo WARNING: public_key.pem not found in %SCRIPT_DIR%
    echo Get it from the server at C:\ScreenRecorderServer\keys\public_key.pem
)
pause

echo Step 8: Removing any existing service before installing...
echo Stopping existing service (errors are normal if service does not exist)...
"%NSSM%" stop ScreenRecSvc
timeout /t 2 /nobreak >nul
echo Removing existing service (errors are normal if service does not exist)...
"%NSSM%" remove ScreenRecSvc confirm
timeout /t 3 /nobreak >nul

echo Ensuring logs directory exists and granting write permissions to all users...
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
icacls "%INSTALL_DIR%\logs" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\ScreenRecSvc" mkdir "%INSTALL_DIR%\ScreenRecSvc"
icacls "%INSTALL_DIR%\ScreenRecSvc" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\ScreenRecSvc\recordings" mkdir "%INSTALL_DIR%\ScreenRecSvc\recordings"
icacls "%INSTALL_DIR%\ScreenRecSvc\recordings" /grant "Users:(OI)(CI)F" /T >nul 2>&1
if not exist "%INSTALL_DIR%\ScreenRecSvc\offline_queue" mkdir "%INSTALL_DIR%\ScreenRecSvc\offline_queue"
icacls "%INSTALL_DIR%\ScreenRecSvc\offline_queue" /grant "Users:(OI)(CI)F" /T >nul 2>&1

echo Creating empty log files if they don't exist...
if not exist "%INSTALL_DIR%\ScreenRecSvc\client.log" type nul > "%INSTALL_DIR%\ScreenRecSvc\client.log"
if not exist "%INSTALL_DIR%\ScreenRecSvc\crash.log" type nul > "%INSTALL_DIR%\ScreenRecSvc\crash.log"
icacls "%INSTALL_DIR%\ScreenRecSvc\client.log" /grant "Users:(OI)(CI)F" >nul 2>&1
icacls "%INSTALL_DIR%\ScreenRecSvc\crash.log" /grant "Users:(OI)(CI)F" >nul 2>&1
echo Step 8 complete.
pause

echo Step 9: Installing Windows service...
echo NSSM path used: %NSSM%
echo Python path:   %INSTALL_DIR%\venv\Scripts\python.exe
echo Script path:   %INSTALL_DIR%\screen_recorder.py
echo.

:: -----------------------------------------------------------------------
:: Configure the service to run under the currently logged-in user account
:: instead of SYSTEM.  Windows services that run as SYSTEM are isolated in
:: Session 0 and cannot access the interactive desktop / display.
:: Running as the real user account places the service in the user session
:: so that mss / screen-capture APIs see the actual screen.
:: -----------------------------------------------------------------------
echo.
echo IMPORTANT: The service must run as YOUR Windows user account (not SYSTEM)
echo so that it can capture the screen.  Please enter your Windows credentials.
echo.
echo Username format examples:
echo   .\RAHUL          (local account, dot-backslash prefix)
echo   Wings\RAHUL      (local account with computer name)
echo   DOMAIN\RAHUL     (domain account)
echo.
echo NOTE: If your account has NO password, Windows blocks services from running.
echo       The installer can automatically allow blank passwords for services.
echo.

:: Get username - use simple set /p without delayed expansion
set SVC_USER=
set /p SVC_USER="Enter Windows username (e.g. .\RAHUL or Wings\RAHUL): "
echo.

:: Check if username is empty and branch accordingly
if "%SVC_USER%"=="" goto :use_localsystem
goto :ask_password

:use_localsystem
echo No username entered. Service will run as LocalSystem (screen capture may not work).
set SVC_USER=LocalSystem
set SVC_PASS=
goto :install_service

:ask_password
echo Username: %SVC_USER%
echo.
echo If your account has NO password, just press Enter when asked for password.
echo (The installer will automatically configure Windows to allow blank password)
echo.
set SVC_PASS=
set /p SVC_PASS="Enter Windows password for %SVC_USER% (press Enter if no password): "
echo.

:: If blank password, configure Windows to allow blank passwords for network/service logon
if "%SVC_PASS%"=="" (
    echo.
    echo Blank password detected. Configuring Windows to allow blank passwords...
    echo This modifies: Accounts: Limit local account use of blank passwords to console logon only
    echo.
    
    :: Disable the "Limit local account use of blank passwords to console logon only" policy
    reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v "DisableAutomaticRestartSignOn" /t REG_DWORD /d 1 /f >nul 2>&1
    
    :: Main policy: Allow blank passwords for network/service logon
    reg add "HKLM\SYSTEM\CurrentControlSet\Control\Lsa" /v "LimitBlankPasswordUse" /t REG_DWORD /d 0 /f >nul 2>&1
    
    if %errorLevel%==0 (
        echo SUCCESS: Windows policy updated to allow blank passwords for services.
        echo.
        echo Registry key modified:
        echo HKLM\SYSTEM\CurrentControlSet\Control\Lsa\LimitBlankPasswordUse = 0
        echo.
    ) else (
        echo WARNING: Failed to update Windows policy. You may need to do this manually:
        echo.
        echo Method 1 - Using Registry Editor:
        echo   1. Open regedit
        echo   2. Navigate to: HKLM\SYSTEM\CurrentControlSet\Control\Lsa
        echo   3. Set LimitBlankPasswordUse to 0
        echo.
        echo Method 2 - Using Local Security Policy:
        echo   1. Open secpol.msc
        echo   2. Navigate to: Local Policies ^> Security Options
        echo   3. Find "Accounts: Limit local account use of blank passwords..."
        echo   4. Set to Disabled
        echo.
    )
)
pause
goto :install_service

:install_service
echo.
pause

echo Installing NSSM service...
"%NSSM%" install ScreenRecSvc "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\screen_recorder.py"
if errorlevel 1 (
    echo ERROR: NSSM install failed.
    echo Make sure nssm.exe is present at: %NSSM%
    echo Make sure you are running this script as Administrator.
    pause
    exit /b 1
)
echo NSSM service registered OK.

echo Configuring service settings...
"%NSSM%" set ScreenRecSvc AppDirectory "%INSTALL_DIR%"
"%NSSM%" set ScreenRecSvc DisplayName "Screen Recording Service"
"%NSSM%" set ScreenRecSvc Description "Automatic screen recording service"
"%NSSM%" set ScreenRecSvc Start SERVICE_AUTO_START
"%NSSM%" set ScreenRecSvc AppStdout "%INSTALL_DIR%\logs\service.log"
"%NSSM%" set ScreenRecSvc AppStderr "%INSTALL_DIR%\logs\service_error.log"
"%NSSM%" set ScreenRecSvc AppRotateFiles 1
"%NSSM%" set ScreenRecSvc AppRotateOnline 1
"%NSSM%" set ScreenRecSvc AppRotateSeconds 86400
"%NSSM%" set ScreenRecSvc AppRotateBytes 1048576
"%NSSM%" set ScreenRecSvc AppExit Default Restart
"%NSSM%" set ScreenRecSvc AppExit 0 Exit
echo Service settings applied.

:: Set the service logon account so it runs in the user's desktop session
:: Use a separate flag to avoid backslash/dot in SVC_USER breaking the IF comparison
if "%SVC_USER%"=="LocalSystem" goto :skip_logon_config
    echo Configuring service to log on as: %SVC_USER%
    "%NSSM%" set ScreenRecSvc ObjectName "%SVC_USER%" "%SVC_PASS%"
    if errorlevel 1 (
        echo WARNING: Failed to set service logon account.
        echo Common causes:
        echo   - Wrong username format. Use .\YourUsername or DOMAIN\YourUsername
        echo   - Wrong password
        echo   - Account lacks "Log on as a service" right
        echo Fix manually: Services.msc ^> ScreenRecSvc ^> Properties ^> Log On tab
    ) else (
        echo Service logon account configured successfully.
    )
    goto :logon_config_done
:skip_logon_config
    echo.
    echo WARNING: Service is configured to run as LocalSystem (Session 0).
    echo Screen capture will be attempted via automatic user-session detection,
    echo but for reliable capture it is strongly recommended to run the service
    echo as the target user account ^(re-run this installer and enter credentials^).
    echo.
    echo Attempting to grant LocalSystem the 'Act as part of the operating system'
    echo privilege ^(SeTcbPrivilege^) so it can relaunch in the user session...
    echo.
    :: Export current security policy, add SeTcbPrivilege for *S-1-5-18 (LocalSystem),
    :: then re-import it.
    set _SECEDIT_DB=%TEMP%\screensvc_secedit.db
    set _SECEDIT_INF=%TEMP%\screensvc_tcb.inf
    (
        echo [Unicode]
        echo Unicode=yes
        echo [Version]
        echo signature="$CHICAGO$"
        echo Revision=1
        echo [Privilege Rights]
        echo SeTcbPrivilege = *S-1-5-18
    ) > "%_SECEDIT_INF%"
    secedit /configure /db "%_SECEDIT_DB%" /cfg "%_SECEDIT_INF%" /areas USER_RIGHTS /quiet
    if %errorLevel%==0 (
        echo SUCCESS: SeTcbPrivilege granted to LocalSystem.
        echo The service can now relaunch the recorder in the active user session.
    ) else (
        echo WARNING: Could not automatically grant SeTcbPrivilege.
        echo To grant it manually:
        echo   1. Open secpol.msc
        echo   2. Navigate to: Local Policies ^> User Rights Assignment
        echo   3. Open "Act as part of the operating system"
        echo   4. Add "LOCAL SERVICE" or "NT AUTHORITY\SYSTEM"
        echo   5. Restart the service.
        echo.
        echo Alternatively, re-run this installer and enter your Windows user
        echo credentials to run the service as your own account instead.
    )
    if exist "%_SECEDIT_INF%" del "%_SECEDIT_INF%" >nul 2>&1
    if exist "%_SECEDIT_DB%" del "%_SECEDIT_DB%" >nul 2>&1
    echo.
:logon_config_done
echo Step 9 complete - Service installed.
pause

echo Step 10: Starting service...
"%NSSM%" start ScreenRecSvc
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
echo Service Name: ScreenRecSvc
echo Installation Directory: %INSTALL_DIR%
echo.
echo Log Files:
echo   - Service stdout: %INSTALL_DIR%\logs\service.log
echo   - Service stderr: %INSTALL_DIR%\logs\service_error.log
echo   - Client log:     %INSTALL_DIR%\ScreenRecSvc\client.log
echo   - Crash log:      %INSTALL_DIR%\ScreenRecSvc\crash.log
echo.
echo The client will start automatically on system boot.
echo.
echo To manage the service:
echo   - Start:   sc start ScreenRecSvc
echo   - Stop:    sc stop ScreenRecSvc
echo   - Status:  sc query ScreenRecSvc
echo.
echo To view logs:
echo   - type "%INSTALL_DIR%\ScreenRecSvc\client.log"
echo   - type "%INSTALL_DIR%\ScreenRecSvc\crash.log"
echo.
echo To uninstall, run: uninstall_client_service.bat
echo ================================================
echo.
pause
