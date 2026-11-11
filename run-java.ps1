# run-java.ps1 — Starts the Java Auction Engine
# University Auction Bid Management System

$JavaDir = "$PSScriptRoot\java-engine"

# Check if port 9090 is already occupied
$portInUse = netstat -an | Select-String ":9090 " | Select-String "LISTENING"
if ($portInUse) {
    Write-Host "⚠ Port 9090 is already in use. Java engine may already be running." -ForegroundColor Yellow
    Write-Host "  Run: netstat -an | findstr :9090" -ForegroundColor DarkGray
    exit 1
}

Write-Host "Starting Java Auction Engine on port 9090..." -ForegroundColor Cyan
Set-Location $JavaDir
java -cp src engine.Main
