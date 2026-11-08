import unittest
from unittest.mock import patch
import numpy as np
from marker_augmentation import MarkerStrokeAugment


class MarkerAugmentationTests(unittest.TestCase):
    def test_thickening_changes_pixels_not_transcription_or_original(self):
        image=np.full((48,120,3),245,np.uint8);image[10:35,40:43]=20
        original=image.copy();data={'image':image,'label':'27'}
        with patch('numpy.random.rand',side_effect=[.9,.1]):
            result=MarkerStrokeAugment()(data)
        self.assertEqual(result['label'],'27')
        self.assertLess(int(result['image'].sum()),int(original.sum()))
        self.assertTrue(np.array_equal(image,original))

    def test_unchanged_path_preserves_image(self):
        image=np.full((48,120,3),245,np.uint8)
        with patch('numpy.random.rand',return_value=.1):
            result=MarkerStrokeAugment()({'image':image,'label':'9/20'})
        self.assertIs(result['image'],image)
        self.assertEqual(result['label'],'9/20')


if __name__=='__main__':
    unittest.main()
