@echo off
REM Setup script to link your existing Nabbed player to auth
REM This script will prompt you for your Supabase credentials if not set

cd /d "%~dp0"

REM Check if environment variables are set
if "%SUPABASE_URL%"=="" (
    echo SUPABASE_URL not set in environment.
    echo Please set it, or edit this batch file with your values.
    echo.
    echo You can either:
    echo   1. Edit LINK_PLAYER_QUICK.bat and add your SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
    echo   2. Set them in this terminal session:
    echo      set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
    echo      set SUPABASE_SERVICE_ROLE_KEY=your_key_here
    echo      then run: LINK_PLAYER_QUICK.bat ^<username^> ^<password^>
    pause
    exit /b 1
)

if "%SUPABASE_SERVICE_ROLE_KEY%"=="" (
    echo SUPABASE_SERVICE_ROLE_KEY not set in environment.
    echo Please set it, or edit this batch file with your values.
    pause
    exit /b 1
)

REM Set player ID (your existing Nabbed account)
set PLAYER_ID=d4ac398c-12a6-4cf3-836e-8ede11835029

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

if "%~1"=="" (
    echo Usage: LINK_PLAYER_SETUP.bat ^<username^> ^<password^>
    echo.
    echo Example:
    echo   LINK_PLAYER_SETUP.bat nabbed mypassword
    echo.
    echo Make sure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set!
    pause
    exit /b 1
)

if "%~2"=="" (
    echo Error: Password required
    pause
    exit /b 1
)

python link_existing_player.py %1 %2 %PLAYER_ID%

pause

