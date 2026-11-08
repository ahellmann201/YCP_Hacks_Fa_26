import unittest
from unittest.mock import patch
import cv2
import numpy as np
from scanner.vision.crop_adjustments import focus_date_ink

# Import the crop function without letting the worker's process-wide offline
# hook change networking for the test runner.
with patch('socket.socket.connect'),patch('socket.socket.connect_ex'),patch('socket.create_connection'):
    from scanner.reading.scanner_auto import prepare_field_crop


class DateCropTests(unittest.TestCase):
    def test_date_crop_excludes_overlapping_barcode_and_keeps_writing(self):
        image=np.full((160,600,3),245,np.uint8)
        cv2.putText(image,'8/12/26',(20,100),cv2.FONT_HERSHEY_SIMPLEX,1.5,(20,20,20),5)
        cv2.line(image,(0,115),(310,115),(80,80,80),1)
        for x in range(330,415,8):
            cv2.rectangle(image,(x,10),(x+3,145),(220,0,0),-1)
        coverage=np.full((160,600),255,np.uint8)
        crop=prepare_field_crop(image,coverage,{'size':(600,160)},'date_sampled',
                                (0,0,.7,1),[],barcode_box=[330,10,415,145])
        red=(crop[:,:,0]>150)&(crop[:,:,1]<30)&(crop[:,:,2]<30)
        self.assertFalse(bool(red.any()))
        self.assertGreater(int((crop[:,:,0]<80).sum()),1000)
        self.assertLess(crop.shape[1],330)

    def test_blank_crop_is_not_forced_into_artificial_text_roi(self):
        image=np.full((80,220,3),245,np.uint8)
        self.assertTrue(np.array_equal(focus_date_ink(image),image))


if __name__=='__main__':
    unittest.main()
