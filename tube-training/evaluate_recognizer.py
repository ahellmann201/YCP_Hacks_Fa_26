"""Measure exact-match and character error rate on approved field crops."""
import argparse
import csv
import json
import os
import time
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j-1] + (left != right)))
        previous = current
    return previous[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--split', choices=['train', 'val'], default='val')
    parser.add_argument('--model', type=Path, help='Optional fine-tuned ONNX recognition model')
    parser.add_argument('--keys', type=Path, help='Matching character dictionary if required')
    parser.add_argument('--language', choices=['ch', 'en'], default='ch')
    parser.add_argument('--report', type=Path, default=Path('baseline-report'))
    args = parser.parse_args()
    from PIL import Image
    from rapidocr import RapidOCR, ModelType, OCRVersion, LangRec
    settings = {
        'Global.use_det': False, 'Global.use_cls': False,
        'Rec.ocr_version': OCRVersion.PPOCRV5,
        'Rec.model_type': ModelType.MOBILE,
        'Rec.lang_type': LangRec.EN if args.language == 'en' else LangRec.CH,
        'Rec.rec_batch_num': 1,
        'EngineConfig.onnxruntime.intra_op_num_threads': 1,
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
    }
    if args.model:
        settings['Rec.model_path'] = str(args.model.resolve())
    if args.keys:
        settings['Rec.rec_keys_path'] = str(args.keys.resolve())
    annotations = [json.loads(line) for line in
                   (args.dataset / 'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    annotations = [row for row in annotations
                   if row['task'] == 'recognition' and row['split'] == args.split]
    if not annotations:
        raise SystemExit('No recognition crops in that split.')
    engine = RapidOCR(params=settings)
    results = []
    for row in annotations:
        started = time.perf_counter()
        with Image.open(args.dataset / row['crop']) as image:
            result = engine(image.convert('RGB'), use_det=False, use_cls=False, use_rec=True)
        prediction = ' '.join(result.txts) if result.txts is not None else ''
        expected = row['text']
        canonical = prediction.upper() if row['field'] == 'serial_number' else prediction
        results.append({
            'tube_id': row['tube_id'], 'group_id': row['group_id'], 'field': row['field'],
            'crop': row['crop'], 'expected': expected, 'raw_prediction': prediction,
            'prediction': canonical, 'exact': canonical == expected,
            'edits': distance(canonical, expected), 'characters': len(expected),
            'seconds': round(time.perf_counter() - started, 3),
        })
        print(row['tube_id'], row['field'], repr(expected), '->', repr(canonical), flush=True)
    args.report.mkdir(parents=True, exist_ok=True)
    with (args.report / 'predictions.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    def metrics(rows):
        return {'crops': len(rows), 'exact_match': sum(r['exact'] for r in rows) / len(rows),
                'character_error_rate': sum(r['edits'] for r in rows) / sum(r['characters'] for r in rows)}
    summary = {'overall': metrics(results), 'by_field': {
        name: metrics([r for r in results if r['field'] == name])
        for name in sorted({r['field'] for r in results})
    }, 'note': 'Validation is for development. First inference may include model download/loading.'}
    (args.report / 'metrics.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
