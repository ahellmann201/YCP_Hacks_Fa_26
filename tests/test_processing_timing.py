import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.queue.background_scanner import QueueStore


class TimingTests(unittest.TestCase):
    def test_timing_survives_reload_and_review_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'scanner.sqlite3'
            store = QueueStore(path)
            session = store.create('timing test')['id']
            with patch('scanner.queue.background_scanner.time.time', return_value=100):
                store.register(session, 'a'*32)
            with patch('scanner.queue.background_scanner.time.time', return_value=105):
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

    def test_session_metrics_count_approved_fields_and_preserve_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = QueueStore(Path(temporary)/'scanner.sqlite3')
            session = store.create('metrics')['id']
            small = {'sample_id':'123', 'date_sampled':'9/20', 'machine':'UP1',
                     'component':'1 GS', 'serial_number':'PP1', 'date_received':'2026-11-07'}
            large = {'sample_id':'456', 'date_sampled':'8/20', 'machine':'M1',
                     'component':'Rear', 'reference_lube':'', 'serial_number':''}
            for record, kind, fields, duration in [('a'*32, 'small', small, 20), ('b'*32, 'large', large, 40)]:
                store.register(session, record)
                store.complete(store.claim(), {'fields':fields, 'label_type':kind}, [], duration)
            self.assertIsNone(store.status(session)['metrics']['field_accuracy_percent'])
            fixed_small = dict(small, machine='UP2', date_received='2026-11-08')
            fixed_large = dict(large, component='Front', machine='M2')
            store.edit(session, 'a'*32, fixed_small, 'small', True)
            store.edit(session, 'b'*32, fixed_large, 'large', True)
            metrics = store.status(session)['metrics']
            self.assertEqual(metrics['average_processing_seconds'], 30)
            self.assertEqual(metrics['timed_tubes'], 2)
            self.assertEqual(metrics['correct_fields'], 7)
            self.assertEqual(metrics['total_fields'], 10)
            self.assertEqual(metrics['field_accuracy_percent'], 70)
            store.edit(session, 'a'*32, fixed_small, 'small', False)
            self.assertEqual(store.status(session)['metrics']['field_accuracy_percent'], 60)
            self.assertEqual(store.sample('a'*32)['review']['original_fields'], small)


if __name__ == '__main__':
    unittest.main()
