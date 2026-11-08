# Tube OCR training tools

Train and evaluate a PP-OCRv5 mobile field-text recognizer on a Windows NVIDIA GPU computer. This folder is separate from the Raspberry Pi scanner application. No trained model is installed into the scanner by these tools.

## What is included

- Local photo conversion and field annotation tool; split all views of a tube together.
- Dataset export with group and identical-photo overlap checks.
- Original ONNX recognizer evaluation, conservative Paddle fine-tuning, checkpoint comparison.
- Date display formatting with raw values and explicit partial-date assumptions.
- Tests for dataset export, annotation saving and date formatting.

Photos, label records, virtual environments, pretrained/trained weights and generated exports are intentionally ignored. Keep a separate backup of your dataset. Existing project-specific assistant labels are available only in the original local training workspace.

## Windows setup

Run in this folder using Python 3.12. The tested framework is Paddle GPU 3.2.2 with CUDA 12.6 and an RTX 3060 Laptop GPU. Actual driver/runtime compatibility must be verified using the GPU check below.

```powershell
py -3.12 -m venv .venv-train
.\.venv-train\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv-train\Scripts\python.exe -m pip install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
.\.venv-train\Scripts\python.exe -c "import paddle; paddle.utils.run_check()"
git clone --depth 1 https://github.com/PaddlePaddle/PaddleOCR.git PaddleOCR
git -C PaddleOCR fetch --depth 1 origin dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf
git -C PaddleOCR checkout dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf
.\.venv-train\Scripts\python.exe -m pip install -r PaddleOCR/requirements.txt -r requirements-labeling.txt -r requirements-baseline.txt
Invoke-WebRequest "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/PP-OCRv5_mobile_rec_pretrained.pdparams" -OutFile PP-OCRv5_mobile_rec_pretrained.pdparams
```

The code expects PaddleOCR's `configs/rec/PP-OCRv5/PP-OCRv5_mobile_rec.yml` and its matching original training checkpoint/dictionary. An ONNX model cannot substitute for the training checkpoint. See the [official recognition training documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_recognition.en.md).

## Prepare the data

For HEIC photos, install ImageMagick with HEIC support. Put pictures in one numbered folder per tube, such as `Tube1/IMG_0001.HEIC`.

```powershell
.\.venv-train\Scripts\python.exe prepare_images.py "C:\path\to\sample_images"
.\.venv-train\Scripts\python.exe annotation_server.py
```

Use the local page to select label type, draw complete text-value crops, transcribe exactly what is visible, and assign Train or Validation per tube. Barcode IDs and small-label circled components are exported as separate tasks. Blank/uncertain text is excluded from recognition training. Keep partial dates and handwritten separators as written in the recognition targets. Serial numbers follow the app's uppercase policy.

Click Export approved/verified dataset after assigning both splits. For supplied assistant drafts, provenance remains distinct from human-reviewed labels; don't mistake automatic acceptance for independent verification.

## Train

Double-click **Start expanded training.cmd**, or run:

```powershell
.\.venv-train\Scripts\python.exe run_expanded_training.py
```

The newest local export is used. An existing dataset elsewhere can be selected with `--dataset "C:\path\to\export"`. `--prepare-only` validates files and writes a configuration without training.

Each run gets a new timestamped folder under `training-expanded/`. It evaluates the original checkpoint, trains ten epochs, then evaluates the saved checkpoint. It starts from original pretrained weights, freezes the backbone and normalization layers, uses fixed-size inputs, batch size four, and learning rate 0.000003. It does not overwrite previous experiments.

For Windows, this tool makes a narrow local change to PaddleOCR's evaluator to include the last validation batch, which the tested upstream implementation skips. Data-loader workers remain zero. The PaddleOCR revision is recorded in the generated metadata.

```powershell
.\.venv-train\Scripts\python.exe inspect_predictions.py "training-expanded\YOUR_RUN"
```

This saves per-field predictions for original and trained checkpoints. Report raw exact-match accuracy separately from formatted-date accuracy; date formatting is postprocessing, not evidence of better handwriting recognition.

## Current experiment results

The additional [thick-marker training experiments](MARKER_TRAINING.md) ran twenty further epochs with controlled stroke-width augmentation. Validation stayed at 5/9 and the separate two-field Sharpie-style reference still failed, so no new model was deployed. See the recorded comparison rather than assuming training itself improved recognition.

The newer [cleaned-data and English fine-tuning experiments](TRAINING_EXPERIMENTS.md) completed all five stages. The selected English head-only candidate gets 5/9 raw exact matches, versus 4/9 originally, with character error rate 10.71% versus 19.64%. Date-formatted accuracy remains 5/9. These are preliminary development measurements; the Pi app still uses its existing recognizer.

The local dataset contained 38 tube folders / 114 photos, with 67 training and 9 validation recognition crops. After ten epochs, raw validation exact matches stayed at 4/9; mean normalized edit similarity increased from 0.798942 to 0.839065. The validation set has only four Small-label tubes. These are preliminary development results, not proof of general accuracy, Large-label accuracy or writer-independent performance. Additional unseen tubes are needed for a final test.

`date_formats.py` formats full dates as `MM/DD/YYYY` and configured month/year values as `MM/YYYY`, retaining raw values. Two-digit years use 20xx. Two-part month/year interpretation is flagged as an assumption; merged OCR digits and impossible dates require correction. This formatter is not connected to the Pi app yet.

## Tests and deployment

See [MODEL_COMPARISON.md](MODEL_COMPARISON.md) for comparing the included English recognizer with both multilingual models and scoring date formatting separately from raw OCR. The measured result is 5/9 after date formatting for the original and fine-tuned models, versus 4/9 for English; English correctly reads both tested serial numbers. The app's model choice is unchanged.

```powershell
.\.venv-train\Scripts\python.exe -m unittest -v test_dataset test_draft_labels test_date_formats test_comparison test_annotation_server
```

The converted model and CPU parity results are now available in [trained-model/tube_rec](../trained-model/tube_rec/README.md), with conversion and standalone inference helpers in this folder. Measuring memory/latency on the Pi 3 and app integration remain to be done. The existing app retains its barcode, label detection/cropping and review functions. No automatic-cropping or circled-selection model is trained here.
