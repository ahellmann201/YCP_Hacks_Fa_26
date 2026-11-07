# Spin Station: Agent Instructions

Read this whole file before changing anything. Then work only on your assigned agent section.

**Deadline:** Sunday Nov 8, 9:00 AM EST.
**Goal:** win the MRG Labs Schneider Prize. MLH sponsor prizes are secondary.

## 1. Product

A benchtop station films a rotating sample tube with a phone and turns the wrapped label into a flat image or a set of clear views. The software reads the label locally, checks its own work, and retries uncertain fields. A non-technical clerk reviews what is still uncertain and exports a CSV.

Pitch: **"A label reader that checks its own work, and only asks for help when it needs to."**

### Required by MRG

An incomplete project is not judged on stretch goals, so finish these first.

1. Easy, repeatable label scanning
2. Reads handwritten and typed text
3. Saves an image for human review of every sample
4. Gives a confidence level for each reading
5. Exports multiple samples to a user-named, 7-column CSV
6. Runs on a workstation or Raspberry Pi
7. Is usable by a non-technical clerk, with no terminal or code
8. Handles batches of hundreds of samples
9. Supports label format changes through templates

Stretch goals: a robust UI, and on-screen correction of low-confidence strings, including after a batch ends.

### Guidance from MRG (Sean Neuman)

- Do not build gantry integration. No gantry details will be provided.
- The gantry would hold a sample on a vertical spinning hand. A separate spinner or human-operated instrument could be useful.
- Online or offline both work.
- Avoid token costs and subscriptions. AI is acceptable only if it significantly outperforms other options.

## 2. Rules for every agent

1. **Stay in your files.** Edit only the files you own in Section 5. If you need a change elsewhere, write it under "Requests" in `docs/handoff.md`.
2. **Protect the contract.** Only the Pipeline agent may change Section 4.
3. **Keep the core local.** It must work with no internet, API key, or paid service. Do not use Vultr or any cloud deployment.
4. **Keep sponsors optional.** Sponsor features stay off by default, and the app must work without them.
5. **Never fabricate results.** Report real measurements, including failures. Never hardcode label values or match on known Sample IDs.
6. **Keep real and synthetic results separate.** Label every metric as real or synthetic.
7. **Protect the test set.** Never train on `data/samples/`, `data/truth.csv`, or any held-out synthetic split.
8. **Design for the Pi.** Prefer small models and CPU inference. Do not load heavy models at import time.
9. **Keep it simple.** Build only your assigned task. Do not refactor another agent's code.
10. **Test your work.** Add a test in `tests/` for logic you write, then run it before reporting done.
11. **Commit small changes** with a clear message. Do not commit `.env`, secrets, `.venv/`, or `out/`.
12. **Hand off.** When you finish a task, update your section of `docs/handoff.md` with what works, what does not, and how to run it.

## 3. Current state

The baseline scores 11/32 attempted fields correct (34%) on real labels. `score.py` reports 19/40 because blank fields that were never attempted count as correct.

| Area | Status |
|---|---|
| Barcode Sample ID | 9/9 |
| Circled options, small labels | 5/5 |
| Machine | 1/8 |
| Date Sampled | 1/8 |
| Large label Component | 0/3 |
| Confidence flag | Caught 20 of 21 wrong values (only 8 scored labels) |

Known issues:

- Handwriting is the main weakness.
- `register.py` handles scale but not rotation. It expects a tight, nearly straight label.
- No review output exists. Confidence is only in `results.jsonl`.
- Failed images are missing from the CSV.
- Reusing a batch name skips images already processed.
- There are no typed label samples and no real tube footage yet.
- Sample `125719` is in MRG's example CSV but has no image. `111329` has an image but no truth row.
- `123779` is `420 NDF` in the truth file, but the label may read `420 NPF`. This is unconfirmed.
- `tests/` is empty, and the project is not a git repo yet.

## 4. Shared contract

Owner: Pipeline agent. Each line of `results.jsonl` is one sample:

```json
{
  "image": "scan_0001.jpg",
  "template": "small",
  "sample_id": "111333",
  "status": "accepted",
  "error": null,
  "fields": [
    {
      "column": "Machine",
      "value": "UP 6509",
      "confidence": 0.91,
      "crop": "machine.jpg",
      "note": "",
      "needs_review": false,
      "source": "local",
      "original_value": null
    }
  ]
}
```

- `status`: `accepted`, `needs_review`, or `failed`.
- `source`: `barcode`, `local`, `retry`, `llm`, `clerk`, or `system`.
- `needs_review`: true when confidence is below `REVIEW_BELOW` (0.80) or a format check fails.
- `original_value`: the machine's value after a clerk changes it. Otherwise null.
- A failed sample keeps its image and appears in the review queue. It is never silently dropped.

CSV rules:

