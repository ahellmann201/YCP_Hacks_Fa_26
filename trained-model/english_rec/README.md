# English recognition comparison model

This is the unmodified `en_PP-OCRv5_rec_mobile.onnx` distributed by RapidAI/RapidOCR v3.10.0, renamed to `recognizer.onnx` for the shared helper. `characters.txt` is extracted from the model's embedded character metadata; CTC blank/space tokens are added by the helper.

Source: https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx

Model family: PaddleOCR PP-OCRv5 English mobile. See the included Apache 2.0 LICENSE and upstream [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) / [RapidOCR](https://github.com/RapidAI/RapidOCR) projects. This model was not fine-tuned on the tube dataset.

The model is stored in the repository for offline testing. No downloads or usage charges are required at inference time. It has not replaced the app's recognizer.

From the repository root:

```bash
python tube-training/onnx_recognizer.py /path/to/field_crop.jpg --model-dir trained-model/english_rec
```

On the same nine validation crops, it correctly reads both serial numbers, but only 4/9 complete fields overall. This small development sample does not establish superiority or general accuracy.
