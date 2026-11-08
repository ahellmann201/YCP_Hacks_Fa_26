"""Conservative boundary extension and optional heavy-ink normalization."""


def extend_serial_region(image,template,region):
    import cv2
    import numpy as np
    width,height=template['size'];left,top,right,bottom=region
    original=right
    while right<1.08:
        x1=max(0,round(left*width));x2=min(image.shape[1],round(right*width))
        y1=max(0,round(top*height));y2=min(image.shape[0],round(bottom*height))
        crop=image[y1:y2,x1:x2]
        if crop.shape[0]<20 or crop.shape[1]<20:
            break
        gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
        band=gray[int(gray.shape[0]*.15):int(gray.shape[0]*.75),-max(3,int(width*.006)):]
        if not np.any(band<float(np.median(gray))-35):
            break
        if x2>=image.shape[1]:
            break
        right=min(1.08,right+.04)
    return (left,top,right,bottom),right>original


def thin_heavy_ink(crop):
    import cv2
    import numpy as np
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    if min(gray.shape)<20:
        return None
    _,ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    if not .015<float((ink>0).mean())<.40:
        return None
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink,8)
    text=np.zeros_like(ink)
    for n in range(1,count):
        _,_,width,height,area=stats[n]
        if height>gray.shape[0]*.15 and width<gray.shape[1]*.95 and area>12:
            text[labels==n]=255
    distance=cv2.distanceTransform(text,cv2.DIST_L2,3)
    peaks=distance[(distance>=cv2.dilate(distance,np.ones((3,3),np.uint8))-.01)&(distance>=2)]
    if peaks.size<5 or 2*float(np.median(peaks))*48/gray.shape[0]<2.5:
        return None
    # Shrink dark strokes by approximately one pixel; preserve the original.
    return cv2.dilate(crop,np.ones((2,2),np.uint8))


def prefer_thinned_reading(original,score,candidate,candidate_score,field,received):
    from sample_dates import sampled_date_issue, extract_written_date
    import math
    if not candidate or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in [score,candidate_score]):
        return False
    if candidate_score<.80 or candidate_score<score+.06:
        return False
    if sum(c.isalnum() for c in candidate)<sum(c.isalnum() for c in original):
        return False
    if field=='date_sampled' and (not extract_written_date(candidate) or sampled_date_issue(candidate,received)):
        return False
    return True
