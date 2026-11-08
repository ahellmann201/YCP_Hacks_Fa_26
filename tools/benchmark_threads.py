"""Compare OCR thread settings on saved tube photos without changing records (Linux)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(BASE))


def select_tubes(base, count):
    """Round-robin label/photo-count groups; omit exact reuploads and known duplicate IDs."""
    buckets = {}
    seen_ids, seen_photos = set(), set()
    for path in sorted((base/'uploads').glob('*/sample.json'), key=lambda p:p.stat().st_mtime, reverse=True):
        try:
            sample = json.loads(path.read_text())
            photos = [(path.parent/e['filename']).resolve() for e in sample['images']]
            if not 1 <= len(photos) <= 8 or any(p.parent != path.parent.resolve() or not p.is_file() for p in photos):
                continue
            digests = []
            for photo in photos:
                digest = hashlib.sha256()
                with photo.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(64*1024), b''):
                        digest.update(chunk)
                digests.append(digest.hexdigest())
            signature = tuple(sorted(digests))
            result_path = path.parent/'ocr.json'
            result = json.loads(result_path.read_text()) if result_path.exists() else {}
            sample_id = str(result.get('suggestions', {}).get('sample_id') or '').strip()
            if signature in seen_photos or (sample_id and sample_id in seen_ids):
                continue
            seen_photos.add(signature)
            if sample_id:
                seen_ids.add(sample_id)
            kind = result.get('label_type', 'unknown')
            buckets.setdefault((str(kind), len(photos)), []).append(path.parent)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    chosen = []
    while len(chosen) < count:
        added = False
        for key in sorted(buckets):
            if buckets[key] and len(chosen) < count:
                chosen.append(buckets[key].pop(0)); added = True
        if not added:
            break
    return chosen


def summarize(runs, counts):
    summary = {}
    for count in counts:
        group = [r for r in runs if r['threads'] == count]
        per_tube = {}
        for run in group:
            per_tube.setdefault(run['tube'], []).append(run['seconds'])
        averages = [statistics.mean(times) for times in per_tube.values()]
        summary[str(count)] = {
            'tubes':len(per_tube), 'runs':len(group),
            'mean_seconds':statistics.mean(r['seconds'] for r in group),
            'median_seconds':statistics.median(r['seconds'] for r in group),
            'slowest_tube_mean_seconds':max(averages),
            'tubes_with_mean_under_30s':sum(seconds <= 30 for seconds in averages),
            'peak_ocr_worker_mib':max(r['ocr_worker_peak_mib'] for r in group),
        }
    references = {}
    comparisons = 0
    same = True
    for run in runs:
        reading = (run['label_type'], run['suggestions'], run['photo_errors'])
        if run['tube'] in references:
            comparisons += 1
            same = same and references[run['tube']] == reading
        else:
            references[run['tube']] = reading
    return summary, same if comparisons else None


def worker(args):
    import resource
    from scanner.vision.label_preview import build_preview
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
        request.write_text(json.dumps({'images':images, 'debug_dir':str(debug),
                                       'date_received':sample.get('date_received','')}))
        before = time.perf_counter()
        env = dict(os.environ, SCANNER_OCR_THREADS=str(args.threads))
        process = subprocess.run([sys.executable, str(BASE/'scanner'/'reading'/'scanner_auto.py'), str(request), str(output)],
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
    parser.add_argument('--samples', type=int, default=1, help='Automatically select up to this many distinct tubes, varied by label/photo count')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--thread-counts', type=int, nargs='+', choices=[1,2,3,4], default=[2,3,4],
                        help='Thread counts to compare (default: 2 3 4)')
    parser.add_argument('--output', type=Path, default=BASE/'thread-benchmark-results.json')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--threads', type=int, choices=[1,2,3,4], default=1, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('Run this full-tube benchmark on the Linux Pi.')
    if args.repeats < 1 or args.samples < 1:
        parser.error('repeats and samples must be positive')
    if args.tube is not None and args.samples != 1:
        parser.error('Choose --tube or --samples, not both')
    if args.tube is None:
        choices = list((BASE/'uploads').glob('*/sample.json'))
        if not choices:
            parser.error('Upload a tube first, or pass --tube uploads/RECORD_ID')
        args.tube = max(choices, key=lambda p:p.stat().st_mtime).parent
    if args.worker:
        print(json.dumps(worker(args)))
        return
    tubes = select_tubes(BASE, args.samples) if args.samples > 1 else [args.tube]
    if not tubes:
        parser.error('No usable tube folders found')
    print(f'Selected {len(tubes)} distinct tubes (requested {args.samples}).', flush=True)
    runs = []
    counts = list(dict.fromkeys(args.thread_counts))
    for repeat in range(args.repeats):
        # Alternate order to reduce systematic filesystem-cache/order bias.
        for tube_number, tube in enumerate(tubes if repeat%2 == 0 else list(reversed(tubes)), 1):
            for threads in (counts if repeat%2 == 0 else list(reversed(counts))):
                print(f'Tube {tube_number}/{len(tubes)} ({tube.name}), {threads} thread(s), repeat {repeat+1}/{args.repeats} ...', flush=True)
                completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                    '--tube', str(tube.resolve()), '--threads', str(threads)], capture_output=True, text=True)
                if completed.returncode:
                    raise RuntimeError(completed.stderr or completed.stdout)
                result = json.loads(completed.stdout)
                runs.append(result)
                print(f"{result['seconds']:.1f}s/tube; OCR worker peak {result['ocr_worker_peak_mib']:.1f} MiB", flush=True)
                args.output.write_text(json.dumps({'runs':runs}, indent=2))
    summary, same = summarize(runs, counts)
    per_tube = [{ 'tube':tube.name, 'summary':summarize([r for r in runs if r['tube']==tube.name], counts)[0] }
                for tube in tubes]
    report = {'summary':summary, 'per_tube':per_tube, 'same_field_outputs':same, 'runs':runs,
              'scope':'Saved photos, fresh OCR worker, model load, OCR and preview; no upload, queue, database saves or web-server memory. Worker and preview-parent memory peaks are separate, not total app memory. No scan records are modified. Cache not cleared; run order alternates.'}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'summary':summary, 'same_field_outputs':same}, indent=2))
    print('Report:', args.output)


if __name__ == '__main__':
    main()
