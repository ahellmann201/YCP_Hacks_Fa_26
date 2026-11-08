import unittest
from types import SimpleNamespace as NS
import cv2
import numpy as np
from label_alignment import tight_large_transform, TIGHT_LARGE_FIELDS


def barcode():
    return NS(position=NS(top_left=NS(x=383,y=156), top_right=NS(x=605,y=156),
                          bottom_right=NS(x=605,y=204), bottom_left=NS(x=384,y=204)))


class AlignmentTests(unittest.TestCase):
    def test_flat_label_keeps_example_values_inside_field_regions(self):
        image=np.zeros((249,778,3),np.uint8)
        transform=tight_large_transform(image,barcode(),{'size':(1200,330)})
        self.assertIsNotNone(transform)
        # Visible value extents from the supplied label, not barcode extrapolation.
        extents={'machine':(155,25,195,62), 'component':(210,75,400,108),
                 'reference_lube':(165,106,235,148), 'date_sampled':(100,159,240,202)}
        for key,(left,top,right,bottom) in extents.items():
            points=np.float32([[[left,top],[right,bottom]]])
            mapped=cv2.perspectiveTransform(points,transform)[0]
            x1,y1,x2,y2=TIGHT_LARGE_FIELDS[key]
            with self.subTest(field=key):
                self.assertGreaterEqual(mapped[0,0],x1*1200)
                self.assertGreaterEqual(mapped[0,1],y1*330)
                self.assertLessEqual(mapped[1,0],x2*1200)
                self.assertLessEqual(mapped[1,1],y2*330)

    def test_normal_camera_frame_keeps_existing_alignment(self):
        self.assertIsNone(tight_large_transform(np.zeros((900,1200,3),np.uint8),barcode(),{'size':(1200,330)}))

    def test_wrong_barcode_location_does_not_trigger_flat_label_path(self):
        code=barcode()
        for point in vars(code.position).values():
            point.y-=140
        self.assertIsNone(tight_large_transform(np.zeros((249,778,3),np.uint8),code,{'size':(1200,330)}))


if __name__=='__main__':
    unittest.main()
