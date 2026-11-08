import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from zip_import import prepare_archive, plan_archive, ImportError
from background_scanner import QueueStore
from session_store import SessionError


def photo():
    output = io.BytesIO()
    Image.new('RGB', (60, 30), 'white').save(output, 'JPEG')
    return output.getvalue()


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as batch:
        for name, content in entries:
            batch.writestr(name, content)
    output.seek(0)
    return output


class BatchTests(unittest.TestCase):
    def test_mislabeled_supported_formats_use_actual_contents(self):
        for actual, expected in [('PNG','.png'), ('JPEG','.jpg'), ('TIFF','.jpg'), ('BMP','.jpg')]:
            with self.subTest(actual=actual), tempfile.TemporaryDirectory() as temporary:
                output=io.BytesIO()
                Image.new('RGB',(60,30),'white').save(output,actual)
                root=Path(temporary)
                samples=prepare_archive(archive([('tube/Large_Label (1).jpeg',output.getvalue())]),root,'s','date','now')
                image=samples[0]['images'][0]
                self.assertEqual(image['filename'],'image_1'+expected)
                self.assertEqual(image['detected_format'],actual)
                with Image.open(root/samples[0]['record_id']/image['filename']) as saved:
                    self.assertEqual(saved.format,'PNG' if actual=='PNG' else 'JPEG')

    def test_folder_grouping_staging_and_atomic_queue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = archive([('samples/tube_001/a.jpg', photo()), ('samples/tube_001/b.jpg', photo()),
                             ('samples/tube_002/a.jpg', photo()), ('samples/notes.txt', b'notes')])
            samples = prepare_archive(batch, root, 'session', '2026-11-07', 'now')
            self.assertEqual([s['image_count'] for s in samples], [2, 1])
            self.assertEqual(len({s['record_id'] for s in samples}), 2)
            for sample in samples:
                saved = json.loads((root/sample['record_id']/'sample.json').read_text())
                self.assertEqual(saved, sample)
                self.assertTrue((root/sample['record_id']/'image_1.jpg').exists())
            store = QueueStore(root/'scanner.sqlite3')
            session = store.create('batch')['id']
            store.register_batch(session, [s['record_id'] for s in samples])
            self.assertEqual(store.status(session)['counts']['queued'], 2)

    def test_invalid_paths_root_photos_and_excess_photos_rejected(self):
        cases = [[('../tube/a.jpg', photo())], [('/tube/a.jpg', photo())],
                 [('a.jpg', photo())], [(f'tube/{i}.jpg', photo()) for i in range(9)]]
        for entries in cases:
            with self.subTest(entries=entries[0][0]), zipfile.ZipFile(archive(entries)) as batch:
                with self.assertRaises(ImportError):
                    plan_archive(batch)

    def test_corrupt_image_rejected_before_queue_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ImportError):
                prepare_archive(archive([('tube/a.jpg', b'not an image')]), Path(temporary), 's', 'date', 'now')

    def test_missing_heic_dependency_rejects_before_staging_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = archive([('tube_1/a.jpg', photo()), ('tube_2/a.heic', b'heic')])
            with patch.dict('sys.modules', {'pillow_heif':None}):
                with self.assertRaisesRegex(ImportError, 'pillow-heif'):
                    prepare_archive(batch, root, 's', 'date', 'now')
            self.assertEqual(list(root.iterdir()), [])

    def test_batch_registration_rolls_back_if_tube_belongs_to_other_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = QueueStore(Path(temporary)/'scanner.sqlite3')
            first = store.create('first')['id']
            second = store.create('second')['id']
            store.register(first, 'b'*32)
            with self.assertRaises(SessionError):
                store.register_batch(second, ['a'*32, 'b'*32])
            self.assertEqual(store.status(second)['jobs'], [])
            self.assertIsNone(store.sample('a'*32))


if __name__ == '__main__':
    unittest.main()
