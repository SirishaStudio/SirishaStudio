@echo off
REM ============================================================
REM  Sirisha Studio - one-time setup (Windows)
REM ============================================================
REM  Creates a virtual environment in .venv\ and installs everything
REM  listed in requirements.txt. Run this once after cloning.
REM ============================================================

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [X] Python launcher 'py' not found.
  echo     Install Python 3.11 or 3.12 from https://www.python.org/downloads/
  echo     Make sure to TICK "Add Python to PATH" during install.
  pause
  exit /b 1
)

echo.
echo [1/3] Creating virtual environment in .venv\ ...
py -3 -m venv .venv
if errorlevel 1 (
  echo [X] Failed to create .venv
  pause
  exit /b 1
)

echo.
echo [2/3] Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo.
echo [3/3] Installing project dependencies (this can take a few minutes) ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [X] pip install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  Setup complete!
echo.
echo  IMPORTANT: For PDF tools to work you also need POPPLER:
echo    1. Download from
echo       https://github.com/oschwartz10612/poppler-windows/releases
echo    2. Unzip somewhere on your PC
echo    3. Open config.py and set POPPLER_PATH to the 'Library\bin'
echo       folder inside the unzipped poppler folder.
echo.
echo  Then double-click run.bat to start the app.
echo ============================================================
pause
