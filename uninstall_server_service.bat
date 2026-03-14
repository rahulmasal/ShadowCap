@echo off
echo ================================================
echo   Screen Recorder Server - Windows Service Uninstaller
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

:: Stop service if running
echo Stopping service...
sc stop ScreenRecorderServer 2>nul
timeout /t 3 /nobreak >nul

:: Remove service
echo Removing Windows service...
if exist "%SCRIPT_DIR%nssm.exe" (
    "%SCRIPT_DIR%nssm.exe" remove ScreenRecorderServer confirm
) else (
    sc delete ScreenRecorderServer
)

:: Ask about removing files
echo.
set /p REMOVE_FILES="Remove installation directory and logs? (y/n): "
if /i "%REMOVE_FILES%"=="y" (
    echo Removing files...
    if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
    echo Files removed.
) else (
    echo Files kept at: %INSTALL_DIR%
)

echo.
echo ================================================
echo   Uninstallation Complete!
echo ================================================
echo.
echo The Screen Recorder Server service has been removed.
echo.
pause
