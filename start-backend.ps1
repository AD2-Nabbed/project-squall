# Start Backend Server Script
# Usage: .\start-backend.ps1

Write-Host "Setting up environment variables..." -ForegroundColor Cyan

# Set Supabase environment variables
$env:SUPABASE_URL = "https://xvxgkrittqgwqpuzryrf.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k"

Write-Host "Environment variables set!" -ForegroundColor Green
Write-Host ""
Write-Host "Starting backend server on http://127.0.0.1:8000..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
uvicorn app.main:app --reload --port 8000

