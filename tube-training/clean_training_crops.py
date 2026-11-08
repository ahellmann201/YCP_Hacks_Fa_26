"""Apply an audited crop recipe to a copy; leave validation bytes unchanged."""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from PIL import Image


def build(source,output,recipe,image_manifest=None):
    if output.exists():raise ValueError('Choose a new output directory to preserve previous data')
    rows=[json.loads(s) for s in (source/'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    images={r['image_id']:r for r in json.loads(image_manifest.read_text())} if image_manifest else {}
    image_root=image_manifest.parent if image_manifest else None
    groups={};hashes={}
    for row in rows:
        for mapping,key in [(groups,row['group_id']),(hashes,row['source_sha256'])]:
            if key in mapping and mapping[key]!=row['split']:raise ValueError('Train/validation overlap')
            mapping[key]=row['split']
    (output/'crops').mkdir(parents=True)
    selected=[];audit=[];seen=set()
    for row in rows:
        if row['task']!='recognition':continue
        operation=recipe.get(row['id'],{}) if row['split']=='train' else {}
        if operation.get('exclude'):
            audit.append({'id':row['id'],'action':'exclude','reason':operation['exclude']});continue
        original=source/row['crop'];target=output/row['crop']
        if row['split']=='val':shutil.copy2(original,target)
        else:
            with Image.open(original) as im:crop=im.convert('RGB')
            if 'expand_top' in operation:
                info=images[row['image_id']];points=row.get('source_polygon')
                if not points:
                    left,top,right,bottom=row['box'];points=[(left,top),(right,top),(right,bottom),(left,bottom)]
                points=[list(p) for p in points]
                for i in [0,1]:points[i][1]=max(0,points[i][1]-operation['expand_top'])
                with Image.open(image_root/info['image']) as im:
                    im=im.rotate(-row.get('rotation',0)).convert('RGB')
                    width=round(math.dist(points[0],points[1]));height=round(math.dist(points[0],points[3]))
                    quad=[v for i in [0,3,2,1] for v in points[i]]
                    crop=im.transform((width,height),Image.Transform.QUAD,quad,Image.Resampling.BICUBIC)
            if 'trim' in operation:
                left,top,right,bottom=operation['trim']
                crop=crop.crop((round(left*crop.width),round(top*crop.height),round(right*crop.width),round(bottom*crop.height)))
            digest=hashlib.sha256(crop.tobytes()+str(crop.size).encode()).hexdigest()
            if digest in seen:
                audit.append({'id':row['id'],'action':'exclude','reason':'Exact duplicate training pixels'});continue
            seen.add(digest);crop.save(target)
            if operation:audit.append({'id':row['id'],'action':'recrop','operation':operation})
        selected.append(row)
    (output/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
    lines=[r['crop']+'\t'+r['text'] for r in selected if r['split']=='train']
    (output/'train.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    shutil.copy2(source/'val.txt',output/'val.txt')
    for row in selected:
        if row['split']=='val':assert (source/row['crop']).read_bytes()==(output/row['crop']).read_bytes()
    report={'source':str(source),'training_crops':len(lines),'validation_crops':sum(r['split']=='val' for r in selected),
            'validation_unchanged':True,'audit':audit,'note':'Recipe is visually audited by assistant; existing labels are not independently verified.'}
    (output/'cleanup-report.json').write_text(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--recipe',type=Path,required=True);p.add_argument('--image-manifest',type=Path)
    a=p.parse_args();print(json.dumps(build(a.source.resolve(),a.output.resolve(),json.loads(a.recipe.read_text()),a.image_manifest.resolve() if a.image_manifest else None),indent=2))
