"""Use the trained English recognizer for Small-label machine/serial crops."""
import importlib.util
import os
from pathlib import Path
from scanner.reading.ocr_settings import ocr_threads


class FieldReader:
    def __init__(self):
        self.model = None
        self.failed = False
        self.warnings = []
        self.last_confidence = None

    def load(self):
        root = Path(__file__).resolve().parents[2]
        helper = root/'tube-training/onnx_recognizer.py'
        spec = importlib.util.spec_from_file_location('tube_field_onnx', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Recognizer(root/'trained-model/english_finetuned_rec', threads=ocr_threads())

    def read(self, crop, field, label_type, fallback):
        self.last_confidence = None
        # English improved serials/machines; dates and Large labels retain baseline OCR.
        eligible = label_type == 'small' and field in {'machine', 'serial_number'}
        if not eligible or os.environ.get('SCANNER_FIELD_MODEL', 'english') == 'rapidocr' or self.failed:
            return fallback()
        try:
            if self.model is None:
                self.model = self.load()
            result = self.model(crop)
            text = result['text'].strip()
            if text:
                self.last_confidence = result.get('confidence')
                return text.upper() if field == 'serial_number' else text
        except Exception as error:
            self.failed = True
            self.warnings.append('English field recognizer unavailable; using original OCR. '+str(error)[:160])
        return fallback()
