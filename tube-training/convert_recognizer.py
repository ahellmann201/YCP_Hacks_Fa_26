"""Export a trained checkpoint and convert its inference graph to ONNX."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    for name in ['run','repo','convert-python','output']:
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--train-python',type=Path,default=Path(sys.executable))
    a=p.parse_args()
    run,repo,out=a.run.resolve(),a.repo.resolve(),a.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(a.train_python.resolve()),'tools/export_model.py','-c',str(run/'finetune.yml'),'-o',
        'Global.pretrained_model='+str(run/'checkpoints/best_accuracy'),
        'Global.save_inference_dir='+str(out/'paddle')],cwd=repo,check=True)
    subprocess.run([str(a.convert_python.resolve()),'-m','paddle2onnx.command',
        '--model_dir',str(out/'paddle'),'--model_filename','inference.json',
        '--params_filename','inference.pdiparams','--save_file',str(out/'recognizer.onnx'),
        '--opset_version','14','--enable_onnx_checker','True','--optimize_tool','None'],check=True)
    model=out/'recognizer.onnx'
    if not model.is_file() or not model.stat().st_size:raise RuntimeError('Converter did not create a model')
    shutil.copy2(repo/'ppocr/utils/dict/ppocrv5_dict.txt',out/'characters.txt')
    (out/'checksums.json').write_text(json.dumps({name:hashlib.sha256((out/name).read_bytes()).hexdigest()
        for name in ['recognizer.onnx','characters.txt']},indent=2))
    print('Converted. Run verify_onnx_conversion.py before deployment:',model)


if __name__=='__main__':main()
