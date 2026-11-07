"""Conservative experiment using PaddleOCR's training loop and original weights."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT / 'PaddleOCR'
sys.path.insert(0, str(REPO))
for flag in ('-c', '--config'):
    if flag in sys.argv:
        index = sys.argv.index(flag) + 1
        sys.argv[index] = str(Path(sys.argv[index]).resolve())
os.chdir(REPO)

import paddle
from tools import train
from ppocr.utils.utility import set_seed

original_build = train.build_model


def freeze_norm(layer, inputs):
    layer.eval()


def build_model(config):
    model = original_build(config)
    for parameter in model.backbone.parameters():
        parameter.stop_gradient = True
    count = 0
    for layer in model.sublayers():
        if isinstance(layer, (paddle.nn.BatchNorm1D, paddle.nn.BatchNorm2D, paddle.nn.BatchNorm3D)):
            layer.register_forward_pre_hook(freeze_norm)
            for parameter in layer.parameters():
                parameter.stop_gradient = True
            count += 1
    print(f'Frozen backbone and {count} normalization layers; training recognition head.')
    return model


if __name__ == '__main__':
    train.build_model = build_model
    config, device, logger, writer = train.program.preprocess(is_train=True)
    set_seed(config['Global'].get('seed', 1024))
    train.main(config, device, logger, writer)
