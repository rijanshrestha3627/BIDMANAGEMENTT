# start-all.ps1 — Starts Java Engine, Flask Backend, and Frontend Server
# University Auction Bid Management System

$Root = $PSScriptRoot
$JavaDir = "$Root\java-engine"
$BackendDir = "$Root\python-backend"
$FrontendDir = "$Root\frontend"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting University Auction Bid Management System" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Function to check if a port is in use
function Test-PortOccupied([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue)
}

# 1. Start Java Engine (Port 9090)
if (Test-PortOccupied 9090) {
    Write-Host "[!] Port 9090 is already occupied (Java Engine may be running)." -ForegroundColor Yellow
} else {
    Write-Host "[1/3] Starting Java Auction Engine on port 9090..." -ForegroundColor Green
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$JavaDir'; Write-Host '--- Java Engine Output ---' -ForegroundColor Cyan; java -cp src engine.Main" -WindowStyle Normal
    Start-Sleep -Seconds 3
}

# 2. Start Flask Backend (Port 5000)
if (Test-PortOccupied 5000) {
    Write-Host "[!] Port 5000 is already occupied (Flask Backend may be running)." -ForegroundColor Yellow
} else {
    Write-Host "[2/3] Starting Flask Backend on port 5000..." -ForegroundColor Green
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; Write-Host '--- Flask Backend Output ---' -ForegroundColor Green; python app.py" -WindowStyle Normal
    Start-Sleep -Seconds 3
}

# 3. Start Frontend Server (Port 5500)
if (Test-PortOccupied 5500) {
    Write-Host "[!] Port 5500 is already occupied (Frontend Server may be running)." -ForegroundColor Yellow
} else {
    Write-Host "[3/3] Starting Frontend Server on port 5500..." -ForegroundColor Green
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; Write-Host '--- Frontend Server Output ---' -ForegroundColor Magenta; python -m http.server 5500" -WindowStyle Normal
    Start-Sleep -Seconds 2
}

Write-Host "`nAll services launched!" -ForegroundColor Cyan
Write-Host "----------------------------------------------------------"
Write-Host "  Frontend:  http://localhost:5500/index.html" -ForegroundColor White
Write-Host "  Admin:     http://localhost:5500/admin-login.html" -ForegroundColor White
Write-Host "  Backend:   http://localhost:5000" -ForegroundColor White
Write-Host "  Java API:  http://localhost:9090/health" -ForegroundColor White
Write-Host "----------------------------------------------------------"

Start-Process "http://localhost:5500/index.html"
