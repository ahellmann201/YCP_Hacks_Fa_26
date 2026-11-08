"""Locate Large-label underline rows without extra OCR or a learned model."""
from itertools import product


def large_row_regions(image, template):
    import cv2
    import numpy as np
    width, height=template['size']
    gray=cv2.cvtColor(image[:height,:width],cv2.COLOR_RGB2GRAY)
    _,dark=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    qr_candidates=[]
    for contour in cv2.findContours(dark,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]:
        x,y,w,h=cv2.boundingRect(contour)
        area=cv2.contourArea(contour)
        if (x>width*.60 and y<height*.60 and w>width*.10 and h>height*.30
            and .65<w/h<1.6 and area/(w*h)>.75):
            qr_candidates.append((area,x))
    qr_left=max(qr_candidates)[1] if qr_candidates else None
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                             cv2.THRESH_BINARY_INV,31,13)
    # Keep QR frames out of the line detector; the barcode is removed by
    # rejecting vertical/steep segments and implausible row spacing.
    ink[:,int(width*.77):]=0
    lines=cv2.HoughLinesP(ink,1,np.pi/180,60,minLineLength=int(width*.24),maxLineGap=int(width*.025))
    if lines is None:
        return None
    segments=[]
    for x1,y1,x2,y2 in np.asarray(lines).reshape(-1,4):
        if x2<x1:
            x1,y1,x2,y2=x2,y2,x1,y1
        if abs(y2-y1)>height*.06 or x2-x1<width*.24:
            continue
        y=(y1+y2)/2
        if height*.10<y<height*.97:
            segments.append((float(y),int(x1),int(x2),int(min(y1,y2)),int(max(y1,y2))))
    groups=[]
    for segment in sorted(segments):
        if groups and abs(segment[0]-groups[-1][0][0])<max(3,height*.025):
            groups[-1].append(segment)
        else:
            groups.append([segment])
    rows=[]
    for group in groups:
        longest=max(group,key=lambda s:s[2]-s[1])
        rows.append((longest[0],min(s[1] for s in group),max(s[2] for s in group),
                     min(s[3] for s in group),max(s[4] for s in group)))
    windows=[(.12,.35),(.30,.53),(.48,.73),(.68,.96)]
    choices=[sorted([r for r in rows if low*height<r[0]<high*height],
                    key=lambda r:r[2]-r[1],reverse=True)[:4] for low,high in windows]
    if any(not options for options in choices):
        return None
    best=None;best_score=-float('inf')
    for candidate in product(*choices):
        positions=np.array([row[0] for row in candidate])
        gaps=np.diff(positions)
        if min(gaps)<height*.10 or max(gaps)>height*.30 or max(gaps)>min(gaps)*1.65:
            continue
        score=sum((r[2]-r[1])/width for r in candidate)-float(gaps.std()/gaps.mean())*4
        if score>best_score:
            best,best_score=candidate,score
    if best is None:
        return None
    spacing=float(np.median(np.diff([row[0] for row in best])))
    regions={}
    for index,field in enumerate(['machine','component','reference_lube','date_sampled']):
        row=best[index]
        x1,_,x2,_=template['fields'][field]
        # Never move the left boundary inward and risk losing an initial digit.
        left=min(x1*width,max(x1*width-width*.03,row[1]-width*.015))
        right=x2*width
        expected_end=.35 if field=='date_sampled' else .55
        if row[2]>width*expected_end and row[2]>left+width*.2:
            right=min(right,row[2]+width*.005)
        if field!='date_sampled' and qr_left is not None and qr_left-left>width*.25:
            right=min(right,qr_left-width*.005)
        top=(best[index-1][0]+spacing*.12) if index else row[3]-spacing*1.10
        bottom=row[4]+spacing*.20  # Preserve j/g/y descenders below the underline.
        regions[field]=(max(0,left)/width,max(0,top)/height,min(width,right)/width,min(height,bottom)/height)
    return {'regions':regions,'baselines':[round(row[0],1) for row in best], 'qr_left':qr_left,
            'numeric_bottoms':{'machine':min(height,best[0][4]+1),
                               'date_sampled':min(height,best[3][4]+1)}}
