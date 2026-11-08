# Smudge robustness experiment

Completed 20 epochs starting from `experiments-v2/english_head`. The final backbone block and heads train, normalization stays frozen, learning rate is 0.000001, seed 1024, batch size four. The existing 44 training fields and nine development fields retain their original labels and whole-tube/source split. No image or label from validation was added to training.

`SmudgeAugment` leaves 45% of its inputs unchanged. Otherwise it makes a faint nearby blurred ink transfer and gentle localized fading. Main dark strokes remain visible; it never overlays opaque blobs, guesses a new transcription, or changes a source photo. Marker-width and mild image augmentation also remain active. Synthetic ink transfer is an approximation of some smears; recognition of real damage needs real examples and cannot recover hidden strokes reliably. PaddleOCR documents small-learning-rate fine-tuning and combining real data with augmentation: [official fine-tuning guidance](https://www.paddleocr.ai/v2.10.0/en/ppocr/model_train/finetune.html).

## Results

| Development check | Previous deployed English model | Smudge model |
|---|---:|---:|
| Clean exact fields | 5/9 | 6/9 |
| Clean character error rate | 10.71% | 8.93% |
| Fixed synthetic smudge variants only | 13/27 | 18/27 |
| Existing controlled stress variants | 27/54 | 32/54 |
| Extra readable views | 2/3 | 2/3 |
| Blank-field checks | 2/2 | 2/2 |
| Separate numeric marker reference | 0/2 | 0/2 |

The improved clean field is machine `UP7102`. All three tested machines and both serials are now exact. Dates still fail in three of four clean cases. The app therefore retains its existing date and Large-label paths; the new weights replace the English model used for Small-label machines/serials. Confidence thresholds and review rules are unchanged. Correct text can still carry a review warning; fewer flags have not been established on an independent batch.

The clean validation has four Small-label tubes and was repeatedly used for selection. Stress versions are correlated copies of those fields. The extra marker reference has been inspected repeatedly. These are development measurements, not a new independent test set, writer generalization proof or a claim that every smear is recognized. The private dataset retains mixed human-reviewed/assistant-transcribed provenance. Per-field predictions and comparisons are in [smudge-results](smudge-results).

## Reproduce

From the Git checkout, with the existing private training workspace and GPU environment:

```powershell
& ../tube-training/.venv-train/Scripts/python.exe tube-training/run_marker_training.py --base-run ../tube-training/experiments-v2/english_head --dataset ../tube-training/cleaned-training-v1 --repo ../tube-training/PaddleOCR --output ../tube-training/smudge-training-new --epochs 20 --partial --smudge
& ../tube-training/.venv-train/Scripts/python.exe tube-training/build_smudge_validation.py ../tube-training/cleaned-training-v1 ../tube-training/smudge-validation-new
```

Choose fresh output directories. The training runner saves configuration, checkpoint, source fingerprints, metadata and before/after predictions locally. It does not select an app model automatically. `build_smudge_validation.py` writes one clean and three deterministically smudged copies per held-out recognition crop, checks split boundaries and never changes input crops.

Conversion used `convert_recognizer.py`, then `verify_onnx_conversion.py --cpu` with the stress-suite config. All 36 decoded predictions matched Paddle, ONNX and standalone preprocessing. Graph checking and the current app regression suite passed. Model size remains 7,850,705 bytes with one recognizer and no extra inference passes. Windows cropped-field latency and peak memory were similar to the prior model; see the recorded benchmark. Pi full-tube latency/memory must be remeasured on the Pi.

The selected weights are shipped in `trained-model/english_finetuned_rec`; the prior weights remain accessible in Git commit `90bcd32`. Dataset images and Paddle checkpoints stay in the private local workspace.
