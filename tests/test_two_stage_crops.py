import unittest
import cv2
import numpy as np
from crop_adjustments import tighten_field_right,can_fill_empty_from_focus


class TwoStageTests(unittest.TestCase):
    def test_right_trim_keeps_thin_last_digit_and_original_height(self):
        image=np.full((90,700,3),245,np.uint8)
        cv2.putText(image,'2',(20,65),cv2.FONT_HERSHEY_SIMPLEX,1.8,(20,20,20),4)
        cv2.putText(image,'7',(62,65),cv2.FONT_HERSHEY_SIMPLEX,1.8,(20,20,20),1)
        cv2.line(image,(0,68),(699,68),(60,60,60),1)
        cv2.rectangle(image,(350,78),(380,89),(20,20,20),-1)
        before=image.copy();cropped=tighten_field_right(image)
        self.assertEqual(cropped.shape[0],90)
        self.assertLess(cropped.shape[1],200)
        self.assertGreater(cropped.shape[1],95)
        self.assertTrue(np.array_equal(cropped,image[:,:cropped.shape[1]]))
        self.assertTrue(np.array_equal(image,before))

    def test_blank_is_unchanged(self):
        image=np.full((80,600,3),245,np.uint8)
        self.assertIs(tighten_field_right(image),image)

    def test_higher_confidence_disagreement_cannot_replace_existing_27(self):
        self.assertFalse(can_fill_empty_from_focus('27','37',.99,'machine','2026-11-08',[]))
        self.assertTrue(can_fill_empty_from_focus('','27',.99,'machine','2026-11-08',[]))
        self.assertFalse(can_fill_empty_from_focus('','27',.8,'machine','2026-11-08',[]))
        self.assertFalse(can_fill_empty_from_focus('','4.13.34',.99,'date_sampled','2026-11-08',[]))


if __name__=='__main__':
    unittest.main()
