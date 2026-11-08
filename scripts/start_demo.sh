#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv-ocr/bin/python ]]; then
    echo "Missing .venv-ocr. Follow the fresh-install section in README.md."
    exit 1
fi
export SCANNER_OCR_THREADS="${SCANNER_OCR_THREADS:-3}"
case "$SCANNER_OCR_THREADS" in
    1|2|3|4) ;;
    *) echo "SCANNER_OCR_THREADS must be 1, 2, 3 or 4"; exit 1 ;;
esac
echo "Starting the demo with $SCANNER_OCR_THREADS OCR threads."
echo "Open one of these addresses from a device on the same network:"
for address in $(hostname -I); do
    if [[ "$address" == *:* ]]; then
        echo "  http://[$address]:${PORT:-8000}"
    else
        echo "  http://$address:${PORT:-8000}"
    fi
done
echo "Keep this terminal open. Press Ctrl+C to stop."
echo "The uploads folder is emptied the next time the server starts. Download a CSV first if you still need the photos."
exec .venv-ocr/bin/python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
