import unittest
from unittest.mock import Mock, patch
from field_recognizer import FieldReader
from ocr_settings import ocr_threads


class FieldReaderTests(unittest.TestCase):
    def test_thread_setting_is_bounded_and_defaults_to_one(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(ocr_threads(), 1)
        with patch.dict('os.environ', {'SCANNER_OCR_THREADS':'2'}):
            self.assertEqual(ocr_threads(), 2)
        with patch.dict('os.environ', {'SCANNER_OCR_THREADS':'8'}):
            with self.assertRaises(ValueError):
                ocr_threads()

    def test_reuses_model_and_uppercases_serial(self):
        reader = FieldReader()
        model = Mock(return_value={'text':'Pp123', 'confidence':.9})
        fallback = Mock(return_value='old')
        with patch.object(reader, 'load', return_value=model) as load:
            self.assertEqual(reader.read(None, 'serial_number', 'small', fallback), 'PP123')
            reader.read(None, 'machine', 'small', fallback)
            load.assert_called_once()
        fallback.assert_not_called()

    def test_dates_large_labels_and_disabled_mode_keep_original(self):
        reader = FieldReader()
        fallback = Mock(return_value='original')
        with patch.object(reader, 'load') as load:
            self.assertEqual(reader.read(None, 'date_sampled', 'small', fallback), 'original')
            self.assertEqual(reader.read(None, 'machine', 'large', fallback), 'original')
            with patch.dict('os.environ', {'SCANNER_FIELD_MODEL':'rapidocr'}):
                self.assertEqual(reader.read(None, 'machine', 'small', fallback), 'original')
            load.assert_not_called()

    def test_missing_model_falls_back_without_repeated_loads(self):
        reader = FieldReader()
        fallback = Mock(return_value='old')
        with patch.object(reader, 'load', side_effect=FileNotFoundError('model')) as load:
            self.assertEqual(reader.read(None, 'machine', 'small', fallback), 'old')
            self.assertEqual(reader.read(None, 'serial_number', 'small', fallback), 'old')
            load.assert_called_once()
        self.assertEqual(len(reader.warnings), 1)


if __name__ == '__main__':
    unittest.main()
