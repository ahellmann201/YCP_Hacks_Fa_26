"""Compare one/two OCR threads on saved tube photos without changing records (Linux)."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parent


def worker(args):
    import resource
    from label_preview import build_preview
    folder = args.tube.resolve()
    sample = json.loads((folder/'sample.json').read_text())
    with tempfile.TemporaryDirectory(prefix='tube-thread-test-') as temporary:
        root = Path(temporary)
        request, output = root/'request.json', root/'result.json'
        images = []
        for entry in sample['images']:
            path = (folder/entry['filename']).resolve()
            if path.parent != folder or not path.is_file():
                raise ValueError('Invalid or missing tube photo')
            images.append(str(path))
        debug = root/'analysis'/'benchmark'
        request.write_text(json.dumps({'images':images, 'debug_dir':str(debug)}))
        before = time.perf_counter()
        env = dict(os.environ, SCANNER_OCR_THREADS=str(args.threads))
        process = subprocess.run([sys.executable, str(BASE/'scanner_auto.py'), str(request), str(output)],
                                 cwd=BASE, env=env, capture_output=True, text=True, timeout=180*len(images)+60)
        if process.returncode:
            raise RuntimeError(process.stderr[-2000:])
        result = json.loads(output.read_text())
        if result.get('error'):
            raise RuntimeError(result['error'])
        if not any(not image.get('error') for image in result.get('images', [])):
            raise RuntimeError('No photos processed successfully: '+json.dumps(result.get('images')))
        build_preview(root, 'benchmark', result, result.get('label_type'))
        seconds = time.perf_counter()-before
        return {'tube':folder.name, 'threads':args.threads, 'images':len(images), 'seconds':seconds,
                'ocr_worker_peak_mib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,
                'preview_parent_peak_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                'label_type':result.get('label_type'), 'suggestions':result.get('suggestions'),
                'photo_errors':[image.get('error') for image in result.get('images', [])]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tube', type=Path, help='Saved uploads/<record-id> folder; default latest tube')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--output', type=Path, default=BASE/'thread-benchmark-results.json')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--threads', type=int, choices=[1,2], default=1, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('Run this full-tube benchmark on the Linux Pi.')
    if args.repeats < 1:
        parser.error('repeats must be positive')
    if args.tube is None:
        choices = list((BASE/'uploads').glob('*/sample.json'))
        if not choices:
            parser.error('Upload a tube first, or pass --tube uploads/RECORD_ID')
        args.tube = max(choices, key=lambda p:p.stat().st_mtime).parent
    if args.worker:
        print(json.dumps(worker(args)))
        return
    runs = []
    for repeat in range(args.repeats):
        # Alternate order to reduce systematic filesystem-cache/order bias.
        for threads in ([1,2] if repeat%2 == 0 else [2,1]):
            print(f'Testing {threads} thread(s), repeat {repeat+1}/{args.repeats} ...', flush=True)
            completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                '--tube', str(args.tube.resolve()), '--threads', str(threads)], capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(completed.stderr or completed.stdout)
            result = json.loads(completed.stdout)
            runs.append(result)
            print(f"{result['seconds']:.1f}s/tube; OCR worker peak {result['ocr_worker_peak_mib']:.1f} MiB", flush=True)
            args.output.write_text(json.dumps({'runs':runs}, indent=2))
    summary = {str(n):{'mean_seconds':statistics.mean(r['seconds'] for r in runs if r['threads']==n),
                       'peak_ocr_worker_mib':max(r['ocr_worker_peak_mib'] for r in runs if r['threads']==n)} for n in [1,2]}
    reference = (runs[0]['label_type'], runs[0]['suggestions'], runs[0]['photo_errors'])
    same = all((r['label_type'], r['suggestions'], r['photo_errors']) == reference for r in runs)
    report = {'summary':summary, 'same_field_outputs':same, 'runs':runs,
              'scope':'Saved photos, fresh OCR worker, model load, OCR and preview; no upload, queue, database saves or web-server memory. Worker and preview-parent memory peaks are separate, not total app memory. No scan records are modified. Cache not cleared; run order alternates.'}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'summary':summary, 'same_field_outputs':same}, indent=2))
    print('Report:', args.output)


if __name__ == '__main__':
    main()
