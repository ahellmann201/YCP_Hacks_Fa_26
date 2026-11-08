"""Compare original and trained Paddle checkpoints on every validation crop."""
import copy
import csv
import json
import os
import sys
from pathlib import Path
from evaluate_recognizer import distance

ROOT=Path(__file__).resolve().parent
run=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else sorted((ROOT/'training-expanded').iterdir())[-1]
sys.path.insert(0,str(ROOT/'PaddleOCR'))
os.chdir(ROOT/'PaddleOCR')
sys.argv=[sys.argv[0],'-c',str(run/'finetune.yml')]
from tools import eval as evaluator
from ppocr.metrics.rec_metric import RecMetric

evaluator.config,evaluator.device,evaluator.logger,_=evaluator.program.preprocess()
original_config=copy.deepcopy(evaluator.config)
results={}


class CaptureMetric(RecMetric):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.predictions=[]

    def __call__(self,values,*args,**kwargs):
        predictions,labels=values
        self.predictions.extend({'prediction':p[0],'confidence':float(p[1]),'expected':t[0]}
                                for p,t in zip(predictions,labels))
        return super().__call__(values,*args,**kwargs)


for name,checkpoint in [('original',None),('trained',str(run/'checkpoints/best_accuracy'))]:
    evaluator.config=copy.deepcopy(original_config)
    evaluator.config['Global']['checkpoints']=checkpoint
    metric=CaptureMetric(**evaluator.config['Metric'])
    evaluator.build_metric=lambda config:metric
    evaluator.main()
    results[name]=metric.predictions

dataset=Path(original_config['Eval']['dataset']['data_dir'])
labels=[line.split('\t',1) for line in (dataset/'val.txt').read_text().splitlines()]
metadata={r['crop']:r for r in map(json.loads,(dataset/'manifest.jsonl').read_text().splitlines())}
assert len(results['original'])==len(results['trained'])==len(labels),'Validation rows skipped'
rows=[]
for (crop,text),before,after in zip(labels,results['original'],results['trained']):
    assert text==before['expected']==after['expected'],'Validation order mismatch'
    meta=metadata[crop]
    rows.append({'tube':meta['tube_id'],'field':meta['field'],'expected':text,
        'original':before['prediction'],'trained':after['prediction'],
        'original_errors':distance(text,before['prediction']),
        'trained_errors':distance(text,after['prediction']),
        'original_confidence':before['confidence'],'trained_confidence':after['confidence'],
        'crop':str(dataset/crop)})
with (run/'prediction-comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(run/'prediction-comparison.json').write_text(json.dumps(rows,indent=2))
for row in rows:print(json.dumps(row,ensure_ascii=True))
print('Saved comparison:',run/'prediction-comparison.csv')
