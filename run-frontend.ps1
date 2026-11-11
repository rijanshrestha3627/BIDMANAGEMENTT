# run-frontend.ps1 — Starts the frontend HTTP server
# University Auction Bid Management System

$FrontendDir = "$PSScriptRoot\frontend"

# Check if port 5500 is already occupied
$portInUse = netstat -an | Select-String ":5500 " | Select-String "LISTENING"
if ($portInUse) {
    Write-Host "⚠ Port 5500 is already in use. Frontend server may already be running." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting frontend server on http://localhost:5500 ..." -ForegroundColor Cyan
Write-Host "Open: http://localhost:5500/index.html" -ForegroundColor Green
Set-Location $FrontendDir
python -m http.server 5500
