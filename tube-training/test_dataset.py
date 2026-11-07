import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from dataset import export_dataset, write


class ExportTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'crops').mkdir()
        images, annotations, tubes = [], [], {}
        for index, split in enumerate(('train', 'val'), start=1):
            tube = f'tube_{index}'
            identifier = str(index) * 32
            images.append({'image_id': tube, 'tube_id': tube, 'source_sha256': tube})
            tubes[tube] = {'group_id': tube, 'label_type': 'small', 'split': split}
            annotations.append({'id': identifier, 'image_id': tube, 'field': 'serial_number',
                                'status': 'verified', 'text': 'PP123'})
            Image.new('RGB', (100, 40), 'white').save(root / 'crops' / (identifier + '.png'))
        write(root / 'manifest.json', images)
        write(root / 'tube_meta.json', tubes)
        write(root / 'annotations.json', annotations)
        return tubes, annotations

    def test_export_and_ignore_uncertain(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            tubes, annotations = self.fixture(root)
            annotations.append({'status': 'uncertain', 'text': 'DO NOT TRAIN'})
            write(root / 'annotations.json', annotations)
            result = export_dataset(root)
            self.assertEqual(result['training_crops'], 1)
            self.assertEqual(result['validation_crops'], 1)
            self.assertNotIn('DO NOT TRAIN', (Path(result['path']) / 'train.txt').read_text())

    def test_group_leakage_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            tubes, _ = self.fixture(root)
            tubes['tube_2']['group_id'] = 'tube_1'
            write(root / 'tube_meta.json', tubes)
            with self.assertRaisesRegex(ValueError, 'crosses'):
                export_dataset(root)

    def test_blank_is_not_recognition_text(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            _, annotations = self.fixture(root)
            annotations[1]['status'] = 'blank'
            annotations[1]['text'] = ''
            write(root / 'annotations.json', annotations)
            with self.assertRaisesRegex(ValueError, 'validation'):
                export_dataset(root)


if __name__ == '__main__':
    unittest.main()
