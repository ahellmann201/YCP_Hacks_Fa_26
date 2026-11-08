"""Compare three local recognizers with identical preprocessing; never train."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from onnx_recognizer import Recognizer
from date_formats import format_sample_date
from evaluate_recognizer import distance


def formatted_match(field,expected,prediction,two_part='review'):
    if expected==prediction:return True
    if field!='date_sampled':return False
    left=format_sample_date(expected,two_part=two_part)
    right=format_sample_date(prediction,two_part=two_part)
    return bool(left['formatted'] and right['formatted'] and
                left['formatted']==right['formatted'] and left['precision']==right['precision'])


def main():
    root=Path(__file__).resolve().parent.parent
    p=argparse.ArgumentParser()
    p.add_argument('dataset',type=Path,help='Export containing manifest.jsonl and crops/')
    p.add_argument('--original-model',type=Path,help='Original multilingual ONNX; defaults to RapidOCR cached model')
    p.add_argument('--trained-dir',type=Path,default=root/'trained-model/tube_rec')
    p.add_argument('--english-dir',type=Path,default=root/'trained-model/english_rec')
    p.add_argument('--report',type=Path,default=Path('model-comparison-report'))
    p.add_argument('--two-part',choices=['review','month_year'],default='review')
    a=p.parse_args()
    if a.original_model is None:
        import rapidocr
        a.original_model=Path(rapidocr.__file__).parent/'models/ch_PP-OCRv5_rec_mobile.onnx'
    if not a.original_model.is_file():
        raise SystemExit('Original model not found. Pass --original-model PATH. This tool does not download models.')
    entries=[json.loads(line) for line in (a.dataset/'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    entries=[row for row in entries if row['split']=='val' and row['task']=='recognition']
    if not entries:raise SystemExit('No validation recognition crops.')
    a.report.mkdir(parents=True,exist_ok=True)
    model_paths={'original':a.original_model,'trained':a.trained_dir/'recognizer.onnx','english':a.english_dir/'recognizer.onnx'}
    rows=[]
    for name,path in model_paths.items():
        directory=a.trained_dir if name=='original' else path.parent
        recognizer=Recognizer(directory,model_path=path)
        if name=='original':
            chars=recognizer.session.get_modelmeta().custom_metadata_map.get('character')
            if not chars:raise ValueError('Original model must carry its character metadata')
            recognizer.characters=['blank']+chars.splitlines()+[' ']
            if len(recognizer.characters)!=recognizer.session.get_outputs()[0].shape[-1]:raise ValueError('Original dictionary mismatch')
        for entry in entries:
            crop=a.dataset/entry['crop']
            image=cv2.imdecode(np.fromfile(crop,dtype=np.uint8),cv2.IMREAD_COLOR)
            result=recognizer(image);text=result['text']
            prediction=text.upper() if entry['field']=='serial_number' else text
            expected=entry['text']
            formatted=format_sample_date(prediction,two_part=a.two_part) if entry['field']=='date_sampled' else {}
            rows.append({'model':name,'tube_id':entry['tube_id'],'field':entry['field'],
                'expected':expected,'raw_prediction':text,'prediction':prediction,
                'raw_exact':expected==prediction,'formatted_exact':formatted_match(entry['field'],expected,prediction,a.two_part),
                'date_formatted':formatted.get('formatted',''),'date_assumption':formatted.get('assumption') or '',
                'date_status':formatted.get('status',''),'confidence':result['confidence'],
                'character_edits':distance(expected,prediction),'expected_characters':len(expected)})
        print('Compared',name,len(entries),'fields',flush=True)
    def score(items):
        return {'fields':len(items),'raw_correct':sum(r['raw_exact'] for r in items),
                'after_date_formatting_correct':sum(r['formatted_exact'] for r in items),
                'character_error_rate':sum(r['character_edits'] for r in items)/sum(r['expected_characters'] for r in items)}
    summary={'models':{name:score([r for r in rows if r['model']==name]) for name in model_paths},
        'by_field':{name:{field:score([r for r in rows if r['model']==name and r['field']==field])
            for field in sorted({r['field'] for r in rows})} for name in model_paths},
        'two_part_date_policy':a.two_part,
        'model_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in model_paths.items()},
        'note':'Development comparison only. Date formatting is postprocessing, not better OCR. Model selection on these same tubes needs a fresh independent test.'}
    with (a.report/'predictions.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (a.report/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
