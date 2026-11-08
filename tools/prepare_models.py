"""Prepare the exact app OCR models online once, or check them offline."""
import argparse
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Block networking and verify cached models load')
    args=parser.parse_args()
    if args.check:
        def offline(*unused,**kwargs):
            raise OSError('Models are missing or invalid. Run tools/prepare_models.py with internet first.')
        socket.socket.connect=offline;socket.socket.connect_ex=offline;socket.create_connection=offline
    try:
        from rapidocr import RapidOCR
        from scanner.reading.ocr_settings import rapidocr_parameters
        RapidOCR(params=rapidocr_parameters(threads=1))
        from scanner.reading.field_recognizer import FieldReader
        FieldReader().load()
    except Exception as error:
        raise SystemExit('Model preparation/check failed: '+str(error))
    print('App OCR models loaded successfully'+(' with networking blocked.' if args.check else '.'))


if __name__=='__main__':
    main()
