@echo off
setlocal
set "QT_PREVIEW_VENV=%LOCALAPPDATA%\LoLHelperQtPreview\venv"
if exist "%QT_PREVIEW_VENV%\Scripts\python.exe" goto install
py -3 -m venv "%QT_PREVIEW_VENV%"
if errorlevel 1 goto failed
:install
"%QT_PREVIEW_VENV%\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto failed
"%QT_PREVIEW_VENV%\Scripts\python.exe" "%~dp0main.py" %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Qt preview could not start. See the error above. Python 3.11+ is required.
pause
exit /b 1
