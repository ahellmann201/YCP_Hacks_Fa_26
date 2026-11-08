# LRS-3 demo package

[Download the software demo](LRS-3-software-demo.mp4) · [Download the presentation](LRS-3-project-presentation.pptx)

## Recording

Recorded on November 8, 2026 from the actual local scanner application at main commit `28be14b`, using three project photographs of one physical tube. The application decoded the barcode, retained unclear handwritten fields for review, and exported a CSV with the explicit include-unreviewed option. No API responses or readings were mocked. Browser display zoom was reduced to fit the review interface. Intro and closing cards explain the scope. The video is silent.

This is a software workflow demonstration. Physical motor movement, live phone capture, successful transcription of the handwritten fields, and a live xAI request are not shown. The per-session processing time visible in the recording is a single laptop example, not the earlier 20.8-second Pi benchmark or a general performance estimate. Values need review before use.

## Presentation

The 13-slide deck includes speaker notes and covers the problem, collection of 150+ images from 40+ samples, the documented field-crop training experiment, hardware iterations, the automatic capture design, local OCR, Grok review, results, limitations, next steps and challenge entries.

The 150+ images and 40+ sample counts are team-reported collection totals. The documented experiment used 44 training fields and 9 development fields; these counts describe different units and scopes. Its small development comparison improved clean exact fields from 5/9 to 6/9 and synthetic-smudge variants from 13/27 to 18/27. These are not an independent accuracy estimate. The 90% figure remains a target.

The earlier Pi benchmark averaged 20.8 seconds per tube, excluding capture, upload, queue wait and review. See [the training report](../../tube-training/SMUDGE_TRAINING.md) and [project README](../../README.md) for context. CAD previews in the slides illustrate designs rather than physical demonstration footage.
