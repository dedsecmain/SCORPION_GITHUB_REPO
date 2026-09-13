@echo off
setlocal
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Scorpion ist noch nicht eingerichtet. Starte zuerst setup_scorpion.bat
  pause
  exit /b 1
)
set PYTHONPATH=%CD%\src
.venv\Scripts\python.exe -m scorpion
if errorlevel 1 pause
