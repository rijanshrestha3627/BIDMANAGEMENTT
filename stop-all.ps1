# stop-all.ps1 — Stops Java Engine (9090), Flask Backend (5000), and Frontend Server (5500)
# University Auction Bid Management System

Write-Host "Stopping all auction services..." -ForegroundColor Cyan

$ports = @(9090, 5000, 5500)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            try {
                Stop-Process -Id $p -Force -ErrorAction Stop
                Write-Host "Stopped process $p on port $port" -ForegroundColor Green
            } catch {
                Write-Host "Could not stop PID $p on port $port : $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "Port $port is already clear." -ForegroundColor Gray
    }
}

Write-Host "All auction services stopped." -ForegroundColor Cyan
