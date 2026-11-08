import unittest
import cv2
import numpy as np
from scanner.vision.component_marks import black_circle_crops


class ComponentMarksTests(unittest.TestCase):
    def test_grey_rings_are_found_without_blue_ink(self):
        image=np.full((200,1200,3),255,np.uint8)
        cv2.putText(image,'2',(170,120),cv2.FONT_HERSHEY_SIMPLEX,2,(0,0,0),3)
        cv2.putText(image,'NGS',(850,120),cv2.FONT_HERSHEY_SIMPLEX,2,(0,0,0),3)
        cv2.ellipse(image,(190,95),(40,55),0,0,360,(70,70,70),3)
        cv2.ellipse(image,(910,95),(85,55),0,0,360,(70,70,70),3)
        centers=[key[0]*15 for key,crop in black_circle_crops(image,680)]
        self.assertTrue(any(abs(x-190)<20 for x in centers))
        self.assertTrue(any(abs(x-910)<20 for x in centers))

    def test_solid_ink_blob_is_not_a_selection_ring(self):
        image=np.full((200,1200,3),255,np.uint8)
        cv2.ellipse(image,(190,95),(40,55),0,0,360,(0,0,0),-1)
        self.assertEqual(black_circle_crops(image,680),[])
