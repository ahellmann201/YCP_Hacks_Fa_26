import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from background_scanner import QueueStore
from session_store import SessionError
from session_cleanup import clear_uploads
from review_checks import field_checks
from label_preview import build_preview


def render(reviews):
    return json.dumps([r['fields'] for r in reviews], sort_keys=True).encode()


class ReviewCleanupTests(unittest.TestCase):
    def test_review_flags_are_conservative(self):
        fields = {'sample_id':'1', 'machine':'UP1', 'serial_number':'PP1', 'date_sampled':'9/20', 'component':'1 GS'}
        result = {'images':[{'fields':fields, 'field_scores':{'machine':.99, 'serial_number':.7}}]}
        checks = field_checks(fields, 'small', result)
        self.assertEqual(checks['sample_id'], [])
        self.assertEqual(checks['machine'], [])
        self.assertTrue(checks['serial_number'])
        self.assertTrue(checks['date_sampled'])
        self.assertTrue(checks['component'])
        self.assertTrue(field_checks(fields, 'small', {})['machine'])

    def test_selected_field_crop_saved_for_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary); root=folder/'analysis'/'a'
            root.mkdir(parents=True)
            Image.new('RGB',(100,35),'white').save(root/'photo_1_machine.jpg')
            result={'images':[{'label_type':'small','debug':['photo_1_machine.jpg'],'fields':{'machine':'UP1'}}],
                    'suggestions':{'machine':'UP1'}}
            evidence=build_preview(folder,'a',result,'small')
            self.assertEqual(evidence['sources']['machine'],1)
            self.assertTrue((root/'field_machine.jpg').is_file())

    def test_finish_requires_complete_export_and_current_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=QueueStore(Path(temporary)/'scanner.sqlite3')
            sid=store.create('test')['id']; record='a'*32
            store.register(sid,record)
            with self.assertRaises(SessionError):
                store.finish_for_export(sid,'0'*64,True,render)
            store.complete(store.claim(),{'fields':{'sample_id':'1'},'label_type':'small'},[])
            token=hashlib.sha256(render(store.reviews(sid))).hexdigest()
            with self.assertRaises(SessionError):
                store.finish_for_export(sid,token,False,render)
            store.edit(sid,record,{'sample_id':'2'},'small',True)
            with self.assertRaises(SessionError):
                store.finish_for_export(sid,token,False,render)
            self.assertIsNone(store.get(sid)['finished_at'])
            token=hashlib.sha256(render(store.reviews(sid))).hexdigest()
            self.assertEqual(store.finish_for_export(sid,token,False,render),[record])
            self.assertTrue(store.get(sid)['finished_at'])
            self.assertEqual(store.reviews(sid)[0]['fields']['sample_id'],'2')

    def test_cleanup_keeps_other_sessions_and_checks_paths_before_deleting(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root=Path(temporary)/'uploads';root.mkdir()
            for record in ['a'*32,'b'*32]:
                (root/record).mkdir();(root/record/'image.jpg').write_bytes(b'image')
            with self.assertRaises(ValueError):
                clear_uploads(root,['a'*32,'../outside'])
            self.assertTrue((root/('a'*32)).exists())
            clear_uploads(root,['a'*32])
            self.assertFalse((root/('a'*32)).exists())
            self.assertTrue((root/('b'*32)/'image.jpg').exists())
            clear_uploads(root,['a'*32])  # Retry after a lost response is safe.


if __name__=='__main__':
    unittest.main()
