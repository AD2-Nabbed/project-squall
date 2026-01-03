@echo off
REM Start Backend Server Script for CMD
echo Changing to project directory...
cd /d "C:\Users\Nabbed\Documents\GitHub\project-squall"

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Setting environment variables...
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k

echo.
echo Starting backend server on http://127.0.0.1:8000...
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --port 8000

