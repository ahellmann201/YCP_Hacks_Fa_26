"""CPU-only cropped-field recognition. No Paddle dependency or model download."""
import argparse
import json
import math
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort


def prepare(image):
    if image is None or image.ndim!=3 or image.shape[2]!=3:raise ValueError('Expected a BGR color image')
    height,width=image.shape[:2]
    if min(height,width)<1:raise ValueError('Empty image')
    resized_width=min(320,math.ceil(48*width/height))
    resized=cv2.resize(image,(resized_width,48),interpolation=cv2.INTER_LINEAR).astype('float32')
    resized=resized.transpose(2,0,1)/255.0
    resized-=0.5;resized/=0.5
    padded=np.zeros((3,48,320),dtype='float32');padded[:,:,:resized_width]=resized
    return padded[None,...]


class Recognizer:
    def __init__(self,model_dir,model_path=None):
        directory=Path(model_dir)
        self.characters=['blank']+(directory/'characters.txt').read_text(encoding='utf-8').splitlines()+[' ']
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(model_path or directory/'recognizer.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        if self.session.get_outputs()[0].shape[-1]!=len(self.characters):raise ValueError('Model/dictionary mismatch')

    def __call__(self,image):
        result=self.session.run(None,{self.session.get_inputs()[0].name:prepare(image)})[0][0]
        indices=result.argmax(1);scores=result.max(1)
        selected=[i for i,index in enumerate(indices) if index!=0 and (i==0 or index!=indices[i-1])]
        text=''.join(self.characters[indices[i]] for i in selected)
        return {'text':text,'confidence':float(scores[selected].mean()) if selected else 0.0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('image',type=Path)
    p.add_argument('--model-dir',type=Path,default=Path(__file__).resolve().parent.parent/'trained-model/tube_rec')
    a=p.parse_args();image=cv2.imdecode(np.fromfile(a.image,dtype=np.uint8),cv2.IMREAD_COLOR)
    print(json.dumps(Recognizer(a.model_dir)(image),ensure_ascii=False))
