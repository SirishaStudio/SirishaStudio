@echo off
REM ============================================================
REM  Sirisha Studio - one-click launcher (Windows)
REM ============================================================
REM  First time only:
REM    1) Install Python 3.11 or 3.12 from python.org (TICK 'Add to PATH')
REM    2) Download Poppler for Windows from:
REM         https://github.com/oschwartz10612/poppler-windows/releases
REM       Unzip somewhere and edit POPPLER_PATH in config.py to point to
REM       the 'Library\bin' folder inside.
REM    3) Double-click setup.bat (creates venv + installs everything)
REM
REM  Then every time after that:  just double-click THIS file.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [!] Virtual environment not found. Running first-time setup...
  echo.
  call setup.bat
  if errorlevel 1 exit /b 1
)

echo.
echo ============================================================
echo  Starting Sirisha Studio on http://127.0.0.1:5000
echo  Press CTRL+C in this window to stop the server.
echo ============================================================
echo.

".venv\Scripts\python.exe" app.py

pause
