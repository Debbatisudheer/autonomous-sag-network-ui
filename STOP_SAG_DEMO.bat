@echo off
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do (
  taskkill /PID %%P /F >nul 2>&1
)
echo SAG showcase server stopped (if it was running).
pause
