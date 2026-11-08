"""Geometry checks for tightly framed, flat Large-label images."""

TIGHT_LARGE_FIELDS = {
    'machine':(.17,.01,.73,.27),
    'component':(.24,.26,.76,.45),
    'reference_lube':(.18,.40,.79,.62),
    'date_sampled':(.10,.60,.46,.91),
}


def tight_large_transform(image, barcode, template):
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    if not 2.7 <= width/height <= 4.5:
        return None
    p = barcode.position
    points = np.float32([[p.top_left.x,p.top_left.y], [p.top_right.x,p.top_right.y],
                         [p.bottom_right.x,p.bottom_right.y], [p.bottom_left.x,p.bottom_left.y]])
    left, top = points.min(axis=0)/[width,height]
    right, bottom = points.max(axis=0)/[width,height]
    # A wide, upright photo plus the expected lower-right linear barcode
    # identifies a cropped flat label, not an ordinary full camera frame.
    if not (.28 <= left < right <= .96 and .48 <= top < bottom <= .99
            and .17 <= right-left <= .65 and .06 <= bottom-top <= .38):
        return None
    if abs(p.top_left.y-p.top_right.y)/height > .10:
        return None
    target_width, target_height = template['size']
    source = np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    target = np.float32([[0,0],[target_width-1,0],
                         [target_width-1,target_height-1],[0,target_height-1]])
    return cv2.getPerspectiveTransform(source,target)
