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
    from scanner.reading.sample_dates import sampled_date_issue, extract_written_date
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


def focus_date_ink(crop,minimum_width_fraction=.35):
    """Tighten evidence around tall date strokes, retaining the original pixels."""
    import cv2
    import numpy as np
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    height,width=gray.shape
    if height<20 or width<40:
        return crop
    ink=(gray<float(np.median(gray))-35).astype('uint8')*255
    rule=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(25,int(width*.55))),np.uint8))
    foreground=cv2.bitwise_and(ink,cv2.bitwise_not(rule))
    count,_,stats,_=cv2.connectedComponentsWithStats(foreground,8)
    components=[(x,y,w,h,area) for x,y,w,h,area in stats[1:]
                if h>=height*.18 and w>=2 and area>=8 and not (w<3 and h>height*.9)]
    if not components:
        return crop
    tallest=max(component[3] for component in components)
    components=[c for c in components if c[3]>=tallest*.45]
    left=min(c[0] for c in components);top=min(c[1] for c in components)
    right=max(c[0]+c[2] for c in components);bottom=max(c[1]+c[3] for c in components)
    if right-left<width*minimum_width_fraction or bottom-top<height*.25:
        return crop
    padding=max(3,round(height*.07))
    return crop[max(0,top-padding):min(height,bottom+padding),
                max(0,left-padding):min(width,right+padding)].copy()


def tighten_field_right(crop):
    """Second-stage right-edge trim; original top/left/bottom pixels stay intact."""
    import cv2
    import numpy as np
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    height,width=gray.shape
    if height<20 or width<50:
        return crop
    ink=(gray<float(np.median(gray))-35).astype('uint8')*255
    rule=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(25,int(width*.5))),np.uint8))
    foreground=cv2.bitwise_and(ink,cv2.bitwise_not(rule))
    count,_,stats,_=cv2.connectedComponentsWithStats(foreground,8)
    components=[]
    for x,y,w,h,area in stats[1:]:
        if h<height*.18 or area<8:
            continue
        # A narrow crease spanning both image boundaries is not a text ending.
        # Never discard a detached/short digit solely because it is thin.
        if x>width*.45 and y<=2 and y+h>=height-2 and w<max(4,height*.12):
            continue
        components.append((x,y,w,h,area))
    if not components:
        return crop
    tallest=max(c[3] for c in components)
    main=[c for c in components if c[3]>=tallest*.60]
    if not main:
        return crop
    right=max(c[0]+c[2] for c in main)
    # Retain smaller following strokes/separators in the same vertical text band.
    top=min(c[1] for c in main);bottom=max(c[1]+c[3] for c in main)
    band_top=top+(bottom-top)*.20
    band_bottom=bottom-(bottom-top)*.20
    for x,y,w,h,area in components:
        center=y+h/2
        if h>=max(3,tallest*.20) and band_top<=center<=band_bottom:
            right=max(right,x+w)
    right=min(width,right+max(8,round(height*.15)))
    if right>=width-max(5,int(width*.03)) or right<20:
        return crop
    return crop[:,:right].copy()


def refine_field_crop(crop,field,trim_right=False):
    if trim_right:
        crop=tighten_field_right(crop)
    return focus_date_ink(crop) if field=='date_sampled' else crop


def can_fill_empty_from_focus(original,candidate,score,field,received,quality_reasons):
    import math
    from scanner.reading.sample_dates import extract_written_date,sampled_date_issue
    if original or not candidate or not isinstance(score,(int,float)) or not math.isfinite(score) or score<.95 or quality_reasons:
        return False
    return field!='date_sampled' or bool(extract_written_date(candidate) and not sampled_date_issue(candidate,received))