- Keep these exact columns, in this order: `Sample ID,Date Sampled,Date Received,Machine,Component,Serial Number,Refrence Lube`
- Keep MRG's spelling, `Refrence`.
- Write UTF-8 with a BOM.
- Use `M/D/YYYY` dates. Date Received is today's date.
- A field that is empty on the label stays empty.
- Large labels leave Serial Number blank. Small labels leave Refrence Lube blank.

Reader interface, from `handwriting.py`: `read(crop: np.ndarray) -> Reading(text, probability)`.

Capture output: a folder of flat `.jpg` label images, or one folder of views per sample, as described in the Capture agent section.

## 5. Agents and file ownership

Person A runs agents 1 to 3. Person B runs agents 4 to 6.

| # | Agent | Person | Owns |
|---|---|---|---|
| 1 | Capture | A | `labelreader/capture/`, `tests/test_capture.py` |
| 2 | Reader | A | `labelreader/handwriting.py`, `labelreader/normalize.py`, `labelreader/readers/`, `bench/compare_readers.py`, `tests/test_readers.py`, `tests/test_normalize.py` |
| 3 | Data and Training | A | `training/`, `bench/stress_test.py`, `models/` |
| 4 | Pipeline | B | `labelreader/pipeline.py`, `labelreader/register.py`, `labelreader/choices.py`, `labelreader/retry.py`, `labelreader/score.py`, `labelreader/__main__.py`, `templates/`, `pyproject.toml`, `tests/test_pipeline.py` |
| 5 | App | B | `app/`, `tests/test_app.py` |
| 6 | Demo and Hardware | B | `rig/`, `app/static/live.html`, `app/static/live.js`, `pi/`, `pitch/`, `README.md` |

Shared: `docs/handoff.md`, where each agent edits only its own section. Do not edit `data/`.
The App agent owns `app/` except for the two `live` files listed under Demo and Hardware.

### Agent 1: Capture

Goal: turn real tube footage into images the pipeline can read.

| File | Purpose |
|---|---|
| `labelreader/capture/frames.py` | Load video, drop blurred frames, detect the barcode to start and stop a scan |
| `labelreader/capture/unwrap.py` | Plan A: stitch the centre strip of each frame into a flat label |
| `labelreader/capture/views.py` | Plan B: choose 4 to 6 sharp views at different angles |
| `labelreader/capture/straighten.py` | Rotate and crop a label so `register.py` can use it |

Tasks, in order:

1. Test Plans A and B on real tube video as early as possible.
2. Add straightening, because the pipeline needs a nearly straight label.
3. Report which plan to use at Checkpoint 1.

Done when a real tube video produces images where the barcode and all captions are found.

Fallbacks: A is the stitched spin, B is the set of views, C is clerk-guided photos, and D is replaying saved scans.

### Agent 2: Reader

Goal: raise real-label accuracy without adding running costs.

| File | Purpose |
|---|---|
| `labelreader/readers/trocr.py` | Current TrOCR reader, moved behind the same interface |
| `labelreader/readers/digits.py` | Small ONNX reader for dates, machine numbers, and serials |
| `labelreader/readers/llm.py` | Optional Gemini vision reader, off by default, crops only |
| `bench/compare_readers.py` | Compare accuracy, speed, and cost per 100 samples |

Tasks, in order:

1. Build the comparison using the current TrOCR reader.
2. Improve preprocessing and the rules in `normalize.py`.
3. Add the digit reader once Agent 3 exports a model.
4. Test typed text as soon as a typed sample is available.
5. Add the Gemini reader only after the core path works. Read the API key from `.env`, send only uncertain field crops, and include it in the comparison.

Done when the comparison reports per-field accuracy, seconds per label, and cost per 100 samples. Keep the existing imports from `handwriting.py` working.

### Agent 3: Data and Training

Goal: produce training data, a small model, and a stress test.

| File | Purpose |
|---|---|
| `training/generate_labels.py` | Create synthetic large and small labels with known truth |
| `training/train_digits.py` | Train the digit and date model on CPU |
| `training/export_onnx.py` | Export the model to `models/` |
| `bench/stress_test.py` | Run 1,000 synthetic samples and report throughput and failures |

Tasks, in order:

1. Build the generator with blur, glare, rotation, stains, and curvature.
2. Create separate train, validation, and test splits using a fixed seed.
3. Start the overnight training run. This machine has 12 CPU cores, about 7 GB of RAM, and no visible NVIDIA GPU.
4. Export the model and give Agent 2 its input format.
5. Run the 1,000-sample stress test on the full pipeline.

Done when `models/` has an ONNX model and its real-label result has been measured by Agent 2. If it does not beat TrOCR on real labels, say so and do not ship it as the default.

Do not use YOLO unless the Pipeline agent reports that caption matching fails on real unwrapped labels.

### Agent 4: Pipeline

Goal: make the core reliable and own the shared contract.

