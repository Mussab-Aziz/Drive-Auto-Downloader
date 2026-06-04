@echo off
REM Python Diagnostic and PATH Fix Script

echo.
echo ========================================
echo Python Installation Diagnostic
echo ========================================
echo.

REM Check if Python is installed anywhere
echo Checking for Python installations...
echo.

REM Try standard command
echo [1] Testing 'python' command...
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo SUCCESS: python command works!
    python --version
    echo.
    goto success
) else (
    echo FAILED: 'python' command not found
)

echo.

REM Try python3 command
echo [2] Testing 'python3' command...
python3 --version >nul 2>&1
if %errorlevel% == 0 (
    echo SUCCESS: python3 command works!
    python3 --version
    echo.
    echo Use 'python3 app_ui.py' instead of 'python app_ui.py'
    echo.
    goto success
) else (
    echo FAILED: 'python3' command not found
)

echo.

REM Try to find Python in common locations
echo [3] Checking common Python installation paths...
echo.

set "found=0"

if exist "C:\Python312\python.exe" (
    echo Found: C:\Python312\python.exe
    set "found=1"
)
if exist "C:\Python311\python.exe" (
    echo Found: C:\Python311\python.exe
    set "found=1"
)
if exist "C:\Python310\python.exe" (
    echo Found: C:\Python310\python.exe
    set "found=1"
)
if exist "%APPDATA%\Python\Python312\Scripts\python.exe" (
    echo Found: %%APPDATA%%\Python\Python312\Scripts\python.exe
    set "found=1"
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    echo Found: %%LOCALAPPDATA%%\Programs\Python\Python312\python.exe
    set "found=1"
)

if %found% == 1 (
    echo.
    echo Python files found, but not in PATH!
    echo.
    goto path_fix
) else (
    echo Python not found in common locations.
    echo.
    goto install_needed
)

:path_fix
echo.
echo ========================================
echo Adding Python to PATH
echo ========================================
echo.
echo Run this command as Administrator:
echo.
echo setx PATH "%%PATH%%;C:\Python312"
echo.
echo Or use Windows Settings to add Python to your PATH:
echo 1. Open Settings ^(Windows + I^)
echo 2. Search for "Environment Variables"
echo 3. Click "Edit the system environment variables"
echo 4. Click "Environment Variables" button
echo 5. Under System variables, click "Path" then "Edit"
echo 6. Click "New" and add your Python installation path
echo.
pause
exit /b 1

:install_needed
echo.
echo ========================================
echo Python Not Found - Installation Required
echo ========================================
echo.
echo Please install Python from: https://www.python.org/downloads/
echo.
echo During installation, IMPORTANT:
echo - Check the box: "Add Python to PATH"
echo - Use the default installation location
echo.
echo After installing, restart this terminal and try again.
echo.
pause
exit /b 1

:success
echo ========================================
echo Now run your app:
echo ========================================
echo.
echo cd e:\Download Automation
echo python app_ui.py
echo.
pause
exit /b 0
