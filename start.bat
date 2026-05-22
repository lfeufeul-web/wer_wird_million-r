@echo off
:: Wer wird Millionär App Launcher
setlocal

:loop
cls
echo ===================================================
echo   🚀 WER WIRD MILLIONÄR - LOKALER START-MODUS ⭐  
echo ===================================================
echo Status: Suche nach funktionierendem Python...
echo.

set "PYTHON_EXE="

:: 1. Check standard Windows user installation paths first
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" & goto python_found
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" & goto python_found
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" & goto python_found
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe" & goto python_found
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python39\python.exe" set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python39\python.exe" & goto python_found

:: 2. Check py launcher
py --version >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=py" & goto python_found

:: 3. Check global python (last resort because of Windows Store alias issues)
python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python" & goto python_found

python3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python3" & goto python_found

:no_python
echo [FEHLER] Python konnte nicht gefunden werden.
echo Bitte installiere Python von python.org.
pause
exit /b

:python_found
echo Python gefunden: %PYTHON_EXE%
echo.
echo Status: Ueberpruefe Flet-Bibliothek...
echo.

:: Check if flet is installed
"%PYTHON_EXE%" -c "import flet" 2>nul
if errorlevel 1 goto install_flet
goto start_app

:install_flet
echo [INFO] Flet-Bibliothek fehlt. Versuche Installation...
"%PYTHON_EXE%" -m pip install flet
if errorlevel 1 goto flet_install_failed
goto start_app

:flet_install_failed
echo.
echo [FEHLER] Flet konnte nicht ueber pip installiert werden.
echo Bitte installiere flet manuell.
pause
exit /b

:start_app
echo Status: App wird gestartet...
echo.
echo [INFO] Schliesse das App-Fenster, um die App zu beenden.
echo        Druecke STRG+R im App-Fenster zum Aktualisieren.
echo ---------------------------------------------------

"%PYTHON_EXE%" main.py

echo.
echo [!] App geschlossen. Druecke eine Taste zum Neustarten oder schliesse das Konsolenfenster...
pause
goto loop
