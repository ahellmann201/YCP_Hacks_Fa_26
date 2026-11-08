"""Offline CPU latency and process peak-memory benchmark, isolated per model."""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def peak_mib():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ['PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage']]
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize / 1024**2
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024**2 if sys.platform == 'darwin' else 1024)


def worker(args):
    started = time.perf_counter()
    import cv2
    import numpy as np
    import onnxruntime
    from onnx_recognizer import Recognizer
    cv2.setNumThreads(1)
    imported = time.perf_counter()
    images = []
    for path in args.image:
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('Cannot read image: ' + str(path))
        images.append(image)
    load_start = time.perf_counter()
    recognizer = Recognizer(args.model_dir[0])
    loaded = time.perf_counter()
    peak_after_load = peak_mib()
    cold_start = time.perf_counter()
    first = recognizer(images[0])
    cold_seconds = time.perf_counter() - cold_start
    for _ in range(args.warmup):
        for image in images:
            recognizer(image)
    durations = []
    per_image = []
    for path, image in zip(args.image, images):
        times = []
        for _ in range(args.repeats):
            before = time.perf_counter()
            prediction = recognizer(image)
            times.append(time.perf_counter() - before)
        durations.extend(times)
        per_image.append({'image':str(path), 'median_seconds':statistics.median(times),
                          'text':prediction['text'], 'confidence':prediction['confidence']})
    ordered = sorted(durations)
    return {'model':str(args.model_dir[0]), 'python':platform.python_version(),
        'onnxruntime':onnxruntime.__version__, 'platform':platform.platform(),
        'machine':platform.machine(), 'cpu_threads':1, 'images':len(images),
        'repeats_per_image':args.repeats, 'warmup_passes':args.warmup,
        'import_seconds':imported-started, 'model_load_seconds':loaded-load_start,
        'first_recognition_seconds':cold_seconds, 'first_prediction':first,
        'peak_after_load_mib':peak_after_load, 'peak_process_mib':peak_mib(),
        'warm_median_seconds':statistics.median(durations),
        'warm_p95_seconds':ordered[max(0, int(len(ordered)*.95+.999999)-1)],
        'warm_min_seconds':min(durations), 'warm_max_seconds':max(durations),
        'per_image':per_image,
        'scope':'Cropped-field recognition including preprocessing and decoding. Images loaded before timing; excludes upload, barcode, cropping and the FastAPI process. Process peak includes Python, libraries, model and images. Startup is a fresh process, not a cold filesystem cache.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, action='append', help='Field crop; repeat for multiple crops')
    parser.add_argument('--model-dir', type=Path, action='append', help='Repeat to compare model directories')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--warmup', type=int, default=1)
    parser.add_argument('--output', type=Path, default=ROOT/'benchmark-results.json')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1 or args.warmup < 0:
        parser.error('repeats must be positive and warmup cannot be negative')
    if not args.model_dir:
        args.model_dir = [ROOT/'trained-model/tube_rec', ROOT/'trained-model/english_finetuned_rec']
    args.model_dir = [p.resolve() for p in args.model_dir]
    if not args.image:
        crops = sorted((ROOT/'uploads').glob('*/analysis/*/photo_*_*.jpg'))
        args.image = []
        for field in ['machine', 'serial_number', 'date_sampled']:
            match = next((p for p in crops if p.stem.endswith('_'+field)), None)
            if match:
                args.image.append(match)
    if not args.image:
        parser.error('No saved field crops found. Supply --image PATH/TO/CROP.jpg')
    args.image = [p.resolve() for p in args.image]
    if args.worker:
        print(json.dumps(worker(args)))
        return
    results = []
    for model in args.model_dir:
        print('Measuring ' + model.name + ' ...', flush=True)
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--model-dir', str(model),
                   '--repeats', str(args.repeats), '--warmup', str(args.warmup)]
        for image in args.image:
            command.extend(['--image', str(image)])
        env = dict(os.environ, OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
        started = time.perf_counter()
        completed = subprocess.run(command, capture_output=True, text=True, env=env)
        if completed.returncode:
            raise RuntimeError(completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        result['worker_total_seconds'] = time.perf_counter() - started
        results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f"{model.name}: load {result['model_load_seconds']:.2f}s; first field {result['first_recognition_seconds']:.2f}s; "
              f"warm median {result['warm_median_seconds']:.2f}s; peak {result['peak_process_mib']:.1f} MiB", flush=True)
    print('Detailed report: ' + str(args.output.resolve()))


if __name__ == '__main__':
    main()
