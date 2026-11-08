import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from background_scanner import QueueStore


class TimingTests(unittest.TestCase):
    def test_timing_survives_reload_and_review_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'scanner.sqlite3'
            store = QueueStore(path)
            session = store.create('timing test')['id']
            with patch('background_scanner.time.time', return_value=100):
                store.register(session, 'a'*32)
            with patch('background_scanner.time.time', return_value=105):
                job = store.claim()
            store.complete(job, {'fields':{}, 'label_type':'small'}, [], 12.5)
            store = QueueStore(path)
            store.edit(session, 'a'*32, {'sample_id':'123'}, 'small', False)
            timing = store.status(session)['jobs'][0]['timing']
            self.assertEqual(timing, {'processing_seconds':12.5, 'queue_seconds':5, 'total_seconds':17.5})

    def test_old_database_migrates_without_inventing_times(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'scanner.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE scan_jobs(record_id TEXT PRIMARY KEY, state TEXT, error TEXT, notices_json TEXT DEFAULT '[]')")
            db.close()
            store = QueueStore(path)
            session = store.create('legacy')['id']
            store.register(session, 'b'*32)
            job = store.claim()
            store.recover()
            job = store.claim()
            self.assertIsNone(job['queue_seconds'])
            store.complete(job, {'fields':{}}, [], 3)
            timing = store.status(session)['jobs'][0]['timing']
            self.assertEqual(timing['processing_seconds'], 3)
            self.assertIsNone(timing['total_seconds'])


if __name__ == '__main__':
    unittest.main()
