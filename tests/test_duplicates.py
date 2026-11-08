import tempfile
import unittest
from pathlib import Path
from scanner.queue.background_scanner import QueueStore


class DuplicateTests(unittest.TestCase):
    def test_identical_photos_skip_ocr_and_are_session_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            store=QueueStore(Path(folder)/'test.sqlite3')
            session=store.create('first')['id']
            sample={'images':[{'sha256':'abc'},{'sha256':'def'}]}
            store.register(session,'a'*32,sample)
            store.register(session,'b'*32,{'images':list(reversed(sample['images']))})
            self.assertEqual(store.claim()['record_id'],'a'*32)
            self.assertIsNone(store.claim())
            self.assertEqual(store.status(session)['jobs'][1]['state'],'duplicate')
            other=store.create('second')['id']
            store.register(other,'c'*32,sample)
            self.assertEqual(store.claim()['record_id'],'c'*32)

    def test_barcode_keeps_first_row_and_flags_conflicting_readings(self):
        with tempfile.TemporaryDirectory() as folder:
            store=QueueStore(Path(folder)/'test.sqlite3')
            session=store.create('barcodes')['id']
            for record,machine in [('a'*32,'UP1'),('b'*32,'UP2')]:
                store.register(session,record)
                store.complete(store.claim(),{'fields':{'sample_id':'123','machine':machine},
                    'decoded_sample_id':'123','label_type':'small'},[],2)
            self.assertEqual(len(store.reviews(session)),1)
            duplicate=store.status(session)['jobs'][1]
            self.assertEqual(duplicate['state'],'duplicate')
            self.assertIn('machine',duplicate['duplicate_conflicts'])
            self.assertEqual(store.reviews(session)[0]['fields']['machine'],'UP1')

    def test_ocr_only_ids_are_not_used_as_duplicate_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            store=QueueStore(Path(folder)/'test.sqlite3')
            session=store.create('uncertain')['id']
            for record in ['a'*32,'b'*32]:
                store.register(session,record)
                store.complete(store.claim(),{'fields':{'sample_id':'123'},'raw_suggestions':{'sample_id':'123'}},[])
            self.assertEqual(len(store.reviews(session)),2)
