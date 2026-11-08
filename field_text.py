"""Remove known printed headings; conservatively recognize visually empty crops."""
import re


def strip_heading(value, field, kind):
    value=str(value or '').strip()
    patterns={
        'date_sampled':r'(?:date(?:\s*sampled)?|sampled)',
        'serial_number':r'SN',
    }
    if kind=='large':
        patterns.update(machine=r'(?:equip(?:ment)?\s*[i1l][d0o])',
                        component=r'(?:(?:sample|sampl|ample|mple|ple|le)\s*point|point)',
                        reference_lube=r'(?:ref(?:erence)?\s*lube|lube)')
    else:
        patterns['machine']=r'RN'
    pattern=patterns.get(field)
    if pattern:
        value=re.sub(r'^\s*'+pattern+r'(?=\s|[:;|._-]|$)\s*[:;|._-]*\s*','',value,flags=re.I)
    value=value.strip(' \t:;|')
    return '' if re.fullmatch(r'[-_=—–\s]+',value) else value


def visually_empty(crop):
    import cv2
    import numpy as np
    if crop.shape[0]<30 or crop.shape[1]<80:
        return False
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    background=float(np.median(gray))
    if background<170:
        return False
    ink=(gray<background-12).astype('uint8')
    ignored=np.zeros(gray.shape,dtype=bool)
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink,8)
    for n in range(1,count):
        _,_,width,height,_=stats[n]
        if width>=gray.shape[1]*.7 and height<=max(2,int(gray.shape[0]*.02)):
            ink[labels==n]=0  # A thin printed underline, not a tall text component.
            ignored[labels==n]=True
    remaining=gray[~ignored]
    return int(ink.sum())==0 and remaining.size>0 and int(remaining.max())-int(remaining.min())<=2
