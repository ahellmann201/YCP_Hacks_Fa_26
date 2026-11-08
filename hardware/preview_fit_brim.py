"""Render the actual first-layer extrusion paths, checking all four brims."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math, re, zipfile
root=Path(__file__).resolve().parent/'final files'
with zipfile.ZipFile(root/'00_boltless_fit_test_P1P_PLA.gcode.3mf') as z:
    text=z.read('Metadata/plate_1.gcode').decode()
layer=text.split('; CHANGE_LAYER')[1]
x=y=None
feature=''
obj=None
paths=[]
brim_objects=set()
for line in layer.splitlines():
    if line.startswith('; FEATURE: '): feature=line.split(': ',1)[1]
    if line.startswith('; OBJECT_ID: '): obj=line.split(': ',1)[1]
    if not re.match(r'^G[0123] ',line): continue
    args={k:float(v) for k,v in re.findall(r'([XYEIJ])(-?\d*\.?\d+)',line.split(';')[0])}
    nx,ny=args.get('X',x),args.get('Y',y)
    if x is not None and y is not None and any(k in args for k in ('X','Y','I','J')) and args.get('E',0)>0:
        if line.startswith(('G2 ','G3 ')):
            cx,cy=x+args.get('I',0),y+args.get('J',0)
            radius=math.hypot(x-cx,y-cy)
            a0=math.atan2(y-cy,x-cx); a1=math.atan2(ny-cy,nx-cx)
            sweep=(a1-a0)%(2*math.pi)
            if line.startswith('G2 '): sweep-=2*math.pi
            elif abs(sweep)<1e-9: sweep=2*math.pi
            steps=max(4,math.ceil(abs(sweep)*radius/0.3))
            arc=[(cx+radius*math.cos(a0+sweep*i/steps),cy+radius*math.sin(a0+sweep*i/steps)) for i in range(steps+1)]
            paths.extend((a,b,feature) for a,b in zip(arc,arc[1:]))
        else: paths.append(((x,y),(nx,ny),feature))
        if feature=='Brim': brim_objects.add(obj)
    x,y=nx,ny
assert len(brim_objects)==4, brim_objects
points=[p for a,b,_ in paths for p in (a,b)]
x0=min(p[0] for p in points); x1=max(p[0] for p in points)
y0=min(p[1] for p in points); y1=max(p[1] for p in points)
assert x0>=18 and y0>=28 and x1<256 and y1<256
im=Image.new('RGB',(1300,570),'#f8fafc'); d=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
title=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',31)
d.text((45,25),'FIT TEST - ACTUAL FIRST-LAYER TOOLPATH',font=title,fill='#152b42')
d.text((45,75),'Orange: removable 6 mm outer brim     Blue: printed part',font=font,fill='#334155')
scale=min(1200/(x1-x0),340/(y1-y0))
def screen(p): return (50+(p[0]-x0)*scale,440-(p[1]-y0)*scale)
for a,b,f in paths:
    d.line([screen(a),screen(b)],fill='#e58627' if f=='Brim' else '#174f78',width=2)
d.text((45,495),'Let the plate cool, then remove the thin brim before testing the locking fit.',font=font,fill='#334155')
im.save(root/'00_fit_test_BRIM_first_layer.png')
print('PASS: four brim objects, extrusion bounds', [round(v,2) for v in [x0,y0,x1,y1]])
