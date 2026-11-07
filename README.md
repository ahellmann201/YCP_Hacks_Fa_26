# Sample Scanner

A Raspberry Pi–hosted app for photographing sample tubes, reading labels offline, reviewing the results, and exporting a CSV.

## Quick start

Run these commands on the Pi:

```bash
cd ~/sample-scanner
.venv-ocr/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Leave that terminal running. Press **Ctrl+C** to stop the server.

### Open the website

Find the Pi’s current addresses:

```bash
hostname -I
```

On your phone, open:

```text
http://PI_IP_ADDRESS:8000
```

Use the address belonging to the network your phone can reach.

Previous addresses:

| Connection | Previous Pi address |
|---|---|
| Ethernet directly to Dell | `192.168.50.2` |
| iPhone hotspot | `172.20.10.2` |
| Event Wi-Fi | `10.64.136.62` |

These addresses can change. **Do not open `0.0.0.0` on the phone**—it is the server’s listening address.

Event Wi-Fi may prevent devices from reaching one another. The iPhone hotspot previously worked.

## Using the scanner

1. Photograph **one tube**.
2. Add more photos while rotating that same tube.
3. Tap **Upload and read automatically**.
4. Check the detected label type and suggested fields.
5. Correct missing or inaccurate values.
6. Tap **Confirm and save**.
7. Download the CSV or tap **Next tube**.

Limits: **8 photos per upload, 10 MB per photo**. Supported formats: JPG, PNG, and WebP.

On iPhone, if photos arrive as unsupported HEIC files, select:

**Settings → Camera → Formats → Most Compatible**

### Reviewing results

- Red outlines indicate missing, invalid, or conflicting fields.
- Date Sampled uses **`mm/dd/yyyy`**, for example `09/28/2026`.
- Date Received defaults to the phone’s date when uploading.
- Serial Number is converted to uppercase.
- Original photos remain available for comparison.
- Populated fields can still contain OCR mistakes. Review before saving.
- Short dates with two-digit years need confirmation and entry with a four-digit year.

## Label mapping and CSV columns

CSV columns appear in this order:

| Field | Large label | Small label |
|---|---|---|
| Sample ID | Code 128 barcode value | Code 128 barcode value |
| Date Sampled | Handwritten Date | Handwritten Date |
| Date Received | Upload date; editable | Upload date; editable |
| Machine | Equip ID | RN |
| Component | Sample Point | Circled number + GS/NGS, e.g. `4 GS` |
| Serial Number | Blank | SN, uppercase |
| Reference Lube | Ref Lube | Blank |

The **printed Sample ID** is separate from the app’s generated **record ID**.

Use the app record ID to reopen a saved upload.

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI server, uploads, saved records, CSV export |
| `scanner_auto.py` | Automatic label detection, alignment, field OCR, barcode and circle recognition |
| `static/index.html` | Phone interface, camera controls, review form |
| `ocr_worker.py` | Earlier OCR implementation; not used by the current automatic server |
| `test_barcode.py` | Standalone barcode test |
| `test_handwriting.py` | Standalone handwriting OCR test |
| `.venv-ocr/` | Current app and OCR Python environment |
| `uploads/` | Original photos, OCR results, and reviewed records |

### Saved sample structure

```text
uploads/
└── APP_RECORD_ID/
    ├── image_1.jpg
    ├── image_2.jpg
    ├── sample.json
    ├── ocr.json
    ├── review.json
    └── analysis/
        └── RUN_ID/
            ├── photo_1_aligned.jpg
            └── photo_1_date_sampled.jpg
```

- `sample.json`: upload details.
- `ocr.json`: detected type, suggested values, warnings.
- `review.json`: reviewed values used for CSV export.
- `analysis/`: generated alignment and field crops for troubleshooting.

Uploads, environments, and generated crops are excluded from Git. **Pushing code does not back up sample data.**

## Setup on the Pi

Current development hardware:

- Raspberry Pi 3 Model B
- 64-bit ARM (`aarch64`)
- Debian 13
- Approximately 1 GB RAM

Create the OCR environment if it does not already exist:

```bash
cd ~/sample-scanner
python3 -m venv .venv-ocr
```

Install dependencies:

```bash
.venv-ocr/bin/python -m pip install \
  fastapi uvicorn python-multipart Pillow \
  "rapidocr==3.10.0" \
  "onnxruntime==1.31.1" \
  "zxing-cpp==3.1.1"
