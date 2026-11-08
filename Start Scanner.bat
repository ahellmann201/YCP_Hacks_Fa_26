@echo off
cd /d "%~dp0"
if not exist ".venv-ocr\Scripts\python.exe" (
    echo Missing .venv-ocr. Follow the "Run on the Dell" section in README.md.
    pause
    exit /b 1
)
set SCANNER_OCR_THREADS=3
if "%SCANNER_ACCESS_PASSWORD%"=="" (
    echo Set SCANNER_ACCESS_PASSWORD before starting. See ASSISTANT.md.
    pause
    exit /b 1
)
echo Starting the scanner with 3 OCR threads.
echo Open http://127.0.0.1:8000
echo Keep this window open. Press Ctrl+C to stop.
echo The uploads folder is emptied the next time the server starts. Download a CSV first if you still need the photos.
echo.
.venv-ocr\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
echo.
pause
