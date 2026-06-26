# Drive Downloader – PowerShell Launcher

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║   Google Drive Download Automation       ║" -ForegroundColor Cyan
Write-Host "  ║   Starting backend + frontend...         ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Python backend
Write-Host "[1/2] Starting Python backend on port 8000..." -ForegroundColor Yellow
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python server.py" -PassThru

Start-Sleep -Seconds 2

# Start React frontend
Write-Host "[2/2] Starting React frontend on port 5173..." -ForegroundColor Yellow
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev" -PassThru

Start-Sleep -Seconds 3

# Open browser
Write-Host "[3/3] Opening browser..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "  ✓ Both servers are running!" -ForegroundColor Green
Write-Host "  ► Open: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Press Ctrl+C in each window to stop." -ForegroundColor Gray
