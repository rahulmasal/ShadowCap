@echo off
echo ================================================
echo   Screen Recorder Client - Windows Service Uninstaller
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

echo Step 1: Stopping service...
"%SCRIPT_DIR%nssm.exe" stop ScreenRecSvc
if %errorLevel% neq 0 (
    echo WARNING: Failed to stop service. Error code: %errorLevel%
    echo The service might not be running.
) else (
    echo Service stopped.
)
pause

echo Step 2: Removing Windows service...
"%SCRIPT_DIR%nssm.exe" remove ScreenRecSvc confirm
if %errorLevel% neq 0 (
    echo WARNING: Failed to remove service via NSSM. Error code: %errorLevel%
    echo Trying alternative method...
    sc delete ScreenRecSvc
    if %errorLevel% neq 0 (
        echo WARNING: Failed to delete service via sc. Error code: %errorLevel%
        echo You may need to remove the service manually.
    ) else (
        echo Service removed successfully via sc.
    )
) else (
    echo Service removed successfully via NSSM.
)
pause

echo Step 3: Cleaning up installation directory...
if exist "%INSTALL_DIR%" (
    echo Removing installation directory: %INSTALL_DIR%
    rmdir /s /q "%INSTALL_DIR%"
    echo Installation directory removed.
) else (
    echo Installation directory not found: %INSTALL_DIR%
)
pause

echo Step 4: Cleaning up AppData directory...
set APPDATA_DIR=%APPDATA%\ScreenRecSvc
if exist "%APPDATA_DIR%" (
    echo Removing AppData directory: %APPDATA_DIR%
    rmdir /s /q "%APPDATA_DIR%"
    echo AppData directory removed.
) else (
    echo AppData directory not found: %APPDATA_DIR%
)
pause

echo.
echo ================================================
echo   Uninstallation Complete!
echo ================================================
echo.
echo The Screen Recorder Client service has been removed.
echo.
pause
