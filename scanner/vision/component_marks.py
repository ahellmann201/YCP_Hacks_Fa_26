"""Conservative black/grey circle candidates for Small-label selections."""


def black_circle_crops(row,label_height):
    import cv2
    import numpy as np
    gray=cv2.cvtColor(row,cv2.COLOR_RGB2GRAY)
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,10)
    ink=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    candidates=[]
    for contour in cv2.findContours(ink,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]:
        if len(contour)<12:
            continue
        (cx,cy),(a,b),angle=cv2.fitEllipse(contour)
        short,long=min(a,b),max(a,b)
        if short<label_height*.055 or long<label_height*.09 or long>label_height*.40 or long/short>3.0:
            continue
        points=contour.reshape(-1,2).astype('float32')-[cx,cy]
        theta=np.deg2rad(angle)
        x=(points[:,0]*np.cos(theta)+points[:,1]*np.sin(theta))/(a/2)
        y=(-points[:,0]*np.sin(theta)+points[:,1]*np.cos(theta))/(b/2)
        radius=np.sqrt(x*x+y*y)
        if float(np.median(np.abs(radius-1)))>.20:
            continue
        bins=np.floor((np.arctan2(y,x)+np.pi)/(2*np.pi)*16).astype(int)%16
        if len(set(bins.tolist()))<12:
            continue
        left,top,width,height=cv2.boundingRect(contour)
        px,py=int(width*.17),int(height*.17)
        crop=row[max(0,top+py):min(row.shape[0],top+height-py),
                 max(0,left+px):min(row.shape[1],left+width-px)]
        interior=ink[max(0,top+py):min(row.shape[0],top+height-py),
                     max(0,left+px):min(row.shape[1],left+width-px)]
        if interior.size and float((interior>0).mean())>.60:
            continue
        if crop.size and float((cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)<100).mean())>.70:
            continue
        if crop.size:
            candidates.append((long*short,(round(cx/15),round(cy/15)),crop))
    selected=[];seen=set()
    for _,key,crop in sorted(candidates,key=lambda item:item[0],reverse=True):
        if key not in seen:
            selected.append((key,crop));seen.add(key)
        if len(selected)>=8:
            break
    return selected
