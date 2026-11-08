"""Small stroke-width variations; no label edits or simulated unreadable smears."""
import cv2
import numpy as np


class MarkerStrokeAugment:
    def __init__(self,**kwargs):
        pass

    def __call__(self,data):
        if np.random.rand()<.55:
            return data
        image=data['image']
        size=max(2,min(5,round(image.shape[0]/48)))
        kernel=np.ones((size,size),np.uint8)
        # Eroding a light image thickens its dark strokes. A smaller fraction
        # gets the reverse operation to vary the width of existing marker ink.
        image=cv2.erode(image,kernel) if np.random.rand()<.75 else cv2.dilate(image,kernel)
        data['image']=image
        return data
