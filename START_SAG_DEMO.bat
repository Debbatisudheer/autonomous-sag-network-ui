@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo      SAG NETWORK v2.0.0 - LIVE SHOWCASE
echo ================================================
echo.
echo Starting the showcase server...
echo Keep this window open while using the demo.
echo.
start "SAG Browser" cmd /c "timeout /t 2 /nobreak >nul && start "" http://127.0.0.1:8765"
python showcase\server.py
if errorlevel 1 (
  echo.
  echo The showcase server stopped with an error.
  echo Check that Python is installed and try:
  echo   python showcase\server.py
  pause
)
endlocal
