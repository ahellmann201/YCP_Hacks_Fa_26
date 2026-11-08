"""Validate the prepared data and launch a separate, reproducible training run."""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import yaml
from PIL import Image

ROOT=Path(__file__).resolve().parent


def prepare(dataset=None):
    if dataset is None:
        choices=sorted((ROOT/'exports').glob('*/summary.json'))
        if not choices:raise ValueError('Export a labeled dataset first, or pass --dataset PATH.')
        dataset=choices[-1].parent
    dataset=Path(dataset).resolve()
    weights=ROOT/'PP-OCRv5_mobile_rec_pretrained.pdparams'
    if not weights.is_file():raise ValueError('Missing original pretrained weights')
    output=ROOT/'training-expanded'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True)
    subprocess.run([sys.executable,str(ROOT/'configure_training.py'),
        '--repo',str(ROOT/'PaddleOCR'),'--dataset',str(dataset),'--weights',str(weights),
        '--gpu','--epochs','10','--batch-size','4','--output',str(output)],check=True)
    config=yaml.safe_load((output/'finetune.yml').read_text())
    config['Optimizer']['lr']['learning_rate']=0.000003
    config['Metric']['ignore_space']=False
    config['Train']['dataset']['name']='SimpleDataSet'
    config['Train']['dataset'].pop('ds_width',None)
    config['Train']['dataset'].pop('ext_op_transform_idx',None)
    config['Train']['dataset']['transforms']=copy.deepcopy(config['Eval']['dataset']['transforms'])
    config['Train'].pop('sampler',None)
    records=[json.loads(s) for s in (dataset/'manifest.jsonl').read_text().splitlines()]
    split_by_group={};split_by_hash={}
    for row in records:
        for mapping,key in [(split_by_group,row['group_id']),(split_by_hash,row['source_sha256'])]:
            if key in mapping and mapping[key]!=row['split']:raise ValueError('Train/validation overlap')
            mapping[key]=row['split']
    hashes={};counts={}
    for split in ['train','val']:
        file=dataset/(split+'.txt');raw=file.read_bytes();hashes[split]=hashlib.sha256(raw).hexdigest()
        lines=raw.decode().splitlines();counts[split]=len(lines)
        if not lines:raise ValueError('Empty '+split+' dataset')
        for line in lines:
            path,text=line.split('\t',1)
            if not text.strip():raise ValueError('Empty training label')
            with Image.open(dataset/path) as im:im.verify()
        section=config['Train' if split=='train' else 'Eval']
        section['dataset'].update(data_dir=str(dataset),label_file_list=[str(file)])
    program=(ROOT/'PaddleOCR/tools/program.py').read_text(encoding='utf-8')
    skipped_batch='''max_iter = (
            len(valid_dataloader) - 1
            if platform.system() == "Windows"
            else len(valid_dataloader)
        )'''
    if skipped_batch in program:
        (ROOT/'PaddleOCR/tools/program.py').write_text(program.replace(skipped_batch,
            'max_iter = len(valid_dataloader)  # Include final Windows batch'),encoding='utf-8')
    elif 'max_iter = len(valid_dataloader)' not in program:
        raise ValueError('Unsupported evaluator version; verify that Windows includes its final validation batch.')
    config['Global'].update(pretrained_model=str(weights.with_suffix('')),checkpoints=None,
        save_model_dir=str(output/'checkpoints'),epoch_num=10,
        eval_batch_step=[0,max(1,(counts['train']+3)//4)])
    target=output/'finetune.yml';target.write_text(yaml.safe_dump(config,sort_keys=False))
    metadata=json.loads((output/'run_metadata.json').read_text())
    metadata.update({
        'dataset':str(dataset),'counts':counts,'label_sha256':hashes,
        'label_provenance':'Earlier human-reviewed labels plus assistant-only automatically accepted labels.',
        'weights':str(weights),'training_wrapper':'train_small_dataset.py',
        'warning':'Development validation only, four tubes. This experiment trains field-text recognition, not automatic cropping or circled-selection detection.'
    })
    (output/'run_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(f"Ready: {counts['train']} training crops, {counts['val']} validation crops.",flush=True)
    print('Run folder:',output,flush=True)
    return target,output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--dataset',type=Path,help='Export folder; defaults to newest local export')
    args=parser.parse_args()
    config,output=prepare(args.dataset)
    if args.prepare_only:return
    def run(arguments,name,cwd=ROOT):
        with (output/name).open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,*arguments],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            for line in process.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
            if process.wait():raise RuntimeError('Step failed; see '+str(output/name))
    print('Checking the untouched pretrained model first.',flush=True)
    run(['tools/eval.py','-c',str(config)],'baseline.log',ROOT/'PaddleOCR')
    print('Starting ten training epochs.',flush=True)
    run(['train_small_dataset.py','-c',str(config)],'console.log')
    print('Evaluating the saved best checkpoint.',flush=True)
    run(['tools/eval.py','-c',str(config),'-o','Global.checkpoints='+str(output/'checkpoints/best_accuracy')],
        'final-eval.log',ROOT/'PaddleOCR')
    print('\nCompleted. Compare baseline.log with final-eval.log in:',output,flush=True)
    print('The Pi application has not been changed.',flush=True)


if __name__=='__main__':main()
