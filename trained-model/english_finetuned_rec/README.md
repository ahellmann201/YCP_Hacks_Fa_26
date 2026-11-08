# Fine-tuned English recognition candidate

This offline ONNX model is an English PP-OCRv5 mobile recognizer fine-tuned for five epochs on 44 cleaned tube-field crops. Its backbone and normalization were frozen; training used mild image variations. The matching dictionary, Apache 2.0 license, checksums, metadata, and CPU conversion parity report are included.

| Same nine development fields | Original multilingual | This candidate |
|---|---:|---:|
| Raw exact matches | 4/9 | 5/9 |
| After date formatting | 5/9 | 5/9 |
| Character error rate | 19.64% | 10.71% |

Only four Small-label tubes are represented in validation. The set was repeatedly used to choose checkpoints, and some training labels were assistant-transcribed. This is a candidate for further testing, not evidence of general or Large-label accuracy. Dates remain problematic. See [training experiment details](../../tube-training/TRAINING_EXPERIMENTS.md).

Conversion passed ONNX graph checking. All nine CPU Paddle predictions match ONNX and the standalone helper, with maximum absolute output difference 0.0000319481. Model size is 7,850,705 bytes. Pi latency and memory have not yet been measured for this candidate, and the app's default recognizer is unchanged.

From the repository root on the Pi, test an existing **field crop**:

```bash
.venv-ocr/bin/python tube-training/onnx_recognizer.py "PATH/TO/photo_1_machine.jpg" --model-dir trained-model/english_finetuned_rec
```

This recognizer handles cropped text only. Continue using barcode decoding for Sample ID and the existing app's label detection, cropping, and review workflow. Inference needs no network or usage-based service.

Initialization: official PaddleOCR `en_PP-OCRv5_mobile_rec_pretrained.pdparams`, from [Paddle's model repository](https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/en_PP-OCRv5_mobile_rec_pretrained.pdparams). Training source revision: `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`. Training used Paddle 3.2.2 GPU; conversion used Paddle 3.1.1 CPU and paddle2onnx 2.1.0; CPU inference parity used ONNXRuntime 1.31.1.
