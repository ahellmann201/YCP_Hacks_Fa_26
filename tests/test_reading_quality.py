import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from scanner.reading.reading_quality import crop_quality, guard_readings
from scanner.queue.background_scanner import QueueStore, ScannerQueue


class QualityTests(unittest.TestCase):
    def test_worker_autofills_and_keeps_raw_snapshot_for_accuracy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);record='a'*32;folder=root/'uploads'/record;folder.mkdir(parents=True)
            store=QueueStore(root/'scanner.sqlite3');sid=store.create('quality')['id']
            fields={'sample_id':'1','machine':'2','component':'Rear','reference_lube':'SKF','date_sampled':'4.13.26'}
            result={'label_type':'large','suggestions':fields,'alternatives':{},'images':[
                {'filename':'image_1.jpg','label_type':'large','fields':fields,'debug':[],
                 'field_scores':{'machine':.8,'component':.99,'reference_lube':.99,'date_sampled':.99}}]}
            (folder/'sample.json').write_text(json.dumps({'date_received':'2026-11-07','images':[{'filename':'image_1.jpg'}]}))
            store.register(sid,record);queue=ScannerQueue(store,root)
            def child(command,timeout):
                Path(command[-1]).write_text(json.dumps(result))
            with patch.object(queue,'child',side_effect=child):
                queue.process(store.claim())
            review=store.sample(record)['review']
            self.assertEqual(review['fields']['machine'],'2')
            self.assertEqual(review['ocr_candidates']['machine'],['2'])
            self.assertEqual(review['original_fields']['machine'],'2')
            corrected=dict(review['fields'],machine='27')
            store.edit(sid,record,corrected,'large',True)
            self.assertEqual(store.status(sid)['metrics']['field_accuracy_percent'],80)

    def result(self, fields, score):
        return {'images':[{'fields':fields,'field_scores':{key:score for key in fields}}]}

    def test_uncertain_handwriting_autofills_with_review_hints(self):
        fields={'machine':'2','component':'Rea Mnbr'}
        accepted,candidates,reasons=guard_readings(fields,'large',self.result(fields,.8),'2026-11-07')
        self.assertEqual(accepted,fields)
        self.assertEqual(candidates['machine'],['2'])
        self.assertEqual(candidates['component'],['Rea Mnbr'])
        self.assertTrue(reasons['machine'])
        self.assertEqual(fields['machine'],'2')

    def test_future_date_is_flagged_without_inventing_correct_year(self):
        fields={'date_sampled':'4.13.34'}
        accepted,candidates,reasons=guard_readings(fields,'large',self.result(fields,.99),'2026-11-07')
        self.assertEqual(accepted['date_sampled'],'4.13.34')
        self.assertEqual(candidates['date_sampled'],['4.13.34'])
        self.assertIn('Date Received',reasons['date_sampled'][0])

    def test_clear_readings_and_small_circled_selections_are_retained(self):
        fields={'machine':'UP6509','component':'4 GS','sample_id':'111329'}
        accepted,candidates,_=guard_readings(fields,'small',self.result(fields,.99),'2026-11-07')
        self.assertEqual(accepted,fields)
        self.assertEqual(candidates,{})

    def test_dense_patch_is_reviewed_not_classified_as_blank(self):
        crop=np.full((90,300,3),245,np.uint8)
        cv2.rectangle(crop,(60,10),(170,75),(30,30,30),-1)
        reasons=crop_quality(crop)
        self.assertTrue(reasons)
        fields={'machine':'AB'};result=self.result(fields,.99)
        result['images'][0]['field_quality']={'machine':reasons}
        accepted,candidates,_=guard_readings(fields,'large',result,'2026-11-07')
        self.assertEqual(accepted['machine'],'AB')
        self.assertEqual(candidates['machine'],['AB'])
        self.assertNotIn('blank_fields',result)


if __name__=='__main__':
    unittest.main()
