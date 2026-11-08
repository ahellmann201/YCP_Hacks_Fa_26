# One to four OCR CPU threads

`SCANNER_OCR_THREADS` accepts `1`, `2`, `3` or `4`, defaulting to `1`. It controls ONNXRuntime intra-operation threads for both RapidOCR and the fine-tuned English field recognizer. Inter-operation threads, OpenCV and BLAS remain at one to avoid multiplying thread pools. The queue still processes one tube at a time; photos remain sequential. Models are still loaded per tube worker. This setting does not introduce simultaneous tube processes or persistent model caching.

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

This defaults to the latest saved tube, running 2, 3 and 4 threads twice each in forward/reverse order with fresh processes. It measures all photos, model startup, OCR, and preview assembly, and reports mean seconds per tube and peak OCR worker memory. The preview/benchmark parent peak is reported separately. These are not whole-app memory or upload-to-review measurements. Filesystem caches are not cleared. Results are saved to `thread-benchmark-results.json`; originals, reviews, sessions and CSVs are not changed. Expect several minutes for six complete processing passes. To repeat the earlier comparison, add `--thread-counts 1 2`. The default server thread count is unchanged; benchmarking does not change startup settings.

Choose another tube or more repetitions with:

```bash
.venv-ocr/bin/python benchmark_threads.py --tube uploads/RECORD_ID --repeats 3
```

The user's earlier Pi test measured 34.73s/tube with one thread versus 27.59s with two, with identical fields and peak OCR-worker memory of 307.4 versus 310.0 MiB. Three and four threads still need Pi benchmarking. Choose the setting with a repeatable speed improvement, acceptable memory and unchanged field outputs. Four threads may reduce the website's responsiveness, so check it during actual uploads. Retest on both label types and different photo counts. Tiny floating-point differences may affect OCR decisions; the tool reports whether final suggested fields, label type, and photo error statuses match. It does not automatically change your thread setting. A failed worker, timeout or all-photo failure stops the benchmark instead of treating it as fast successful recognition. Queue waiting, server work, database saves, ZIP conversion and upload transfer are excluded.

## Multiple-tube throughput test

The subsequent Pi comparison measured mean times of 27.93s, 25.93s and 27.48s with 2, 3 and 4 threads respectively, on one saved tube. All fields matched. Three threads is the current candidate for a broader test:

```bash
.venv-ocr/bin/python benchmark_threads.py --samples 10 --thread-counts 3 --repeats 2
```

This selects up to ten distinct usable saved tube records, alternating between available label-type/photo-count groups. It omits exact photo-set duplicates and repeated nonblank sample barcode IDs. Variations of a physical tube without a readable barcode may still be counted separately. It cannot create label types or photo counts that are absent from your uploads. The actual number selected is printed.

Each tube runs twice, with the second pass reversing tube order. Ten tubes at roughly 26 seconds each take around nine minutes for twenty runs. The summary reports mean/median duration across runs, slowest tube mean, number of tubes with a mean at or below 30 seconds, and peak OCR worker memory. The JSON includes per-tube breakdowns, photo counts and detected labels. The overall mean is a throughput measure; not every tube must finish within 30 seconds. Partial runs are saved as the benchmark progresses, but an incomplete report is not a finished batch average.

Output consistency is checked separately within each tube, so different tube IDs are expected rather than treated as inconsistent readings. When there is only one run per tube, consistency is untested (`null`). This test does not measure accuracy against approved fields. It never edits the scanner database or saved OCR/review files. Stop the web server before testing for comparable standalone measurements.
