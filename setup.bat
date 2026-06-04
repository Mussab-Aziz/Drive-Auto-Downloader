@echo off
REM Quick setup script for Google Drive Downloader

echo.
echo ========================================
echo Google Drive Downloader - Setup
echo ========================================
echo.

echo Checking for Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org
    pause
    exit /b 1
)

echo Python found!
echo.

echo Installing required packages...
echo This may take a minute...
echo.

pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client customtkinter

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Get your Google Drive API credentials:
echo    - Go to https://console.cloud.google.com/
echo    - Create an OAuth 2.0 Desktop Application
echo    - Download the JSON file and name it client_secret_file.json
echo.
echo 2. Run the app:
echo    python app_ui.py
echo.
echo For detailed instructions, see README.md
echo.

pause
