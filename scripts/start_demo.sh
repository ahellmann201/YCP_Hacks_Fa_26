#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -z "${SCANNER_ACCESS_PASSWORD:-}" ]]; then
    echo "Set SCANNER_ACCESS_PASSWORD before starting. See README.md."
    exit 1
fi
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
echo "Local address: http://127.0.0.1:${PORT:-8000}"
echo "For phones or other computers, use the configured HTTPS reverse-proxy address."
echo "Keep this terminal open. Press Ctrl+C to stop; unfinished work is retained."
exec .venv-ocr/bin/python -m uvicorn main:app --host "${SCANNER_BIND:-127.0.0.1}" --port "${PORT:-8000}"
