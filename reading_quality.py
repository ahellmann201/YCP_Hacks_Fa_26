"""Autofill OCR readings with review hints; never guess corrections or call smears blank."""
from datetime import date
import math
import re


def crop_quality(crop):
    import cv2
    import numpy as np
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    background=float(np.median(gray))
    ink=(gray<background-30).astype('uint8')
    count,_,stats,_=cv2.connectedComponentsWithStats(ink,8)
    reasons=[]
    for n in range(1,count):
        _,_,width,height,area=stats[n]
        if area>gray.size*.12 and height>gray.shape[0]*.55 and area/(width*height)>.60:
            reasons.append('Large dense ink patch — possible smear or obstruction; check the original.')
            break
    if float(ink.mean())>.01 and float(cv2.Laplacian(gray,cv2.CV_64F).var())<15:
        reasons.append('Blurred or faint strokes — check the original.')
    return reasons


def guard_readings(fields, kind, result, received):
    accepted=dict(fields); candidates={}; withheld={}
    for field in ['machine','date_sampled','serial_number','component','reference_lube']:
        value=fields.get(field,'')
        if field=='component' and kind=='small':
            continue
        if not value:
            reasons=list(dict.fromkeys(reason for image in result.get('images',[])
                for reason in image.get('field_quality',{}).get(field,[])))
            if reasons:
                withheld[field]=reasons
            continue
        readings=[image for image in result.get('images',[]) if
                  str(image.get('fields',{}).get(field) or '').strip().casefold()==str(value).strip().casefold()]
        scores=[image.get('field_scores',{}).get(field) for image in readings]
        reasons=[]
        if not scores or any(not isinstance(score,(int,float)) or not math.isfinite(score) for score in scores):
            reasons.append('OCR certainty is unavailable; verify this reading against the crop.')
        elif min(scores)<.95:
            reasons.append('Uncertain handwriting — verify this reading against the crop.')
        for image in readings:
            for reason in image.get('field_quality',{}).get(field,[]):
                if reason not in reasons:
                    reasons.append(reason)
        if field=='date_sampled':
            match=re.fullmatch(r'(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})',str(value))
            if match:
                month,day,year=map(int,match.groups())
                year=year+2000 if year<100 else year
                try:
                    if date(year,month,day)>date.fromisoformat(received):
                        reasons.append('Read date is after Date Received; verify its digits, especially the year.')
                except ValueError:
                    reasons.append('Read date is not a valid calendar date.')
        if reasons:
            candidates[field]=[str(value)]
            withheld[field]=reasons
    for field,values in result.get('alternatives',{}).items():
        if not accepted.get(field) and values:
            candidates[field]=list(dict.fromkeys(str(value) for value in values))
    return accepted,candidates,withheld
