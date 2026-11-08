"""Continue a saved recognition run with controlled marker-stroke augmentation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import yaml
from run_training_experiments import include_final_validation_batch

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['base-run','dataset','repo','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--epochs',type=int,default=10)
    p.add_argument('--partial',action='store_true',help='Train final backbone block too, with normalization frozen')
    a=p.parse_args()
    if a.epochs<1:
        p.error('epochs must be positive')
    base,dataset,repo,out=[path.resolve() for path in [a.base_run,a.dataset,a.repo,a.output]]
    if out.exists():
        p.error('Choose a fresh output directory')
    include_final_validation_batch(repo)
    rows=[json.loads(s) for s in (dataset/'manifest.jsonl').read_text().splitlines()]
    for key in ['group_id','source_sha256']:
        splits={}
        for row in rows:
            if row[key] in splits and splits[row[key]]!=row['split']:
                raise ValueError('Training/validation overlap')
            splits[row[key]]=row['split']
    cfg=yaml.safe_load((base/'finetune.yml').read_text())
    weights=base/'checkpoints/best_accuracy'
    if not weights.with_suffix('.pdparams').is_file():
        raise ValueError('Base checkpoint not found')
    out.mkdir(parents=True)
    cfg['Global'].update(epoch_num=a.epochs,pretrained_model=str(weights),checkpoints=None,
                         save_model_dir=str(out/'checkpoints'),train_last_block=a.partial,seed=1024)
    cfg['Optimizer']['lr'].update(learning_rate=1e-6,warmup_epoch=0)
    cfg['Metric']['ignore_space']=False
    transforms=copy.deepcopy(cfg['Eval']['dataset']['transforms'])
    transforms[1:1]=[{'MarkerStrokeAugment':None},{'MildTubeAugment':None}]
    cfg['Train']['dataset']['transforms']=transforms
    for split,section in [('train','Train'),('val','Eval')]:
        cfg[section]['dataset'].update(data_dir=str(dataset),label_file_list=[str(dataset/(split+'.txt'))])
        cfg[section]['loader'].update(shuffle=split=='train',drop_last=False,num_workers=0,batch_size_per_card=4)
    path=out/'finetune.yml';path.write_text(yaml.safe_dump(cfg,sort_keys=False))
    (out/'dataset_fingerprints.json').write_text(json.dumps({r['crop']:hashlib.sha256((dataset/r['crop']).read_bytes()).hexdigest() for r in rows},indent=2))
    metadata={'base_checkpoint':str(weights),'epochs':a.epochs,'partial_backbone':a.partial,
              'training_crops':sum(r['split']=='train' for r in rows),'validation_crops':sum(r['split']=='val' for r in rows),
              'note':'Existing labels retained; stroke-width augmentation is synthetic variation, not additional independent handwriting.'}
    (out/'experiment.json').write_text(json.dumps(metadata,indent=2))
    def run(arguments,log):
        with (out/log).open('w',encoding='utf-8') as stream:
            result=subprocess.run([sys.executable,*map(str,arguments)],cwd=repo,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Step failed; read '+str(out/log))
        if 'not matched with loaded params' in (out/log).read_text(encoding='utf-8',errors='replace'):
            raise RuntimeError('Checkpoint parameters did not match; read '+str(out/log))
    for label,checkpoint in [('before_training',weights),('after_training',out/'checkpoints/best_accuracy')]:
        if label=='after_training':
            print('Training marker-stroke run...',flush=True)
            run([HERE/'train_experiment.py','--repo',repo,'-c',path],'training.log')
        run([HERE/'evaluate_checkpoint.py','--repo',repo,'--config',path,'--weights',checkpoint,
             '--output',out/(label+'.json')],label+'.log')
        result=json.loads((out/(label+'.json')).read_text())
        print(label,{k:result[k] for k in ['fields','raw_correct','after_date_formatting_correct','character_error_rate']},flush=True)
    print('Finished. No app model was changed:',out,flush=True)


if __name__=='__main__':
    main()
