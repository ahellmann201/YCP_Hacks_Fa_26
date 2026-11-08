# Offline Sample Scanner

Photograph tube labels, group images by tube, read them on the Pi, correct fields beside their crops, and export one CSV per session. Scanning is offline after initial model preparation. Current demo updates are on **`training`**. The usual demo machine is the Pi. The same server can run from the Dell checkout: [Run on the Dell](#run-on-the-dell).

## Quick demo: Pi already running

In the Pi terminal (SSH or VS Code Remote SSH):

```bash
cd ~/sample-scanner
bash scripts/start_demo.sh
```

This starts the app with **three OCR threads** and prints its addresses. Keep the terminal open. The equivalent direct command is:

```bash
SCANNER_OCR_THREADS=3 .venv-ocr/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

1. **Open the page:** visit `http://PI_ADDRESS:8000` from the phone/Dell. Use `hostname -I` to find current addresses. The hotspot previously assigned `172.20.10.2`; configured direct Dell Ethernet uses `192.168.50.2`. Use a network the viewing device can reach. **Do not browse to `0.0.0.0`.**
2. **Choose a session:** the page starts a new session. Uploaded photos are deleted each time the server starts, so download a CSV before stopping if you still need the pictures. Field text already saved in SQLite stays in the database.
3. **Upload samples:** select 1–8 JPG/PNG/WebP photos of **one tube**, or **one ZIP** containing a folder per tube. For a short demo, use 3–5 clear tubes; use 10–20 for a longer batch. Do not mix ZIPs and loose photos.
4. **Review as results arrive:** ready cards appear above the processing list. Flagged fields have matching crops; other fields and all originals are expandable. Correct OCR values and select **All good — include in CSV**. Confirmed cards disappear. Populated/high-confidence fields can still be wrong.
5. **Show the top metrics:** average processing seconds per tube excludes transfer, queue wait and manual review. Field accuracy is **correct fields / applicable fields × 100**, comparing original readings with confirmed corrections, not model confidence. Date Received and unused fields do not count.
6. **Export:** **Download current CSV** keeps photos for continued work. **Download CSV & finish session** receives the CSV in the browser, starts its download and clears that session's photos/crops. Keep the downloaded file. To intentionally skip review, select **Include unreviewed samples in CSV**. Pending/failed tubes must be resolved before finishing. CSV field records remain in SQLite.
7. **Stop:** press **Ctrl+C** in the server terminal. Closing the page does not delete photos. Starting the server again empties `uploads/`. To power the Pi off afterwards, run `sudo poweroff` and let shutdown complete before removing power.

ZIP structure:

```text
samples.zip
└── samples/
    ├── tube_001/
    │   ├── front.jpg
    │   └── rotated.jpg
    └── tube_002/
        └── label.jpg
```

Limits: **100 tubes per ZIP**, **250 MiB archive**, **512 MiB uncompressed photos**, **8 photos per tube**, **10 MiB and 20 megapixels per photo**. HEIC/HEIF works inside ZIPs when the optional reader is installed. [ZIP guide](docs/BATCH_IMPORT.md) · [Review and cleanup](docs/REVIEW_AND_CLEANUP.md) · [Metrics](docs/SESSION_METRICS.md).

## Run on the Dell

Use this when the demo should run on the laptop instead of the Pi. It is the same site and the same OCR. The laptop keeps its own `uploads/` folder and `scanner.sqlite3`, so Pi sessions do not appear here, and starting this server does not clear the Pi. `scripts/start_demo.sh` is the Pi launcher; on Windows use the commands below. Do not copy this Windows `.venv-ocr` onto the Pi.

Page behavior matches the Pi demo above: one tube or one ZIP, review, CSV, and **Ctrl+C** to stop. Starting the server empties this checkout’s `uploads/`. Download a CSV first if those photos are still needed. The RTX 3060 is for training. This server reads labels on the CPU.

**First time only**, in PowerShell, from the checkout. This Dell’s `py -3` is Python 3.14, and the pinned requirements have Windows wheels for it.

```powershell
cd C:\Hackathons\YCP_Hack_Fa_26\YCP_Hacks_Fa_26
py -3 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements.txt -r requirements-heic.txt
.\.venv-ocr\Scripts\python.exe tools\prepare_models.py
.\.venv-ocr\Scripts\python.exe tools\prepare_models.py --check
```

`prepare_models.py` needs internet once so RapidOCR can cache its models. `--check` then confirms those models plus the included English recognizer with networking blocked. The scan itself stays offline after that.

**Each later start:**

```powershell
cd C:\Hackathons\YCP_Hack_Fa_26\YCP_Hacks_Fa_26
$env:SCANNER_OCR_THREADS = "3"
.\.venv-ocr\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Keep that window open.

1. **On the laptop:** open `http://127.0.0.1:8000`. Do not browse to `0.0.0.0`.
2. **On the phone:** the phone has to reach the laptop. Run `ipconfig` and use the laptop address on the network the phone is actually joined to, for example `http://192.168.50.1:8000` only when the phone is on that same Ethernet link. Campus Wi-Fi cannot see the direct Dell–Pi address `192.168.50.1`. A phone hotspot works when the laptop is connected to that hotspot. **Take photo** uses the phone camera against whichever address opened the page.
3. **Stop:** **Ctrl+C** in the PowerShell window. Closing the browser does not delete photos. The next start does.

## Cold start: the Pi was powered off

This is a normal restart, **not a reinstall**. Keep the existing environment and model cache.

1. Connect Pi power and Ethernet to the Dell if using Remote SSH. Allow it to boot.
2. Enable the iPhone's **Personal Hotspot → Allow Others to Join**; **Maximize Compatibility** can help discovery. Keep the hotspot screen open during connection.
3. On the Dell, reconnect VS Code Remote SSH to `/home/hacks/sample-scanner`, or use:

   ```powershell
   ssh hacks@192.168.50.2
   ```

   This address requires the existing direct-Ethernet setup. If it fails, use the Pi's display/keyboard to inspect networking.

4. In the Pi terminal, check addresses and Wi-Fi:

   ```bash
   nmcli device status
   hostname -I
   ```

   If Wi-Fi is disconnected:

   ```bash
   sudo nmcli device wifi rescan ifname wlan0
   nmcli -f SSID,SIGNAL device wifi list ifname wlan0
   sudo nmcli --ask device wifi connect "EXACT HOTSPOT NAME" ifname wlan0
   hostname -I
   ```

   Use the exact scanned SSID. It has appeared as `AndrewsiPhone` and previously with an apostrophe. Event Wi-Fi may isolate devices. Internet is needed for installation/updates, not a prepared offline scan.

5. Run `cd ~/sample-scanner`, then `bash scripts/start_demo.sh`. Open the hotspot-side Pi address on the phone and choose resume/new.

### Direct Ethernet recovery

The development link uses **Dell Ethernet `192.168.50.1/24`** and **Pi Ethernet `192.168.50.2/24`**, without a gateway/DNS on that direct link; Wi-Fi provides internet. These are configured addresses, not fresh-install defaults.

Check the Dell's physical Ethernet adapter IPv4 settings. On the Pi's local display, inspect `nmcli connection show`. If the actual Ethernet profile is named `netplan-eth0`, restore the previous configuration with:

```bash
sudo nmcli connection modify "netplan-eth0" ipv4.method manual ipv4.addresses "192.168.50.2/24" ipv4.never-default yes
sudo nmcli connection up "netplan-eth0"
```

Substitute the real profile name if different. Changing it can disconnect SSH, so use the Pi's local terminal for recovery. Then retry SSH from the Dell.

## Fresh installation from scratch

The demo Pi is a **Pi 3 Model B, 64-bit Debian 13/aarch64, approximately 1 GB RAM**. GPU training is separate and runs on Windows; the Pi needs inference dependencies only.

**1. Prepare the OS and network.** Boot a 64-bit Pi-compatible OS, create a login, enable SSH if needed and connect to a network reachable from the demo device. A fresh login may differ from `hacks`.

**2. Install the app with internet available:**

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip libgomp1
git clone --branch training https://github.com/ahellmann201/YCP_Hacks_Fa_26.git ~/sample-scanner
cd ~/sample-scanner
python3 -m venv .venv-ocr
.venv-ocr/bin/python -m pip install --upgrade pip
.venv-ocr/bin/python -m pip install -r requirements.txt
```

For HEIC/HEIF ZIP photos, additionally run:

```bash
.venv-ocr/bin/python -m pip install -r requirements-heic.txt
```

Wheels must match the OS/Python architecture. OCR runtime versions reflect this project's tested environment; a different fresh OS is not automatically validated. Do not copy a Windows virtual environment onto the Pi.

**3. Prepare models once in the same environment as the server:**

```bash
.venv-ocr/bin/python tools/prepare_models.py
.venv-ocr/bin/python tools/prepare_models.py --check
```

The first command can download the selected RapidOCR PP-OCRv5 mobile models. The second blocks networking and checks those cached models plus the included English candidate. The app worker blocks network access and cannot download missing models while scanning. Included recognizers are under `trained-model/`.

**4. Check and launch:**

```bash
.venv-ocr/bin/python -m py_compile main.py scanner_auto.py background_scanner.py
bash scripts/start_demo.sh
```

Before presenting, upload one Small and one Large label, inspect crops/originals, correct fields and open the CSV. Test HEIC import on the actual Pi if your ZIP uses it. Syntax/model loading checks do not prove recognition accuracy.

## Updating an existing checkout

Current updates are in **`training`**. `Andrew` is the earlier branch and may still appear on a Pi that received individual file updates.

```bash
cd ~/sample-scanner
git status
git branch --show-current
git fetch origin
```

For a **clean checkout already on `training`**, stop the server, run `git pull --ff-only`, then `bash scripts/start_demo.sh`. If there are local edits or individually restored files, save/commit those before switching branches or pulling. Do not hard-reset or delete `uploads/`/`scanner.sqlite3` as an update step. Pushing source code does not back up sample data.

To synchronize an older mixed Pi checkout in place, stop its server and follow [the backed-up Pi sync procedure](docs/PI_CLEAN_CHECKOUT.md#sync-the-current-pi-folder-in-place). This aligns source to `origin/training`; it does not replay old application changes with a Git rebase.

If VS Code still shows the old root files and many `M`/`A`/`U` markers, use the [clean Pi checkout guide](docs/PI_CLEAN_CHECKOUT.md). It creates `~/sample-scanner-demo` on `training` and links the existing environment and data, preserving the old working tree. Use that folder instead in the demo commands.

## Demo troubleshooting

| Symptom | Action |
|---|---|
| Phone cannot open the page | Keep the server terminal open. Use `http://` and the current reachable Pi IP; check hotspot connectivity. On the Dell, use the laptop address from [Run on the Dell](#run-on-the-dell), not `192.168.50.2`. |
| SSH times out | Check Ethernet link and the `.50.1`/`.50.2` adapter settings above; use the Pi display for recovery. |
| GitHub hostname cannot resolve | Reconnect Pi Wi-Fi/default route or DNS. Prepared OCR does not need GitHub. |
| Old controls remain | Refresh/reopen the page after HTML updates. Restart after Python updates. |
| Missing model / OCR worker stops | Run `tools/prepare_models.py --check`; prepare online if needed. Check memory with `free -h`. |
| Wrong crops or text | Check the crop and all originals. Updated crop code needs new processing; it does not regenerate old crops. |
| HEIC import fails | Install `requirements-heic.txt`, restart and retry. Validation failures queue none of the batch. |
| Photos gone after a restart | Startup empties `uploads/`. Download the CSV before stopping the server if those photos are still needed. |

Local page check from a second Pi terminal:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
```

Expected: `200`. `curl -I` sends HEAD and may return `405` even when the page works.

## Performance and limits

The user-run three-thread Pi benchmark tested **10 tubes twice each**: **20.8s average/tube**, **27.4s slowest tube mean**, **10/10 below 30s mean**, and **329.5 MiB peak OCR worker memory**. Repeated readings matched. It measured saved-photo OCR and preview generation, excluding upload, ZIP preparation, queue wait, manual review and whole-app memory. Later crop/quality updates have not been rebenchmarked over that set.

Three threads help **one worker**; tubes are still processed sequentially and models reload per tube. Matching repeated outputs do not prove accuracy. Cursive, smears, glare, clipping and curvature still need review. The smudge-augmented English model handles Small-label machine/serial crops; other paths retain RapidOCR. Small development comparisons improved from 5/9 to 6/9 clean fields and from 13/27 to 18/27 synthetic-smudge fields; these are not general accuracy estimates. [Smudge experiment and limits](tube-training/SMUDGE_TRAINING.md). [Thread guide](docs/OCR_THREADS.md) · [Model comparison](tube-training/MODEL_COMPARISON.md).

Valid full dates accept `.`, `-` or `/` and display/export as **MM/DD/YYYY**. Two-digit full-date years use 20xx. Partial dates keep their components with `/` separators; no missing day/year is invented. Raw OCR remains saved. Formatting does not repair wrong digits. Machine and serial punctuation are untouched. Date accuracy treats equivalent separators/formatting as equal.

## CSV mapping

| Column | Large label | Small label |
|---|---|---|
| Sample ID | Decoded barcode | Decoded barcode |
| Date Sampled | Written Date | Written Date |
| Date Received | Upload date; editable | Upload date; editable |
| Machine | Equip ID | RN |
| Component | Sample Point | Circled number + GS/NGS |
| Serial Number | Blank | SN, uppercase |
| Reference Lube | Ref Lube | Blank |

## File layout and developer checks

| Location | Purpose |
|---|---|
| `main.py`, `static/` | FastAPI entry point, MRG logo, and phone/browser interface |
| `scanner/queue/` | Background scan queue |
| `scanner/io/` | Sessions, upload cleanup, and ZIP intake |
| `scanner/vision/` | Label alignment, crops, and circled component marks |
| `scanner/reading/` | OCR settings, field text, and the photo-reading pipeline |
| `scripts/start_demo.sh` | Demo launcher; defaults to three OCR threads |
| `tools/` | Model preparation, barcode/handwriting diagnostics, throughput benchmark |
| `tests/` | App regression tests with disposable data |
| `docs/` | ZIP, metrics, review/cleanup and thread guides |
| `tube-training/` | Separate labeling, Windows training/conversion tools and their tests |
| `trained-model/` | Offline models, dictionaries and provenance |
| `legacy/` | Earlier unused OCR worker |
| `uploads/`, `scanner.sqlite3` | Local photo/crop files and session/field records; ignored by Git. `uploads/` is emptied when the server starts. |

Run from the repository root:

```bash
.venv-ocr/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv-ocr/bin/python tools/benchmark_threads.py --samples 10 --thread-counts 3 --repeats 2
.venv-ocr/bin/python tools/test_barcode.py "PATH/TO/PHOTO.jpg"
.venv-ocr/bin/python tools/test_handwriting.py "PATH/TO/PHOTO.jpg"
```

Stop the app for comparable benchmark measurements. The full-tube benchmark and old handwriting timing tool use Linux resource measurements. Core logic has local Windows tests, but the complete Windows camera/demo workflow has not been validated. See [training setup](tube-training/README.md) for the separate GPU environment; do not install training dependencies on the Pi for inference.
