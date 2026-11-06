@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Once scripts\setup.ps1 ile Python ortamini hazirlayin.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -m disktest demo --reports reports
set "demo_result=%errorlevel%"
echo.
echo Raporlar reports klasorunde. Bu surum fiziksel disk testi yapmaz.
pause
exit /b %demo_result%
