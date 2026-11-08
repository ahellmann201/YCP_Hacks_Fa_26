"""Bounded OCR parallelism for the Pi's shared model sessions."""
import os


def ocr_threads():
    value = os.environ.get('SCANNER_OCR_THREADS', '1')
    if value not in {'1', '2'}:
        raise ValueError('SCANNER_OCR_THREADS must be 1 or 2')
    return int(value)
