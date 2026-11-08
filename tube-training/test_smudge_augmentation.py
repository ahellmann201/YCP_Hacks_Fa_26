import unittest
import numpy as np
from smudge_augmentation import SmudgeAugment


class SmudgeTests(unittest.TestCase):
    def test_preserves_label_source_and_dimensions(self):
        image=np.full((60,240,3),245,np.uint8)
        image[12:48,40:45]=20
        before=image.copy()
        state=np.random.get_state()
        try:
            np.random.seed(17)
            result=SmudgeAugment(probability=1)({'image':image,'label':'7738'})
        finally:
            np.random.set_state(state)
        self.assertEqual(result['label'],'7738')
        self.assertTrue(np.array_equal(image,before))
        self.assertEqual(result['image'].shape,image.shape)
        self.assertEqual(result['image'].dtype,np.uint8)
        self.assertFalse(np.array_equal(result['image'],image))
        self.assertLess(result['image'][20:40,41:44].mean(),70)

    def test_disabled_leaves_pixels_untouched(self):
        image=np.full((48,120,3),255,np.uint8)
        self.assertIs(SmudgeAugment(0)({'image':image})['image'],image)


if __name__=='__main__':
    unittest.main()
