@echo off
setlocal enabledelayedexpansion

echo === Blitztext - Windows Installation ===
echo.

set "PYTHON_EXE="

:: 1) py-Launcher verwenden, falls vorhanden
where py >nul 2>&1
if errorlevel 1 goto :try_where_python

set "CANDIDATE="
for /f "delims=" %%V in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "CANDIDATE=%%V"
if not defined CANDIDATE goto :try_where_python
call :check_version "!CANDIDATE!"

:try_where_python
if defined PYTHON_EXE goto :after_check

:: 2) Fallback: jede python.exe im PATH einzeln pruefen
for /f "delims=" %%V in ('where python 2^>nul') do if not defined PYTHON_EXE call :check_version "%%V"

if defined PYTHON_EXE goto :after_check

echo Kein Python 3.10 oder neuer gefunden.
echo.
echo Bitte Python 3.10 oder neuer installieren:
echo   https://www.python.org/downloads/
echo.
echo Wichtig beim Installieren: "Add Python to PATH" aktivieren.
echo Danach diese Datei erneut ausfuehren.
echo.
pause
exit /b 1

:check_version
set "TESTEXE=%~1"
"%TESTEXE%" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_EXE=%TESTEXE%"
exit /b 0

:after_check
echo Gefundenes Python: !PYTHON_EXE!
"!PYTHON_EXE!" --version
echo.

:: ── pythonw.exe-Pfad ableiten ─────────────────────────────────────────────
set "PYTHONW_EXE=!PYTHON_EXE:python.exe=pythonw.exe!"

:: ── Pakete installieren ───────────────────────────────────────────────────
echo [1/2] Installiere Python-Pakete...
"!PYTHON_EXE!" -m pip install --upgrade pip
"!PYTHON_EXE!" -m pip install PyQt6 sounddevice soundfile numpy httpx keyring pynput pyautogui pywin32

echo.

:: ── start.bat erstellen ───────────────────────────────────────────────────
echo [2/2] Erstelle start.bat...

> "%~dp0start.bat" echo @echo off
>> "%~dp0start.bat" echo start "" "!PYTHONW_EXE!" "%~dp0main.py"

echo.
echo === Installation abgeschlossen ===
echo.
echo Starten: Doppelklick auf start.bat
echo.
pause