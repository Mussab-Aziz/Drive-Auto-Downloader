@echo off
title Drive Downloader
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Google Drive Download Automation       ║
echo  ║   Starting backend + frontend...         ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Start Python FastAPI backend
echo [1/2] Starting Python backend (port 8000)...
start "Backend - FastAPI" cmd /k "cd backend && python server.py"

:: Wait a moment for backend to boot
timeout /t 2 /nobreak >nul

:: Start React frontend
echo [2/2] Starting React frontend (port 5173)...
cd frontend
start "Frontend - React" cmd /k "npm run dev"

:: Open browser
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo  Both servers are running!
echo  Open: http://localhost:5173
echo.