Tasks, in order:

1. Run `git init`, commit the baseline, and create `docs/handoff.md`.
2. Implement the Section 4 contract in `pipeline.py`.
3. Include failed samples in the results so they reach the review queue.
4. Separate batch reruns from resume so code changes cannot reuse old results by accident.
5. Fix `score.py` to report attempted-field accuracy, with blank non-applicable fields shown separately.
6. Add `labelreader/retry.py` to retry uncertain fields from other views, then the optional LLM step, then send them to the clerk.
7. Add multi-view input from Agent 1.

Done when one command processes a folder, produces valid results, and never loses a sample.

### Agent 5: App

Goal: let a clerk complete a batch with no terminal.

| File | Purpose |
|---|---|
| `app/server.py` | Local web server, binding to the local network only |
| `app/jobs.py` | Background batch queue with progress and resume |
| `app/static/` | Batch, review, and export screens |

Tasks, in order:

1. Build the review screen first, using `out/baseline/results.jsonl`.
2. Add batch upload and CSV naming.
3. Show each crop next to its value, confidence, and an editable input.
4. Save corrections with `source: "clerk"` and keep `original_value`.
5. Support reviewing all flagged fields after a batch ends.
6. Export the CSV, and warn if any fields are still unreviewed.

Done when a person who has never seen the app can upload, review, and export without help.

### Agent 6: Demo and Hardware

Goal: make the demo real and hard to break.

| File | Purpose |
|---|---|
| `rig/` | Build notes, camera position, lighting, and any motor code |
| `app/static/live.html`, `app/static/live.js` | Live view of real stages and the two bins |
| `pi/` | Raspberry Pi setup and start script |
| `README.md` | Clerk instructions and setup steps |
| `pitch/` | Diagram, results slide, and demo script |

Tasks, in order:

1. Build a hand-turned rig that holds the tube upright, with a fixed phone and soft light.
2. Record real scans and keep them for replay.
3. Build the live view from real pipeline output. It must not be a fake animation.
4. Add a replay mode for use if hardware fails.
5. Test on the Pi after Checkpoint 2, then record seconds per label.
6. Add a motor only if everything above works.
7. Write the demo script around one clerk finishing a batch.

Done when the demo can run start to finish twice in a row, including from replay mode.

## 6. Checkpoints

| When (EST) | Must be true |
|---|---|
| Sat 10:00 | Git and contract are done. Capture has tested real footage. Reader comparison runs. App shows baseline results. Training is running or finished. |
| Sat 18:00 | A real tube goes end to end: scan, read, review, and CSV. |
| Sun 00:00 | Core features are frozen. The Pi test and stress test are done. |
| Sun 06:00 | Code is frozen. Replay scans are saved. Demo has been rehearsed twice. |
| Sun 09:00 | Submitted. |

## 7. What to cut

Cut from the top of this list first:

1. Motor
2. Sponsor features other than the optional LLM
3. Optional LLM reader
4. Plan A stitching, if Plan B works
5. 1,000-sample live demo. Keep the measured stress-test result.
6. Live view polish

Never cut: real-label reading, confidence levels, images for review, clerk correction, CSV export, or the clerk-usable app.

## 8. Metrics for the results slide

Report these on real labels where possible:

- Attempted fields correct on first pass
- Attempted fields correct after retry
- Wrong values that passed without a flag
- Clerk minutes per 100 samples compared with manual entry
- Seconds per label on a workstation and on the Pi
- Cost per 100 samples
- Synthetic 1,000-sample throughput and failure count, labelled as synthetic

## 9. MLH sponsor plan

The MRG prize comes first. Do not start sponsor work before Checkpoint 2 (Sat 18:00). Read each prize's official rules before claiming it.

| Prize | Decision | Plan | Owner |
|---|---|---|---|
| Best Use of Gemini API | **Target** | Optional reader for uncertain field crops, measured in the reader comparison | Reader |
| DEV Writing Challenge ($100) | **Target** | Publish the project story after submission, using real results only | Demo and Hardware |
| Best Use of Tiger Data | Only if time allows | Optional sync of approved batch results. The local app must not depend on it. | App |
| Cursor and Grok Bot raffle | Team decision | Only if the team actually builds with both tools. Do not change the plan for it. | Team |
| Best Domain Name (GoDaddy Registry) | Only if time allows | Register a name only if the prize rules and cost make sense. The product stays local. | Demo and Hardware |
| Best Use of Vultr | Skip | Conflicts with the local-only approach | None |
| Best Use of Solana | Skip | No real use in this product | None |
| Best Use of Snowflake API | Skip | Overlaps with Gemini and adds a cloud dependency | None |

## 10. Open questions

- Are typed labels the third data type, and can MRG provide examples?
- Is `420 NDF` correct, or should it be `420 NPF`?
- Can MRG provide an image for sample `125719`?
