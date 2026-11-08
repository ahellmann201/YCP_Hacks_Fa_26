# English model and formatted-date comparison

Run from `tube-training/` on a computer with the exported validation dataset:

```powershell
.\.venv-train\Scripts\python.exe compare_recognizers.py "exports\YOUR_EXPORT_FOLDER" --report model-comparison-report
```

The original RapidOCR model must already be cached in the environment, or supply `--original-model PATH_TO_ONNX`. English and trained model files are included under `trained-model/`. There are no downloads inside the comparison tool. All three models use the same fixed 48x320 BGR preprocessing and single-thread CPU inference. The dataset is never modified, and no training is performed.

Reports contain per-field predictions, raw exact matches, exact matches after date formatting, character error rate, confidence, and model SHA-256 hashes. Serial-number uppercase normalization is applied consistently; machine spaces and digits are not corrected or guessed.

Two-part dates are left for review by default because `9/20` may mean month/day or month/year. To explicitly use the requested month/year policy:

```powershell
.\.venv-train\Scripts\python.exe compare_recognizers.py "exports\YOUR_EXPORT_FOLDER" --two-part month_year --report model-comparison-report
```

That policy is recorded in the summary and any two-digit month/year assumption appears in the CSV. Full valid dates standardize separators and expand two-digit years to 20xx. Merged digits, invalid dates and missing characters are not repaired. An unchanged raw reading still counts as an exact transcription; the formatter does not turn an unreadable date into a valid one.

## Measured development results

| Model | Raw correct | Correct after date formatting | Serial numbers correct |
| --- | --- | --- | --- |
| Original multilingual | 4/9 | 5/9 | 1/2 |
| Fine-tuned multilingual | 4/9 | 5/9 | 1/2 |
| Pretrained English | 4/9 | 4/9 | 2/2 |

Date formatting accepts `9.27-26` as equivalent to `9.27.26`. It cannot repair the English reading `9.27-d6`. The English model correctly reads a repeated-zero serial number that the other models miss, but inserts a space in another machine number and makes different date mistakes.

These results use nine fields from the same four Small-label development tubes. Selecting models or routing fields based on this sample requires a separate unseen test before claiming improvement. Date formatting improves output usability, not raw OCR recognition. Do not silently substitute model readings based on confidence alone; confidence is not calibrated across models.

`comparison-results/summary.json` records the aggregate run. Detailed local results are left out of Git. The website and Raspberry Pi processing workflow remain unchanged; these are comparison tools for choosing the next integration experiment.
