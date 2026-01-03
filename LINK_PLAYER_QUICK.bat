@echo off
REM Quick script to link your existing Nabbed player to auth
REM Usage: LINK_PLAYER_QUICK.bat <username> <password>

if "%~1"=="" (
    echo Usage: LINK_PLAYER_QUICK.bat ^<username^> ^<password^>
    echo.
    echo Example:
    echo   LINK_PLAYER_QUICK.bat nabbed mypassword
    echo.
    pause
    exit /b 1
)

if "%~2"=="" (
    echo Error: Password required
    pause
    exit /b 1
)

cd /d "%~dp0"

REM Set environment variables
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Set player ID (your existing Nabbed account)
set PLAYER_ID=d4ac398c-12a6-4cf3-836e-8ede11835029

python link_existing_player.py %1 %2 %PLAYER_ID%

pause

