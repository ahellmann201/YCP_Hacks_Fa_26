"""Compare a converted recognizer with its trained checkpoint on identical inputs."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import onnxruntime as ort


def main():
    parser=argparse.ArgumentParser()
    for name in ['repo','config','checkpoint','onnx','output']:
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--cpu',action='store_true',help='Use CPU for both runtimes')
    args=parser.parse_args()
    args.repo=args.repo.resolve()
    sys.path.insert(0,str(args.repo))
    sys.argv=[sys.argv[0],'-c',str(args.config.resolve()),'-o',
              'Global.checkpoints='+str(args.checkpoint.resolve())]
    if args.cpu:sys.argv.append('Global.use_gpu=False')
    from tools import eval as evaluator
    import paddle
    evaluator.config,evaluator.device,evaluator.logger,_=evaluator.program.preprocess()
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(args.onnx.resolve()),sess_options=options,providers=['CPUExecutionProvider'])
    records=[];differences=[]

    def compare(model,loader,decode,metric,*unused):
        model.eval()
        with paddle.no_grad():
            for batch in loader:
                images=batch[0];inputs=images.numpy()
                reference=model(images).numpy()
                converted=session.run(None,{session.get_inputs()[0].name:inputs})[0]
                if reference.shape!=converted.shape:raise ValueError('Output shape differs')
                error=float(np.max(np.abs(reference-converted)));differences.append(error)
                np.testing.assert_allclose(converted,reference,rtol=0.001,atol=0.0001)
                expected=decode(reference,batch[1].numpy())
                actual=decode(converted,batch[1].numpy())
                metric(actual)
                for (left,_),(right,confidence),(label,_) in zip(expected[0],actual[0],actual[1]):
                    records.append({'expected':label,'paddle':left,'onnx':right,
                                    'onnx_confidence':float(confidence),'match':left==right})
        if not records or not all(r['match'] for r in records):raise ValueError('Decoded predictions differ')
        report={'samples':len(records),'all_predictions_match':True,'max_absolute_output_difference':max(differences),
                'numeric_tolerance':{'rtol':0.001,'atol':0.0001},'metrics':metric.get_metric(),
                'input':session.get_inputs()[0].shape,'output':session.get_outputs()[0].shape,'predictions':records}
        args.output.resolve().write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        return report['metrics']

    evaluator.program.eval=compare
    evaluator.main()


if __name__=='__main__':main()
