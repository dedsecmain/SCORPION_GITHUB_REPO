@echo off
setlocal
cd /d "%~dp0"

rem MK90 experimental runner. Never touches main or production startup.
rem This starts in its own local-only data paths.
git -C "%~dp0.." pull --ff-only origin scorpion-mk90
if errorlevel 1 (
    echo MK90 Git-Update fehlgeschlagen. Kein Start mit unklarem Branch.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo MK90-Entwicklungsumgebung fehlt. Bitte zuerst die Python-3.12-Umgebung einrichten.
    pause
    exit /b 1
)

if not exist "%LOCALAPPDATA%\ScorpionMK90DevData" mkdir "%LOCALAPPDATA%\ScorpionMK90DevData"
set "SCORPION_MK90_DEV=1"
set "SCORPION_MK90_BROWSER_ENABLED=1"
set "SCORPION_MK90_SCANNERS_ENABLED=1"
set "SCORPION_WAKE_LISTENER_ENABLED=false"
set "SCORPION_DRIVE_SYNC_ENABLED=false"
set "SCORPION_MODE=LOCAL"
set "SCORPION_MEMORY_PATH=%LOCALAPPDATA%\ScorpionMK90DevData\memory.json"
set "SCORPION_ADAPTIVE_PATH=%LOCALAPPDATA%\ScorpionMK90DevData\adaptive.json"
set "SCORPION_LONG_TERM_MEMORY_PATH=%LOCALAPPDATA%\ScorpionMK90DevData\long_term_memory.json"
set "SCORPION_APP_TRUST_PATH=%LOCALAPPDATA%\ScorpionMK90DevData\app_trust.json"
set "PYTHONPATH=%CD%\src"

echo SCORPION MK90 DEV startet, mit separaten Testdaten und ohne produktiven Autostart.
".venv\Scripts\python.exe" -m scorpion
if errorlevel 1 (
    echo MK90 wurde mit einem Fehler beendet. Terminal-Ausgabe beachten.
    pause
    exit /b 1
)
exit /b 0
