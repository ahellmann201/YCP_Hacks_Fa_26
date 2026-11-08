"""Record field predictions and date-format scores for a Paddle checkpoint."""
import argparse
import json
import sys
from pathlib import Path
from compare_recognizers import formatted_match
from evaluate_recognizer import distance

p=argparse.ArgumentParser()
for name in ['repo','config','weights','output']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.repo.resolve()))
sys.argv=[sys.argv[0],'-c',str(a.config.resolve()),'-o','Global.checkpoints=null','Global.use_gpu=False',
          'Global.pretrained_model='+str(a.weights.resolve())]
from tools import eval as evaluator
from ppocr.metrics.rec_metric import RecMetric
evaluator.config,evaluator.device,evaluator.logger,_=evaluator.program.preprocess()


class CaptureMetric(RecMetric):
    def __init__(self,**kwargs):super().__init__(**kwargs);self.rows=[]
    def __call__(self,result,*args,**kwargs):
        self.rows.extend({'prediction':p[0],'expected':t[0],'confidence':float(p[1])} for p,t in zip(*result))
        return super().__call__(result,*args,**kwargs)


metric=CaptureMetric(**evaluator.config['Metric']);evaluator.build_metric=lambda config:metric
evaluator.main()
dataset=Path(evaluator.config['Eval']['dataset']['data_dir'])
all_rows=[json.loads(s) for s in (dataset/'manifest.jsonl').read_text().splitlines()]
lookup={r['crop']:r for r in all_rows}
labels=[s.split('\t',1) for s in (dataset/'val.txt').read_text().splitlines()]
assert len(labels)==len(metric.rows),'Validation rows skipped'
for (crop,text),row in zip(labels,metric.rows):
    assert text==row['expected'],'Validation order changed'
    row['field']=lookup[crop]['field'];row['tube_id']=lookup[crop]['tube_id']
    prediction=row['prediction'].upper() if row['field']=='serial_number' else row['prediction']
    row['raw_exact']=text==prediction
    row['formatted_exact']=formatted_match(row['field'],text,prediction)
    row['edits']=distance(text,prediction)
summary={'fields':len(metric.rows),'raw_correct':sum(r['raw_exact'] for r in metric.rows),
         'after_date_formatting_correct':sum(r['formatted_exact'] for r in metric.rows),
         'character_error_rate':sum(r['edits'] for r in metric.rows)/sum(len(r['expected']) for r in metric.rows),
         'predictions':metric.rows,'note':'Development validation on four Small-label tubes; no independent final test.'}
a.output.resolve().write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
