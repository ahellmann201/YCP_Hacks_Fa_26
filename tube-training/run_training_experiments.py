"""Controlled small-data experiments; keep existing models and data intact."""
import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
import yaml

HERE=Path(__file__).resolve().parent


def include_final_validation_batch(repo):
    path=repo/'tools/program.py'
    text=path.read_text(encoding='utf-8')
    old='''max_iter = (
            len(valid_dataloader) - 1
            if platform.system() == "Windows"
            else len(valid_dataloader)
        )'''
    if old in text:
        path.write_text(text.replace(old,'max_iter = len(valid_dataloader)  # Include final Windows batch'),encoding='utf-8')
    elif 'max_iter = len(valid_dataloader)' not in text:
        raise ValueError('Unsupported evaluator: verify that the final validation batch is included.')


def main():
    p=argparse.ArgumentParser()
    for name in ['dataset','repo','multilingual-weights','english-weights','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--resume',action='store_true',help='Skip completed stages; restart an incomplete stage from its specified initialization')
    a=p.parse_args();a.dataset=a.dataset.resolve();a.repo=a.repo.resolve();a.output=a.output.resolve()
    a.multilingual_weights=a.multilingual_weights.resolve();a.english_weights=a.english_weights.resolve()
    include_final_validation_batch(a.repo)
    if a.output.exists() and not a.resume:raise SystemExit('Choose a fresh experiment output folder, or explicitly --resume.')
    a.output.mkdir(parents=True,exist_ok=a.resume)
    paths={name:a.dataset/(name+'.txt') for name in ['train','val']}
    count=len(paths['train'].read_text().splitlines());steps=math.ceil(count/4)
    manifest=[json.loads(s) for s in (a.dataset/'manifest.jsonl').read_text().splitlines()]
    fingerprints={split:hashlib.sha256(path.read_bytes()).hexdigest() for split,path in paths.items()}
    fingerprints['crops']={row['crop']:hashlib.sha256((a.dataset/row['crop']).read_bytes()).hexdigest() for row in manifest}
    fingerprint_file=a.output/'dataset_fingerprints.json'
    if fingerprint_file.exists() and json.loads(fingerprint_file.read_text())!=fingerprints:
        raise ValueError('Dataset changed since this experiment started; use a fresh output folder')
    fingerprint_file.write_text(json.dumps(fingerprints,indent=2))
    groups={};hashes={}
    for r in manifest:
        for seen,key in [(groups,r['group_id']),(hashes,r['source_sha256'])]:
            if key in seen and seen[key]!=r['split']:raise ValueError('Training/validation overlap')
            seen[key]=r['split']
    labels=[s.split('\t',1)[1] for s in paths['train'].read_text().splitlines()]
    revision=subprocess.check_output(['git','-C',str(a.repo),'rev-parse','HEAD'],text=True).strip()
    results=json.loads((a.output/'summary.json').read_text()) if a.resume and (a.output/'summary.json').exists() else []
    def config(name,english,weights,epochs,augment,partial):
        template='multi_language/en_PP-OCRv5_mobile_rec.yaml' if english else 'PP-OCRv5_mobile_rec.yml'
        cfg=yaml.safe_load((a.repo/'configs/rec/PP-OCRv5'/template).read_text())
        dictionary=a.repo/cfg['Global']['character_dict_path']
        missing=set(''.join(labels))-set(dictionary.read_text(encoding='utf-8').splitlines())-{' '}
        if missing:raise ValueError('Characters missing from dictionary: '+repr(missing))
        run=a.output/name;run.mkdir(exist_ok=a.resume)
        cfg['Global'].update(use_gpu=True,distributed=False,epoch_num=epochs,seed=1024,
            pretrained_model=str(weights.resolve().with_suffix('') if weights.suffix=='.pdparams' else weights.resolve()),
            checkpoints=None,save_model_dir=str(run/'checkpoints'),save_epoch_step=1,
            eval_batch_step=[0,steps],print_batch_step=5,character_dict_path=str(dictionary),
            use_visualdl=False,train_last_block=partial)
        cfg['Optimizer']['lr'].update(learning_rate=1e-6 if partial else 3e-6,warmup_epoch=0)
        cfg['Metric']['ignore_space']=False
        transforms=copy.deepcopy(cfg['Eval']['dataset']['transforms'])
        cfg['Train']['dataset']['name']='SimpleDataSet'
        cfg['Train']['dataset'].pop('ds_width',None);cfg['Train']['dataset'].pop('ext_op_transform_idx',None)
        if augment:transforms.insert(1,{'MildTubeAugment':None})
        cfg['Train']['dataset']['transforms']=transforms
        cfg['Train'].pop('sampler',None)
        for split,section in [('train','Train'),('val','Eval')]:
            cfg[section]['dataset'].update(data_dir=str(a.dataset),label_file_list=[str(paths[split])])
            cfg[section]['loader'].update(num_workers=0,batch_size_per_card=4,drop_last=False)
            cfg[section]['loader']['shuffle']=split=='train'
        path=run/'finetune.yml';path.write_text(yaml.safe_dump(cfg,sort_keys=False))
        (run/'experiment.json').write_text(json.dumps({'english':english,'augment':augment,'train_last_block':partial,
            'initial_weights':str(weights),'epochs':epochs,'training_crops':count,'paddleocr_revision':revision},indent=2))
        return path,run
    def execute(arguments,log):
        with log.open('w',encoding='utf-8') as stream:
            result=subprocess.run([sys.executable,*map(str,arguments)],cwd=a.repo,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError('Step failed. Read '+str(log))
        text=log.read_text(encoding='utf-8',errors='replace')
        if 'not matched with loaded params' in text:raise RuntimeError('Checkpoint architecture mismatch: '+str(log))
    def evaluate(path,run,weights,label):
        execute([HERE/'evaluate_checkpoint.py','--repo',a.repo,'--config',path,'--weights',weights,'--output',run/(label+'.json')],run/(label+'.log'))
        report=json.loads((run/(label+'.json')).read_text())
        results.append({'experiment':run.name,'stage':label,**{key:report[key] for key in ['fields','raw_correct','after_date_formatting_correct','character_error_rate']}})
        (a.output/'summary.json').write_text(json.dumps(results,indent=2))
        print(results[-1],flush=True)
    phases=[('cleaned_head',False,False,False,10,None),
            ('augmented_head',False,True,False,10,None),
            ('partial_backbone',False,True,True,5,'augmented_head'),
            ('english_head',True,True,False,5,None),
            ('english_partial',True,True,True,5,'english_head')]
    for name,english,augment,partial,epochs,parent in phases:
        if a.resume and (a.output/name/'after_training.json').exists():
            print('Keeping completed stage',name,flush=True)
            continue
        weights=a.output/parent/'checkpoints/best_accuracy' if parent else (a.english_weights if english else a.multilingual_weights)
        path,run=config(name,english,weights,epochs,augment,partial)
        print('Starting',name,flush=True)
        if name in ['cleaned_head','english_head']:evaluate(path,run,weights,'before_training')
        execute([HERE/'train_experiment.py','--repo',a.repo,'-c',path],run/'training.log')
        evaluate(path,run,run/'checkpoints/best_accuracy','after_training')
    print('Finished all experiments. No model deployed:',a.output,flush=True)


if __name__=='__main__':main()
