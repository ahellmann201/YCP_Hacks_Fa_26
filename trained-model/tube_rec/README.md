# Experimental tube handwriting recognizer

`recognizer.onnx` is the converted PP-OCRv5 mobile recognizer trained on 67 cropped fields. `characters.txt` is its matching CTC dictionary. Keep these two files together. No photo uploads, environment, training checkpoint or private dataset are included.

## Verified on Windows CPU

- ONNX structural checker passed; model size is approximately 16.5 MB.
- All 9 validation predictions match the trained Paddle checkpoint.
- Maximum absolute output difference on identical CPU inputs: **0.00001359**, within rtol 0.001 / atol 0.0001.
- The standalone inference helper also reproduces all 9 predictions.
- Exact-match accuracy remains **4/9**. Conversion preserves the existing model's behavior; it does not improve its handwriting accuracy.

`parity-report.json` records the comparison, `model-info.json` describes preprocessing and versions, and `checksums.json` records artifact hashes. The four development validation tubes are all Small labels; there has been no independent final test.

## Try a cropped field

From the repository root, using an environment with `tube-training/requirements-inference.txt` installed:

```bash
python tube-training/onnx_recognizer.py /path/to/field_crop.jpg
```

Inference uses ONNX Runtime CPU with one thread, without Paddle or model downloads. The helper takes one complete, upright field crop, uses BGR input at 48 x 320 with aspect-preserving resizing/right padding, and decodes CTC output. Do not pass an entire tube photograph and expect field detection.

This model has **not yet been benchmarked or connected to the Raspberry Pi app**. Keep the current recognizer available during integration. Barcode decoding, label detection, field cropping, circled selections and editable review remain separate app functions. Dates can be formatted afterward using `tube-training/date_formats.py`.

## Reproduce conversion

Use the GPU training environment to export Paddle inference files. On Windows the tested ONNX converter needs a separate CPU environment with Paddle 3.1.1; Paddle GPU 3.2.2 plus this converter failed to load its native extension. This compatibility issue is also reported in [Paddle2ONNX issue 1615](https://github.com/PaddlePaddle/Paddle2ONNX/issues/1615).

From `tube-training/`:

```powershell
py -3.12 -m venv .venv-convert
.\.venv-convert\Scripts\python.exe -m pip install -r requirements-convert.txt
.\.venv-train\Scripts\python.exe convert_recognizer.py --run "training-expanded\YOUR_RUN" --repo PaddleOCR --convert-python ".venv-convert\Scripts\python.exe" --output model-export
.\.venv-train\Scripts\python.exe verify_onnx_conversion.py --repo PaddleOCR --config "training-expanded\YOUR_RUN\finetune.yml" --checkpoint "training-expanded\YOUR_RUN\checkpoints\best_accuracy" --onnx model-export/recognizer.onnx --output model-export/parity-report.json --cpu
```

The conversion helper disables optional graph optimization; it does not install optional packages at conversion time. ONNX checking remains enabled. See the [official conversion documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/deploy/paddle2onnx/readme.md).

## Attribution

Fine-tuned from PaddlePaddle's PP-OCRv5_mobile_rec pretrained model. Architecture and dictionary originate from the [PaddleOCR project](https://github.com/PaddlePaddle/PaddleOCR), under Apache License 2.0; see the included LICENSE. The source checkpoint was downloaded from PaddlePaddle's official pretrained-model distribution. This is an experimental derivative, not an official PaddlePaddle model release.
