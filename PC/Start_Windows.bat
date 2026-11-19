@echo off
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
if exist ".venv_h743_ui\Scripts\python.exe" goto check
for %%V in (3.12 3.13 3.14) do (
  py -%%V -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    set "H743_PYVER=%%V"
    goto create
  )
)
echo Python 3 not found. Install Python 3.12 with the Windows py launcher.
goto done
:create
echo Creating isolated environment with Python %H743_PYVER%...
py -%H743_PYVER% -m venv .venv_h743_ui
if errorlevel 1 goto done
:check
".venv_h743_ui\Scripts\python.exe" -c "import serial,numpy,PySide6,pyqtgraph" >nul 2>&1
if not errorlevel 1 goto run
echo Installing dependencies in the isolated environment...
".venv_h743_ui\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto done
:run
".venv_h743_ui\Scripts\python.exe" -u -X faulthandler launch.py
:done
echo.
echo If no window appears, send startup.log and the terminal output.
pause
endlocal
