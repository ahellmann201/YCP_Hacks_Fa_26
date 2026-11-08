# Thick-marker training experiment

Two additional English-recognizer stages were run on the existing 44 cleaned training crops: ten epochs with the head trainable, then ten with the final backbone block also trainable. Both keep normalization fixed and use learning rate 0.000001. The original nine validation crops and all tube/source-photo split boundaries were unchanged.

The training photos include a few readable thick-marker-style machine values and a bold partial date. Pen brands are not known. `MarkerStrokeAugment` adds small stroke-width variations without changing text targets: 55% of crops pass unchanged, otherwise dark strokes are thickened in 75% of augmented cases and thinned in 25%. These synthetic variations do not add independent handwriting or make an unreadable smear a valid target. Mild image augmentation remains active. Existing human-reviewed/assistant-transcribed label provenance is unchanged.

| Model stage | Validation exact | Validation character errors | Extra marker reference exact |
|---|---:|---:|---:|
| Existing English fine-tuned baseline | 5/9 | 10.71% | 0/2 |
| +10 epochs, marker augmentation | 5/9 | 10.71% | 0/2 |
| +10 epochs, final backbone block | 5/9 | 10.71% | 0/2 |

The extra two-field development check uses the supplied `27` / `4.13.26` reference label, with manually checked numeric targets, excluded from training. Both stages still read `37 ` and `4.13-34` there. This case has been inspected repeatedly during development, so it is not a fresh independent final test. The original nine-field validation also contains only four Small-label tubes. [Machine-readable results](marker-results/summary.json).

**No model was deployed or overwritten:** the experiments did not establish a recognition improvement. The deployed Large-label path remains unchanged. Further work needs more checked, readable thick-marker dates/digits from distinct tubes and writers, with some whole tubes reserved from all training. Repeating the same few labels or adding more epochs cannot guarantee the year/digit is learned correctly. Smears and missing strokes should remain quality/review cases, not guessed training transcriptions.

## Reproduce on the Windows training machine

Use the existing GPU environment and PaddleOCR checkout. Paths below are examples from the local training workspace; choose a new output folder each time:

```powershell
.\.venv-train\Scripts\python.exe run_marker_training.py --base-run experiments-v2/english_head --dataset cleaned-training-v1 --repo PaddleOCR --output marker-training-new --epochs 10
.\.venv-train\Scripts\python.exe run_marker_training.py --base-run marker-training-new --dataset cleaned-training-v1 --repo PaddleOCR --output marker-training-partial-new --epochs 10 --partial
```

If tools live in the separate Git checkout, invoke `run_marker_training.py` through its full path. Configurations, logs, checkpoints, dataset fingerprints and per-field evaluations remain in the private local output directories. Photos/checkpoints are not committed. The runner does not install or select an app model. Conversion and Pi performance checks are still required before deploying any future successful experiment.
