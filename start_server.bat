@echo off
echo ================================================
echo   Screen Recorder Server - Quick Start
echo ================================================
echo.

cd /d "%~dp0server"

:: Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q

:: Check if .env exists
if not exist ".env" (
    echo Creating default .env file...
    echo SECRET_KEY=change-this-to-secure-random-string > .env
    echo ADMIN_PASSWORD=admin123 >> .env
    echo PORT=5000 >> .env
)

echo.
echo ================================================
echo   Starting Server
echo ================================================
echo.
echo Admin Dashboard: http://localhost:5000/admin
echo Admin Password: admin123 (change in .env file)
echo.
echo Press Ctrl+C to stop the server
echo ================================================
echo.

python app.py

pause