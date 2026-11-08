"""Create a small-data PP-OCRv5 recognition fine-tuning configuration."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path, help='PaddleOCR source checkout')
    parser.add_argument('--dataset', required=True, type=Path, help='Verified exported dataset folder')
    parser.add_argument('--weights', required=True, type=Path, help='Matching training .pdparams checkpoint, NOT ONNX')
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=2)
    parser.add_argument('--output', type=Path, default=Path('training-run'))
    args = parser.parse_args()
    import yaml
    repo, dataset, output = args.repo.resolve(), args.dataset.resolve(), args.output.resolve()
    source = repo / 'configs/rec/PP-OCRv5/PP-OCRv5_mobile_rec.yml'
    if not source.is_file() or not (repo / 'tools/train.py').is_file():
        raise SystemExit('Expected a PaddleOCR source checkout containing PP-OCRv5_mobile_rec.yml.')
    if args.weights.suffix != '.pdparams' or not args.weights.is_file():
        raise SystemExit('Supply the matching PP-OCRv5_mobile_rec training .pdparams checkpoint.')
    for split in ('train', 'val'):
        path = dataset / (split + '.txt')
        if not path.is_file() or not path.read_text(encoding='utf-8').strip():
            raise SystemExit(f'Missing verified {split}.txt. Export from the labeling tool first.')
    config = yaml.safe_load(source.read_text(encoding='utf-8'))
    global_config = config['Global']
    dictionary = repo / global_config['character_dict_path']
    characters = set(dictionary.read_text(encoding='utf-8').splitlines()) | {' '}
    labels = []
    for split in ('train', 'val'):
        for line in (dataset / (split + '.txt')).read_text(encoding='utf-8').splitlines():
            relative, text = line.split('\t', 1)
            if not (dataset / relative).is_file():
                raise SystemExit('Missing crop: ' + relative)
            labels.append(text)
    missing = set(''.join(labels)) - characters
    if missing:
        raise SystemExit('Characters missing from the model dictionary: ' + repr(sorted(missing)))
    max_length = max(25, max(map(len, labels)) + 2)
    output.mkdir(parents=True, exist_ok=True)
    global_config.update(
        use_gpu=args.gpu, distributed=False, epoch_num=args.epochs,
        pretrained_model=str(args.weights.resolve().with_suffix('')),
        checkpoints=None, save_model_dir=str(output / 'checkpoints'),
        save_epoch_step=1, eval_batch_step=[0, 10], print_batch_step=5,
        character_dict_path=str(dictionary.resolve()), max_text_length=max_length,
        cal_metric_during_train=True, use_visualdl=False,
    )
    config['Optimizer']['lr']['learning_rate'] = 0.00001
    config['Optimizer']['lr']['warmup_epoch'] = 0
    for head in config['Architecture']['Head']['head_list']:
        if 'NRTRHead' in head:
            head['NRTRHead']['max_text_length'] = max_length
    # Avoid composing unrelated handwriting lines in the first tiny experiment.
    config['Train']['dataset']['transforms'] = [
        item for item in config['Train']['dataset']['transforms'] if 'RecConAug' not in item
    ]
    for split, section in [('train', 'Train'), ('val', 'Eval')]:
        config[section]['dataset']['data_dir'] = str(dataset)
        config[section]['dataset']['label_file_list'] = [str(dataset / (split + '.txt'))]
        config[section]['loader'].update(num_workers=0, batch_size_per_card=args.batch_size, drop_last=False)
    config['Train']['sampler']['first_bs'] = args.batch_size
    config_path = output / 'finetune.yml'
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    revision = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    (output / 'run_metadata.json').write_text(json.dumps({
        'repo': str(repo), 'revision': revision.stdout.strip(),
        'dataset': str(dataset), 'weights': str(args.weights.resolve()),
        'warning': 'Small development experiment; not proof of generalization.',
    }, indent=2), encoding='utf-8')
    print('Configuration:', config_path)
    print('Run from the PaddleOCR source folder:')
    print(f'python tools/train.py -c "{config_path}"')
    print(f'python tools/eval.py -c "{config_path}" -o Global.checkpoints="{output / "checkpoints/best_accuracy"}"')
    print(f'python tools/export_model.py -c "{config_path}" -o Global.pretrained_model="{output / "checkpoints/best_accuracy"}" Global.save_inference_dir="{output / "inference"}"')
    print('Only deploy after baseline comparison and Pi compatibility/performance testing.')


if __name__ == '__main__':
    main()
