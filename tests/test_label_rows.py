import unittest
import cv2
import numpy as np
from label_rows import large_row_regions
from label_alignment import TIGHT_LARGE_FIELDS


class RowTests(unittest.TestCase):
    def template(self):
        return {'size':(1200,330), 'fields':TIGHT_LARGE_FIELDS}

    def label(self):
        image=np.full((330,1344,3),245,np.uint8)
        for (left,right),y in zip([(.17,.73),(.24,.73),(.18,.73),(.10,.46)],[65,125,185,245]):
            for x in range(int(left*1200),int(right*1200),35):
                cv2.line(image,(x,y),(min(x+27,int(right*1200)),y),(50,50,50),1)
        return image

    def test_finds_four_dashed_rows_and_preserves_descender_padding(self):
        image=self.label()
        cv2.circle(image,(450,194),2,(30,30,30),-1)
        result=large_row_regions(image,self.template())
        self.assertIsNotNone(result)
        for actual,expected in zip(result['baselines'],[65,125,185,245]):
            self.assertLess(abs(actual-expected),4)
        self.assertGreaterEqual(result['regions']['reference_lube'][3]*330,196)
        self.assertLess(result['regions']['reference_lube'][1]*330,145)

    def test_qr_frame_is_excluded_from_field_right_edge(self):
        image=self.label();cv2.rectangle(image,(900,15),(1090,180),(20,20,20),5)
        result=large_row_regions(image,self.template())
        self.assertIsNotNone(result)
        self.assertIsNotNone(result['qr_left'])
        self.assertLess(result['regions']['reference_lube'][2]*1200,900)

    def test_missing_or_incomplete_lines_keep_template_fallback(self):
        image=np.full((330,1344,3),245,np.uint8)
        self.assertIsNone(large_row_regions(image,self.template()))
        for y in [65,125,185]:
            cv2.line(image,(240,y),(870,y),(50,50,50),1)
        self.assertIsNone(large_row_regions(image,self.template()))


if __name__=='__main__':
    unittest.main()
