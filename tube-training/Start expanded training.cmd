@echo off
cd /d "%~dp0"
if not exist ".venv-train\Scripts\python.exe" (
  echo Training environment is missing from this folder.
  pause
  exit /b 1
)
".venv-train\Scripts\python.exe" run_expanded_training.py
if errorlevel 1 echo Training stopped. Copy the last error lines for troubleshooting.
pause
