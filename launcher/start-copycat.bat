@echo off
rem Starts the CopyCat server (if it is not running yet) and opens it in the browser.
rem Works from wherever the repo is: it finds the project folder from its own location.
cd /d "%~dp0.."

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if errorlevel 1 (
  start "CopyCat server - close this window to stop CopyCat" /min "%PY%" -m uvicorn backend.main:app --port 8000
  timeout /t 4 /nobreak >nul
)
start "" http://localhost:8000
