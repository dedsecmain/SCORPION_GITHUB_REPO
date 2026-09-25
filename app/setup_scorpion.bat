@echo off
setlocal
cd /d %~dp0

echo ==========================================
echo SCORPION MK50 - Adaptive Core Setup
echo ==========================================
echo.

if not "%CD:~180,1%"=="" (
  echo [WARNUNG] Der Installationspfad ist sehr lang.
  echo Verschiebe den Ordner am besten nach C:\Scorpion
  echo Lange OneDrive-/Schulpfade koennen Python-Pakete brechen.
  echo.
)

where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py -3
) else (
  set PY=python
)

if not exist .venv\Scripts\python.exe (
  echo [1/5] Erstelle Python-Umgebung...
  %PY% -m venv .venv || goto :error
) else (
  echo [1/5] Python-Umgebung existiert bereits.
)

call .venv\Scripts\activate.bat || goto :error

echo [2/5] Aktualisiere pip...
python -m pip install --upgrade pip || goto :error

echo [3/5] Installiere Scorpion-Abhaengigkeiten...
python -m pip install -r requirements.txt || goto :error

if not exist .env copy .env.example .env

echo [4/5] Bereite lokales Hand-Tracking-Modell vor...
set PYTHONPATH=%CD%\src
python -m scorpion.gesture_tracker --download-model
if errorlevel 1 (
  echo [WARNUNG] Gesture-Modell konnte nicht vorgeladen werden. Build Mode versucht es beim ersten Start erneut.
)

echo [5/5] Registriere Windows-Autostart...
set PYTHONPATH=%CD%\src
python -m scorpion.autostart --app-root "%CD%"
if errorlevel 1 (
  echo [WARNUNG] Autostart konnte nicht eingerichtet werden. Scorpion selbst bleibt nutzbar.
)
echo.
echo ==========================================
echo SCORPION MK50 Setup fertig.
echo ==========================================
echo Standardmodus: LOCAL - kein OpenAI API-Key noetig.
echo OPENAI_API_KEY ist optional und wird nur fuer einzeln bestaetigte Cloud-Anfragen benutzt.
echo.
echo Fuer lokale KI brauchst du Ollama separat.
echo Scorpion waehlt bei leerem SCORPION_LOCAL_MODEL automatisch ein Hardware-Profil.
echo Installierte Modelle werden bevorzugt. Modell-Downloads passieren nie ohne deine Bestaetigung.
echo Gute Startmodelle sind:
echo   ollama pull qwen3.5:4b
echo   ollama pull gemma3:4b
echo Optional fuer staerkere Hardware:
echo   ollama pull qwen3:8b
echo.
echo Der Wake-Listener ist in MK50 standardmaessig aktiv und erholt sich nach temporaeren Audiofehlern.
echo Build Mode nutzt lokale Webcam-Handgesten via MediaPipe, einen 3D-Renderer und Maus-Fallback.
echo Externe OBJ/GLB/GLTF/STL/PLY-Modelle koennen lokal importiert werden.
echo Beim ersten Einsatz koennen Whisper-Modelle lokal heruntergeladen werden.
echo Das verbraucht keine OpenAI-API-Credits.
echo.
echo Der offizielle GitHub-Updatekanal ist vorkonfiguriert.
echo Kein Update wird ohne deine Bestaetigung installiert.
echo Scorpion startet nach dem Setup bei der Windows-Anmeldung automatisch.
echo.
echo Danach run_scorpion.bat starten.
goto :done

:error
echo.
echo ==========================================
echo SETUP FEHLGESCHLAGEN.
echo ==========================================
echo Scorpion meldet absichtlich NICHT "fertig".
echo Pruefe die Fehlermeldung oben. Bei sehr langem Pfad: nach C:\Scorpion verschieben,
echo den Ordner .venv loeschen und setup_scorpion.bat erneut starten.
echo.
pause
exit /b 1

:done
pause
exit /b 0
