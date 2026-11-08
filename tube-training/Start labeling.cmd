@echo off
cd /d "%~dp0"
set "TRAIN_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist ".venv-train\Scripts\python.exe" set "TRAIN_PYTHON=%~dp0.venv-train\Scripts\python.exe"
if exist "%TRAIN_PYTHON%" (
    "%TRAIN_PYTHON%" annotation_server.py
) else (
    py -3 annotation_server.py
)
pause
