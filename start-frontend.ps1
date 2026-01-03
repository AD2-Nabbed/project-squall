# Start Frontend Server Script
# Usage: .\start-frontend.ps1

Write-Host "Starting frontend server on http://localhost:8080..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Change to frontend directory and start server
Set-Location frontend
python -m http.server 8080

