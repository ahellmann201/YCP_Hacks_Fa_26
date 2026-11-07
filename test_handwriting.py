import os

# Limit background processing on the Pi.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import resource
import sys
import time
from pathlib import Path

from PIL import Image, ImageOps
from rapidocr import RapidOCR, ModelType, OCRVersion


if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: python test_handwriting.py uploads/SAMPLE_ID/image_1.jpg"
    )

path = Path(sys.argv[1])

if not path.is_file():
    raise SystemExit(f"Photo not found: {path}")

print("Preparing photo...", flush=True)

with Image.open(path) as original:
    if original.width * original.height > 20_000_000:
        raise SystemExit("Please test with a photo under 20 megapixels.")

    original.draft("RGB", (1200, 1200))
    photo = ImageOps.exif_transpose(original).convert("RGB")
    photo.thumbnail((1200, 1200))

print(
    "Loading small OCR models. First use may download model files...",
    flush=True,
)

started = time.perf_counter()

engine = RapidOCR(
    params={
        "Det.ocr_version": OCRVersion.PPOCRV5,
        "Det.model_type": ModelType.MOBILE,
        "Rec.ocr_version": OCRVersion.PPOCRV5,
        "Rec.model_type": ModelType.MOBILE,
        "Det.limit_side_len": 640,
        "Det.limit_type": "max",
        "Rec.rec_batch_num": 1,
        "Cls.cls_batch_num": 1,
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
    }
)

print("Reading label...", flush=True)
reading_started = time.perf_counter()

result = engine(photo)

finished = time.perf_counter()

print("\n--- Recognized text ---")

if result.txts is None or len(result.txts) == 0:
    print("No text detected.")
else:
    for text, score in zip(result.txts, result.scores):
        print(f"{float(score):.2f}  {text}")

print("\n--- Performance ---")
print(f"OCR call: {finished - reading_started:.1f} seconds")
print(f"Total including setup: {finished - started:.1f} seconds")

peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"Peak process memory: {peak_kib / 1024:.1f} MiB")