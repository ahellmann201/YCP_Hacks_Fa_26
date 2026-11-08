"""Fine-tuning runner with optional mild augmentation and final-block training."""
import argparse
import os
import sys
from pathlib import Path
WRAPPER_DIR=Path(__file__).resolve().parent

p=argparse.ArgumentParser(add_help=False);p.add_argument('--repo',type=Path,required=True)
a,remaining=p.parse_known_args();repo=a.repo.resolve()
for flag in ['-c','--config']:
    if flag in remaining:
        i=remaining.index(flag)+1;remaining[i]=str(Path(remaining[i]).resolve())
sys.argv=[sys.argv[0],*remaining];sys.path.insert(0,str(repo));os.chdir(repo)
import cv2
import numpy as np
import paddle
import ppocr.data.imaug as transforms
from tools import train
from ppocr.utils.utility import set_seed


class MildTubeAugment:
    def __init__(self,**kwargs):pass

    def __call__(self,data):
        image=data['image']
        if np.random.rand()<0.5:return data
        choice=np.random.randint(4)
        if choice==0:
            h,w=image.shape[:2];angle=np.random.uniform(-2,2)
            matrix=cv2.getRotationMatrix2D((w/2,h/2),angle,1)
            cosine,sine=abs(matrix[0,0]),abs(matrix[0,1]);nw=int(w*cosine+h*sine)+2;nh=int(h*cosine+w*sine)+2
            matrix[0,2]+=nw/2-w/2;matrix[1,2]+=nh/2-h/2
            image=cv2.warpAffine(image,matrix,(nw,nh),borderValue=(255,255,255))
        elif choice==1:image=np.clip(image.astype('float32')*np.random.uniform(.85,1.15),0,255).astype('uint8')
        elif choice==2:image=cv2.GaussianBlur(image,(3,3),float(np.random.uniform(.4,.8)))
        else:
            h,w=image.shape[:2];scale=np.random.uniform(.75,.95)
            image=cv2.resize(cv2.resize(image,(max(1,int(w*scale)),max(1,int(h*scale)))),(w,h))
        data['image']=image
        return data


def freeze_norm(layer,inputs):layer.eval()


if __name__=='__main__':
    transforms.MildTubeAugment=MildTubeAugment
    sys.path.insert(0,str(WRAPPER_DIR))
    from marker_augmentation import MarkerStrokeAugment
    transforms.MarkerStrokeAugment=MarkerStrokeAugment
    from smudge_augmentation import SmudgeAugment
    transforms.SmudgeAugment=SmudgeAugment
    config,device,logger,writer=train.program.preprocess(is_train=True)
    partial=config['Global'].get('train_last_block',False)
    original=train.build_model
    def build_model(architecture):
        model=original(architecture);trained=[]
        for name,param in model.backbone.named_parameters():
            param.stop_gradient=not (partial and name.startswith('blocks6.'))
            if not param.stop_gradient:trained.append(name)
        if partial and not trained:raise ValueError('Expected final backbone block was not found')
        for layer in model.sublayers():
            if isinstance(layer,(paddle.nn.BatchNorm1D,paddle.nn.BatchNorm2D,paddle.nn.BatchNorm3D)):
                layer.register_forward_pre_hook(freeze_norm)
                for parameter in layer.parameters():parameter.stop_gradient=True
        logger.info('Final backbone block trainable: %s; candidate parameters: %d',partial,len(trained))
        return model
    train.build_model=build_model
    set_seed(config['Global'].get('seed',1024))
    train.main(config,device,logger,writer)
