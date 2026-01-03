@echo off
REM Start Frontend Server Script for CMD
echo Changing to frontend directory...
cd /d "C:\Users\Nabbed\Documents\GitHub\project-squall\frontend"

echo.
echo Starting frontend server on http://localhost:8080...
echo Press Ctrl+C to stop the server
echo.

python -m http.server 8080

