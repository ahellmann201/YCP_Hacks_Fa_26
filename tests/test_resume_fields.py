import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2
from scanner.queue.background_scanner import QueueStore
from scanner.reading.field_text import (
    keep_added_character, keep_complete_page_reading, prefer_explicit_rn,
    repair_lone_i, restore_page_word_gap, separate_number_code, strip_heading,
    visually_empty,
)
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

    def test_a_short_crop_does_not_replace_the_full_label_number(self):
        self.assertEqual(keep_complete_page_reading('27', '2'), '27')
        self.assertEqual(keep_complete_page_reading('53279869', '53279869'), '53279869')
        self.assertEqual(keep_complete_page_reading('UP2642', 'UP7692'), 'UP7692')
        self.assertEqual(keep_added_character('ARING', 'AZRING'), 'AZRING')
        self.assertEqual(keep_added_character('Adjusting side', 'Adiusting side'), 'Adjusting side')
        self.assertEqual(keep_added_character('2', '37'), '2')
        self.assertEqual(separate_number_code('420NPF'), '420 NPF')
        self.assertEqual(separate_number_code('2 GS'), '2 GS')
        self.assertEqual(restore_page_word_gap('A RING', 'AZRING'), 'AZ RING')
        self.assertEqual(restore_page_word_gap('yao NpF', '420NPF'), '420NPF')
        self.assertEqual(repair_lone_i('AEROSHELL I4'), 'AEROSHELL 14')
        self.assertEqual(repair_lone_i('Adjusting side'), 'Adjusting side')
        self.assertEqual(prefer_explicit_rn('UP 2642', 'UP7692'), 'UP2642')
        self.assertEqual(prefer_explicit_rn('UP', 'UP2642'), 'UP2642')
        self.assertEqual(prefer_explicit_rn('UP650C', 'UP6509'), 'UP6509')
        from scanner.reading.scanner_auto import raw_values
        text='Equip ID: 27\nSCANME\nSample point: Rear MoBr'
        self.assertEqual(raw_values(text,'large')['machine'],'27')

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
