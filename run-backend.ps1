# run-backend.ps1 — Starts the Flask Python Backend
# University Auction Bid Management System

$BackendDir = "$PSScriptRoot\python-backend"

# Check if port 5000 is already occupied
$portInUse = netstat -an | Select-String ":5000 " | Select-String "LISTENING"
if ($portInUse) {
    Write-Host "⚠ Port 5000 is already in use. Flask may already be running." -ForegroundColor Yellow
    exit 1
}

# Check Java engine is running
try {
    $response = Invoke-WebRequest -Uri "http://localhost:9090/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✓ Java engine is running." -ForegroundColor Green
} catch {
    Write-Host "⚠ Java engine (port 9090) does not appear to be running." -ForegroundColor Yellow
    Write-Host "  Start it first with: .\run-java.ps1" -ForegroundColor DarkGray
}

Write-Host "Starting Flask backend on http://localhost:5000 ..." -ForegroundColor Cyan
Set-Location $BackendDir
python app.py
