# Smudge-augmented English recognizer

This offline English PP-OCRv5 mobile recognizer starts from the previous five-epoch English head checkpoint, then trains for 20 more epochs with the final backbone block and recognition heads trainable. Normalization remains frozen. Training uses the same 44 crops, with bounded faint ink transfer, local fading, marker-width variation and mild geometric/image augmentation. Original transcriptions and tube/source split boundaries are preserved. This trains recognition robustness, not a pixel-level smear-removal model.

| Development check | Previous English model | Smudge candidate |
|---|---:|---:|
| Clean exact fields | 5/9 | 6/9 |
| Clean character error rate | 10.71% | 8.93% |
| Synthetic smudge exact fields | 13/27 | 18/27 |
| Existing blur/rotation/brightness stress fields | 27/54 | 32/54 |
| Additional readable views | 2/3 | 2/3 |
| Blank fields | 2/2 | 2/2 |
| Separate repeatedly inspected marker reference | 0/2 | 0/2 |

The nine clean fields come from only four Small-label tubes repeatedly used for checkpoint selection. Synthetic variants are correlated copies, not additional independent tubes. Some transcriptions were assistant-produced. These results support a development update, not a general accuracy claim or a guarantee of less review on unseen tubes. Dates remain difficult. See [experiment details](../../tube-training/SMUDGE_TRAINING.md).

The app loads this model through `field_recognizer.py` for Small-label machine and serial-number crops only. Dates, Large-label text and circled component selections retain their existing recognition paths. Review thresholds are unchanged. No extra model, cleanup pass or OCR retry is added to the Pi pipeline. Missing/failed model loading or empty text falls back to original OCR. `SCANNER_FIELD_MODEL=rapidocr` selects the original pipeline.

The ONNX model is 7,850,705 bytes, the same architecture and size as its predecessor. Graph checking passed, all 36 CPU Paddle/ONNX predictions matched, and the standalone helper matched all 36. The parity report includes numerical tolerances. Windows CPU cropped-field testing measured roughly 0.02 seconds warm inference and 87.6 MiB process peak for this candidate, versus 88.6 MiB for the previous checkpoint. These are not Pi or full-tube timings. Rerun Pi benchmarks after updating; previous Pi results measured different weights.

```bash
.venv-ocr/bin/python tube-training/onnx_recognizer.py "PATH/TO/photo_1_machine.jpg" --model-dir trained-model/english_finetuned_rec
```

Initialization: official PaddleOCR English PP-OCRv5 mobile pretrained weights, followed by the recorded English head and smudge experiments. Training source revision `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`; Paddle 3.2.2 GPU for training, Paddle 3.1.1 CPU/paddle2onnx 2.1.0 for conversion, ONNXRuntime 1.31.1 CPU for parity. Apache 2.0 license and matching dictionary are included. Inference is entirely local.
