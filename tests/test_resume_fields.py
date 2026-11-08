import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2
from scanner.queue.background_scanner import QueueStore
from scanner.reading.field_text import strip_heading, visually_empty
from scanner.reading.review_checks import field_checks


class ResumeFieldTests(unittest.TestCase):
    def test_unfinished_sessions_survive_restart_excluding_empty_and_finished(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'scanner.sqlite3';store=QueueStore(path)
            empty=store.create('empty')['id']
            open_id=store.create('open')['id'];store.register(open_id,'a'*32)
            store.complete(store.claim(),{'fields':{'machine':'old'},'label_type':'small'},[])
            store.edit(open_id,'a'*32,{'machine':'corrected'},'small',False)
            closed=store.create('closed')['id'];store.register(closed,'b'*32);store.finish(closed)
            restarted=QueueStore(path)
            self.assertEqual([s['id'] for s in restarted.unfinished()],[open_id])
            self.assertEqual(restarted.status(open_id)['jobs'][0]['review']['fields']['machine'],'corrected')
            new=restarted.create('new')['id']
            self.assertNotEqual(new,open_id)
            self.assertEqual(restarted.unfinished()[0]['id'],open_id)

    def test_printed_prefixes_are_removed_without_guessing_missing_characters(self):
        self.assertEqual(strip_heading('EqUipID: HSCN GPS HNTENNA','machine','large'),'HSCN GPS HNTENNA')
        self.assertEqual(strip_heading('ple point:ARING','component','large'),'ARING')
        self.assertEqual(strip_heading('Ref Lube: AEROSHELL 14','reference_lube','large'),'AEROSHELL 14')
        self.assertEqual(strip_heading('UP6509','machine','small'),'UP6509')
        self.assertEqual(strip_heading('RN: UP6509','machine','small'),'UP6509')
        self.assertEqual(strip_heading('POINTMASTER','component','large'),'POINTMASTER')
        self.assertEqual(strip_heading('Ref Lube: ___','reference_lube','large'),'')

    def test_blank_detector_rejects_faint_text_and_dark_photos(self):
        white=np.full((80,220,3),240,np.uint8)
        self.assertTrue(visually_empty(white))
        ruled=white.copy();cv2.line(ruled,(0,68),(219,68),(30,30,30),1)
        self.assertTrue(visually_empty(ruled))
        written=white.copy();cv2.putText(written,'1',(20,45),cv2.FONT_HERSHEY_SIMPLEX,1,(200,200,200),1)
        self.assertFalse(visually_empty(written))
        very_faint=white.copy();very_faint[20:40,50:52]=236
        self.assertFalse(visually_empty(very_faint))
        self.assertFalse(visually_empty(np.full((80,220,3),100,np.uint8)))
        self.assertEqual(field_checks({'date_sampled':''},'large',{'blank_fields':['date_sampled']})['date_sampled'],[])


if __name__=='__main__':
    unittest.main()
