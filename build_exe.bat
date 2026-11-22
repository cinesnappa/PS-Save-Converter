@echo off
REM Builds dist\PSSaveConverter.exe (one file, no console window).
REM Needs Python and PyInstaller:  python -m pip install pyinstaller
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name PSSaveConverter ^
  --add-data "games.json;." ^
  --add-data "data\ps4_titles.json;data" ^
  --collect-submodules converters ^
  app.py
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)
echo.
echo Done: dist\PSSaveConverter.exe
pause
