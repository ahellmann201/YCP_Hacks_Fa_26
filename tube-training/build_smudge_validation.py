"""Create a fixed development stress suite from validation crops only.

Variants are correlated copies, not additional independent test tubes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from smudge_augmentation import SmudgeAugment


def build(dataset, output):
    entries=[json.loads(line) for line in (dataset/'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    selected=[r for r in entries if r['split']=='val' and r.get('task')=='recognition']
    if not selected:
        raise ValueError('No held-out recognition crops')
    train_groups={r['group_id'] for r in entries if r['split']=='train'}
    train_sources={r['source_sha256'] for r in entries if r['split']=='train'}
    if any(r['group_id'] in train_groups or r['source_sha256'] in train_sources for r in selected):
        raise ValueError('Training/validation overlap')
    output.mkdir(parents=True,exist_ok=False)
    (output/'crops').mkdir()
    rows=[]
    for index,row in enumerate(selected):
        image=cv2.imdecode(np.fromfile(dataset/row['crop'],dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('Unreadable crop')
        for variant in range(4):
            np.random.seed(21000+index*10+variant)
            modified=image if variant==0 else SmudgeAugment(1)({'image':image.copy()})['image']
            crop=f'crops/{index:03}_{variant}.png'
            encoded=cv2.imencode('.png',modified)[1]
            encoded.tofile(output/crop)
            rows.append(dict(row,crop=crop,variant='clean' if variant==0 else f'synthetic_smudge_{variant}',
                             crop_sha256=hashlib.sha256(encoded.tobytes()).hexdigest()))
    (output/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (output/'val.txt').write_text(''.join(r['crop']+'\t'+r['text']+'\n' for r in rows),encoding='utf-8')
    print(f'{len(rows)} variants from {len(selected)} held-out fields; {len(set(r["group_id"] for r in rows))} tubes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    build(a.dataset,a.output)