```

The project was developed with PP-OCRv5 mobile models.

### Download OCR models before offline use

With internet available, run the standalone handwriting test on a real photo:

```bash
.venv-ocr/bin/python test_handwriting.py "uploads/RECORD_ID/image_1.jpg"
```

The test downloads the selected models if needed. It must use the **same `.venv-ocr` environment** as the server.

The automatic worker blocks network connections. If models are missing, it cannot download them during scanning.

### Check syntax

```bash
.venv-ocr/bin/python -m py_compile main.py scanner_auto.py
```

A successful syntax check does not verify recognition accuracy.

## Network commands

### Current connections

```bash
nmcli -f NAME,DEVICE connection show --active
hostname -I
```

### Scan Wi-Fi

```bash
sudo nmcli device wifi rescan ifname wlan0
nmcli -f SSID,SIGNAL device wifi list ifname wlan0
```

### Connect to Wi-Fi or a hotspot

Use the exact name shown by the scan:

```bash
sudo nmcli --ask device wifi connect "NETWORK NAME"
```

Enter the password when prompted.

The hotspot previously appeared as:

```text
Andrew’s iPhone
```

The curly apostrophe matters when entering the name.

On iPhone:

1. Enable **Personal Hotspot → Allow Others to Join**.
2. Enable **Maximize Compatibility**, if available.
3. Keep the Personal Hotspot screen open while connecting.
4. Run `hostname -I` on the Pi after connecting.

Keep Ethernet connected to the Dell while developing through VS Code Remote SSH.

## Troubleshooting

### Website does not load on the phone

Check the server locally from a second Pi terminal:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
```

Expected result:

```text
200
```

Then check:

- The server terminal is still running.
- The phone URL uses `http://`, not `https://`.
- The Pi’s IP address has not changed.
- The phone has a network path to the Pi.
- Event Wi-Fi is not isolating devices.

`curl -I` sends a HEAD request and may return `405 Method Not Allowed`. Use the GET check above.

### HTML changes do not appear

Save `static/index.html`, then refresh Safari.

Try a fresh URL:

```text
http://PI_IP_ADDRESS:8000/?v=7
```

Changing the query value helps request a fresh page.

### Which changes require a restart?

| Changed file | Action |
|---|---|
| `main.py` | Stop and restart Uvicorn |
| `scanner_auto.py` | Save, then use Read photos again |
| `static/index.html` | Save and refresh the browser |

### OCR returns incorrect characters

Check the original photo:

- Is the label close enough and sharp?
- Is glare covering handwriting?
- Are the relevant fields facing the camera?
- Is the entire barcode visible?
- Is the label severely curved or partly hidden?

The scanner cannot recover handwriting missing from the photo.

### Date remains blank

The model may lose slashes or confuse connected digits.

For example, the date `9/28/26` was read as `92866` and `e912866`.

The app deliberately rejects these rather than inventing a date. Enter the correct value as:

```text
09/28/2026
```

### Field crops are misplaced

Automatic alignment uses the barcode and two calibrated reference templates.

Inspect the generated images under:

```text
uploads/RECORD_ID/analysis/
```

Template coordinates are defined in `TEMPLATES` near the top of `scanner_auto.py`.

A successful test on a flat label does not establish accuracy on curved tube photos.

### Reading is slow

The Pi processes one OCR request at a time. Avoid running standalone OCR tests while the server is reading.

Observed development measurements:

- One earlier full-photo test: about 32 seconds and 165 MiB peak process memory.
- One flat reference test: about 13 seconds for OCR and mapping.
- Three isolated field crops: about 3.3 seconds total, excluding alignment and barcode detection.

These are individual measurements, not guaranteed end-to-end scan times.

## Standalone tests

### Barcode

```bash
.venv-ocr/bin/python test_barcode.py "uploads/RECORD_ID/image_1.jpg"
```

Known reference image:

```bash
.venv-ocr/bin/python test_barcode.py \
  "/home/hacks/sample-scanner/uploads/497e292ce08e4b5f91c7f8ecc1ffa494.jpg"
```

Expected reference result:

```text
Decoded value: 111329
Barcode format: Code 128
```

### Handwriting

```bash
.venv-ocr/bin/python test_handwriting.py \
  "/home/hacks/sample-scanner/uploads/497e292ce08e4b5f91c7f8ecc1ffa494.jpg"
```

Handwriting test output is raw text; it does not validate all saved fields.

## Git and GitHub

Repository:

https://github.com/ahellmann201/YCP_Hacks_Fa_26

Development branch:

```text
Andrew
```

### Check repository status

```bash
cd ~/sample-scanner
git status
git branch --show-current
git remote -v
```

### Configure commit identity

Replace the placeholders before running:

```bash
git config user.name "YOUR NAME"
git config user.email "YOUR GITHUB EMAIL"
```

Use an email associated with GitHub or your GitHub noreply address. These settings do not sign you into GitHub.

### Commit and push current app changes

```bash
git add main.py scanner_auto.py static/index.html README.md .gitignore
git diff --cached --stat
git commit -m "Update sample scanner"
git push origin Andrew
git status
```

Check the staged files before committing. Do not include sample photos, environments, credentials, or generated crops.

A commit remains local until the push succeeds.

### VS Code Remote SSH folder

Open this folder on the Pi:

```text
/home/hacks/sample-scanner
```

Source Control should show repository **sample-scanner** and branch **Andrew**.

## Current limitations

- Automatic alignment and circle detection are prototype heuristics.
- Barcode position and printed headings help identify and align the label.
- Severe curvature cannot be flattened reliably by the current perspective transform.
- Handwriting can be confidently misread.
- Red borders identify detectable problems; they cannot catch every wrong value.
- Dates still require manual correction when recognition fails.
- Windows deployment has not yet been validated. Pi environment folders cannot be copied to Windows; dependencies must be installed separately.
- The app is a local-network prototype without authentication or HTTPS.