"""Bounded synthetic ink transfer and fading, applied only to training crops.

Preserves the main stroke rather than replacing it with an opaque smear.
This teaches recognition robustness, not pixel-level stroke segmentation.
"""
import cv2
import numpy as np


class SmudgeAugment:
    def __init__(self, probability=.55, **kwargs):
        self.probability=float(probability)
        if not 0 <= self.probability <= 1:
            raise ValueError('probability must be between zero and one')

    def __call__(self, data):
        if np.random.rand() >= self.probability:
            return data
        original=data['image']
        image=original.astype(np.float32)
        h,w=image.shape[:2]
        # Transfer a faint, blurred copy of existing ink nearby. It follows
        # real strokes without covering characters with opaque random blobs.
        gray=cv2.cvtColor(original,cv2.COLOR_BGR2GRAY)
        background=cv2.GaussianBlur(gray,(0,0),max(2,h*.12))
        ink=np.clip(background.astype(np.float32)-gray,0,180)
        offset=np.random.uniform(-.055,.055,size=2)*h
        ghost=cv2.warpAffine(ink,np.float32([[1,0,offset[0]],[0,1,offset[1]]]),(w,h))
        ghost=cv2.GaussianBlur(ghost,(0,0),max(.6,h*np.random.uniform(.012,.035)))
        image-=ghost[:,:,None]*np.random.uniform(.15,.40)
        # Gentle local fading varies pen pressure while retaining legibility.
        x,y=np.meshgrid(np.arange(w),np.arange(h))
        cx,cy=np.random.uniform(0,w),np.random.uniform(0,h)
        fade=np.exp(-((x-cx)**2+(y-cy)**2)/(2*max(h*.65,1)**2))
        image+=(255-image)*fade[:,:,None]*np.random.uniform(.05,.18)
        data['image']=np.clip(image,0,255).astype(np.uint8)
        return data
