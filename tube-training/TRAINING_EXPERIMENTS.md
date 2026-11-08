# Small-data recognition experiments

These experiments change field-text recognition. Barcode decoding, automatic label cropping, circled component detection, and the Pi app remain separate and unchanged.

## Prepared data

The local `cleaned-training-v1` dataset contains 44 training crops and the original nine validation crops from four Small-label tubes. It starts from 67 training crops, excludes 25 clipped, ambiguous, overlapping, or incorrectly assigned examples, and adds two readable angles from training tubes. Selected surviving crops were trimmed or expanded from the original photo. Source photos, annotations, and the original export remain intact.

The nine validation image files and `val.txt` are byte-for-byte unchanged. Tube groups and source-photo hashes cannot cross splits. Some labels are assistant-transcribed and automatically accepted at the user's request; they are not independently human-verified. Private photos, crops, checkpoints, and data-specific cleanup recipes are kept locally rather than committed.

`clean_training_crops.py` applies an exclusion/trim/expansion recipe to a new dataset copy. It ignores recipes targeting validation examples and records its changes. Example recipe entries, keyed by annotation ID:

```json
{
  "clipped-example-id": {"exclude": "First handwritten character is outside the crop"},
  "neighbor-text-id": {"trim": [0, 0.1, 1, 0.9]},
  "tight-top-id": {"expand_top": 35}
}
```

Expansion also requires `--image-manifest manifest.json` from the labeling workspace. Trim values are fractions of the current crop width/height; expansion is in source-image pixels. Additional angles must stay in their existing tube's split.

## Run the experiments

Use the existing Windows GPU training environment and matching PaddleOCR source checkout, tested at revision `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`. Supply the original multilingual and English **training** `.pdparams` checkpoints, not ONNX inference files. English uses `configs/rec/PP-OCRv5/multi_language/en_PP-OCRv5_mobile_rec.yaml` and its English dictionary.

```powershell
.\.venv-train\Scripts\python.exe run_training_experiments.py --dataset cleaned-training-v1 --repo PaddleOCR --multilingual-weights PP-OCRv5_mobile_rec_pretrained.pdparams --english-weights en_PP-OCRv5_mobile_rec_pretrained.pdparams --output experiments-new
```

Choose a fresh output folder for each run. The runner makes the same narrow PaddleOCR evaluator adjustment as the earlier workflow so Windows includes its final validation batch. It records the upstream revision and asserts that all nine predictions are evaluated in label-file order.

If interrupted, add `--resume` with the same arguments. Completed stages are retained; the incomplete stage restarts from its specified initial checkpoint, not its interrupted optimizer state. Dataset fingerprints reject changes to labels or crop files between runs. Both model templates have validation shuffling explicitly disabled.

| Stage | Initialization | Epochs | Image variations | Backbone |
|---|---|---:|---|---|
| cleaned_head | Original multilingual checkpoint | 10 | None | Frozen |
| augmented_head | Original multilingual checkpoint | 10 | Mild | Frozen |
| partial_backbone | Best augmented_head checkpoint | 5 | Mild | Final `blocks6` trainable |
| english_head | Original English checkpoint | 5 | Mild | Frozen |
| english_partial | Best english_head checkpoint | 5 | Mild | Final `blocks6` trainable |

All normalization layers and their parameters stay frozen. Batch size is four, loader workers zero, seed 1024, and input size 48×320 with BGR normalization and right padding. Head-only learning rate starts at 0.000003; partial-backbone learning rate starts at 0.000001. English and multilingual stages have different epoch budgets, so this is an exploratory model comparison rather than an equal-budget causal experiment.

Half of training images pass through unchanged. Otherwise one mild variation is chosen: rotation up to two degrees with an expanded canvas, brightness adjustment, slight blur, or downscale-and-restore. Validation images receive no augmentation. These transformations add variation, not new independent handwriting examples.

Each stage saves its configuration, initialization details, training log, checkpoint, and per-field CPU evaluation. Aggregate results are in `summary.json`. Raw exact matches, date-formatted matches, and character error rate are separate metrics. Ambiguous two-part dates retain the formatter's review policy; missing date parts are not invented.

## Interpretation and export

Measured on the unchanged nine-field development set:

| Experiment | Raw correct | After date formatting | Character error rate |
|---|---:|---:|---:|
| Original multilingual | 4/9 | 5/9 | 19.64% |
| Cleaned data, frozen backbone | 4/9 | 5/9 | 14.29% |
| Cleaned data + augmentation | 4/9 | 5/9 | 14.29% |
| Multilingual final-block training | 4/9 | 5/9 | 12.50% |
| Original English | 4/9 | 4/9 | 14.29% |
| English head fine-tuning | **5/9** | **5/9** | **10.71%** |
| English final-block training | **5/9** | **5/9** | **10.71%** |

The English head-only checkpoint is selected for a separate candidate export: the subsequent backbone stage did not improve these metrics. English reads both validation serial numbers correctly; its date errors remain. The original multilingual model still reads one full date better after formatting, so English is not a universal winner. Aggregate measurements are in [experiment-results/summary.json](experiment-results/summary.json).

The converted [English fine-tuned candidate](../trained-model/english_finetuned_rec/README.md) is included for offline Pi testing. All nine CPU Paddle, ONNX, and helper predictions match. ONNX graph checking passed; Pi performance is still unmeasured.

This small validation set is repeatedly used to choose checkpoints. It contains no Large-label validation examples and is not an independent final test. More epochs or better development scores alone do not establish better performance on new tubes or writers.

Keep the original model available. Convert a selected run using `convert_recognizer.py`, which copies the dictionary from that run's configuration, and verify CPU Paddle/ONNX parity with `verify_onnx_conversion.py`. Measure latency and memory on the Pi before changing the app's default recognizer.

## Pi speed and memory benchmark

From the repository root, run:

```bash
.venv-ocr/bin/python tube-training/benchmark_recognizers.py
```

This automatically selects up to three saved field crops under `uploads/` and compares the previous trained multilingual model with the new English candidate. Each model gets a fresh process with one CPU thread. It reports model loading, first recognition, warm median/p95 latency, and peak process memory, saving `benchmark-results.json`. Close the scanner server first to measure standalone resource use. Keep both runs under the same background load and power/temperature conditions.

To choose a crop or make a longer run, add `--image "PATH/TO/CROP.jpg" --repeats 10`. Repeat `--image` for more crops. Warm timings include preprocessing and text decoding but exclude reading photos, barcode detection, automatic cropping, and the web app. Peak memory includes the Python interpreter, libraries, loaded images, and model; it is not the full running scanner's memory requirement. Fresh processes do not clear the filesystem cache. Windows measurements are supported for checking the tool but do not predict Pi performance.
