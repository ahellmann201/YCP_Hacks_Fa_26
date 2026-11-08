# Fine-tuned English recognition candidate

This offline ONNX model is an English PP-OCRv5 mobile recognizer fine-tuned for five epochs on 44 cleaned tube-field crops. Its backbone and normalization were frozen; training used mild image variations. The matching dictionary, Apache 2.0 license, checksums, metadata, and CPU conversion parity report are included.

| Same nine development fields | Original multilingual | This candidate |
|---|---:|---:|
| Raw exact matches | 4/9 | 5/9 |
| After date formatting | 5/9 | 5/9 |
| Character error rate | 19.64% | 10.71% |

Only four Small-label tubes are represented in validation. The set was repeatedly used to choose checkpoints, and some training labels were assistant-transcribed. This is a candidate for further testing, not evidence of general or Large-label accuracy. Dates remain problematic. See [training experiment details](../../tube-training/TRAINING_EXPERIMENTS.md).

Conversion passed ONNX graph checking. All nine CPU Paddle predictions match ONNX and the standalone helper, with maximum absolute output difference 0.0000319481. Model size is 7,850,705 bytes. The user's Pi benchmark measured 1.25s loading, 0.66s first field, 0.63s warm median, and 96.7 MiB peak process memory, versus 1.60s / 0.81s / 0.70s / 114.2 MiB for the earlier trained multilingual model. These are standalone field-recognizer measurements.

`scanner_auto.py` now uses this candidate for Small-label machine and serial-number crops through `field_recognizer.py`. Dates, Large labels, full-photo label detection, and circled selections retain the original OCR. RGB photo crops are converted to the recognizer's BGR input. The candidate is loaded once per tube worker when first needed; it is not kept resident between tubes. Missing/failed model loading or empty output falls back to original OCR. To compare the original pipeline on identical images, start the server with `SCANNER_FIELD_MODEL=rapidocr`; omit the setting to enable the candidate routing. Measure full per-tube latency and memory after integration: the worker still contains the original OCR model as well as this candidate.

From the repository root on the Pi, test an existing **field crop**:

```bash
.venv-ocr/bin/python tube-training/onnx_recognizer.py "PATH/TO/photo_1_machine.jpg" --model-dir trained-model/english_finetuned_rec
```

This recognizer handles cropped text only. Continue using barcode decoding for Sample ID and the existing app's label detection, cropping, and review workflow. Inference needs no network or usage-based service.

Initialization: official PaddleOCR `en_PP-OCRv5_mobile_rec_pretrained.pdparams`, from [Paddle's model repository](https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/en_PP-OCRv5_mobile_rec_pretrained.pdparams). Training source revision: `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`. Training used Paddle 3.2.2 GPU; conversion used Paddle 3.1.1 CPU and paddle2onnx 2.1.0; CPU inference parity used ONNXRuntime 1.31.1.
