import unittest
import cv2
import numpy as np
from scanner.vision.crop_adjustments import extend_serial_region, thin_heavy_ink, prefer_thinned_reading
from scanner.reading.sample_dates import extract_written_date, sampled_date_issue


class AdjustmentTests(unittest.TestCase):
    def test_serial_edge_ink_extends_boundary_until_clear(self):
        image=np.full((680,1344,3),245,np.uint8)
        region=(.16,.59,.77,.84)
        cv2.rectangle(image,(910,440),(970,490),(20,20,20),-1)
        expanded,changed=extend_serial_region(image,{'size':(1200,680)},region)
        self.assertTrue(changed)
        self.assertGreater(expanded[2]*1200,970)
        self.assertLessEqual(expanded[2],1.08)
        white=np.full_like(image,245)
        self.assertEqual(extend_serial_region(white,{'size':(1200,680)},region),(region,False))

    def test_thick_ink_variant_preserves_original(self):
        image=np.full((80,300,3),245,np.uint8)
        cv2.putText(image,'27',(30,58),cv2.FONT_HERSHEY_SIMPLEX,1.8,(20,20,20),8)
        original=image.copy();variant=thin_heavy_ink(image)
        self.assertIsNotNone(variant)
        self.assertTrue(np.array_equal(image,original))
        self.assertGreater(int(variant.sum()),int(image.sum()))

    def test_retry_cannot_pick_future_year_or_drop_characters(self):
        self.assertFalse(prefer_thinned_reading('4.13.26',.7,'4.13.34',.99,'date_sampled','2026-11-07'))
        self.assertFalse(prefer_thinned_reading('27',.7,'2',.99,'machine','2026-11-07'))
        self.assertFalse(prefer_thinned_reading('27',.8,'27',.82,'machine','2026-11-07'))
        self.assertTrue(prefer_thinned_reading('2',.7,'27',.9,'machine','2026-11-07'))

    def test_dates_do_not_silently_drop_a_year(self):
        self.assertEqual(extract_written_date('4.13+34'),'4.13+34')
        self.assertEqual(extract_written_date('4.13?34'),'')
        self.assertEqual(extract_written_date('812/26'),'8/12/26')
        self.assertEqual(extract_written_date('811226'),'8/12/26')
        self.assertEqual(extract_written_date('111226'),'')
        self.assertEqual(extract_written_date('920'),'9/20')
        self.assertEqual(extract_written_date('1/0'),'')
        self.assertEqual(extract_written_date('92866'),'')
        self.assertEqual(extract_written_date('112'),'')
        self.assertTrue(sampled_date_issue('4.13+34','2026-11-07'))
        self.assertTrue(sampled_date_issue('02/30/2026','2026-11-07'))
        self.assertFalse(sampled_date_issue('04/13/2026','2026-11-07'))
        self.assertFalse(sampled_date_issue('9/20','2026-11-07'))


if __name__=='__main__':
    unittest.main()
