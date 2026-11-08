# One or two OCR CPU threads

`SCANNER_OCR_THREADS` accepts `1` or `2`, defaulting to `1`. It controls ONNXRuntime intra-operation threads for both RapidOCR and the fine-tuned English field recognizer. Inter-operation threads, OpenCV and BLAS remain at one to avoid multiplying thread pools. The queue still processes one tube at a time; photos remain sequential. Models are still loaded per tube worker. This setting does not introduce simultaneous tube processes or persistent model caching.

Start with two threads:

```bash
SCANNER_OCR_THREADS=2 .venv-ocr/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Omit the environment setting or use `1` to revert. Restart the server for changes to take effect. Successful OCR JSON results include `ocr_threads` for verifying the active setting. No new dependencies are required.

## Pi comparison

Stop the server and close other heavy applications before running:

```bash
.venv-ocr/bin/python benchmark_threads.py
```

This defaults to the latest saved tube, running both settings twice in alternating order with fresh processes. It measures all photos, model startup, OCR, and preview assembly, and reports mean seconds per tube and peak OCR worker memory. The preview/benchmark parent peak is reported separately. These are not whole-app memory or upload-to-review measurements. Filesystem caches are not cleared. Results are saved to `thread-benchmark-results.json`; originals, reviews, sessions and CSVs are not changed. Expect several minutes for four complete processing passes.

Choose another tube or more repetitions with:

```bash
.venv-ocr/bin/python benchmark_threads.py --tube uploads/RECORD_ID --repeats 3
```

Use two threads only if the Pi results show a repeatable speed improvement with acceptable memory and unchanged field outputs. Retest on both label types and different photo counts. Tiny floating-point differences may affect OCR decisions; the tool reports whether final suggested fields, label type, and photo error statuses match. It does not automatically change your thread setting. A failed worker, timeout or all-photo failure stops the benchmark instead of treating it as fast successful recognition. Queue waiting, server work, database saves, ZIP conversion and upload transfer are excluded.
