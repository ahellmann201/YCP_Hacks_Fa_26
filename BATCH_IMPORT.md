# Upload folders of tube photos

Create a ZIP containing one folder per tube, optionally inside a common parent folder:

```text
sample_images/
  tube_001/
    photo1.jpg
    photo2.jpg
  tube_002/
    photo1.jpg
```

In Windows File Explorer, right-click the parent folder and choose **Compress to ZIP file** (or **Send to → Compressed (zipped) folder**). On the scanner page, select **Upload samples** and choose the archive. The same button accepts ordinary photos for one tube. Select one ZIP by itself or 1–8 photos; mixing ZIPs and loose photos is rejected. Each folder containing photos becomes one tube, grouped by its full folder path. Put all photos for a tube directly in that tube folder; images in deeper subfolders are treated as separate groups. Photos at the ZIP root are rejected to avoid guessing tube membership.

The server checks the archive and prepares all tube records before adding them to the current session in one queue transaction. Each tube gets its own review card, timing and CSV row. Photos are processed sequentially on the Pi while the page continues polling. The original folder name appears on the review card. Source filenames are metadata, never extraction destinations. A failed connection after submission may still leave the batch queued: check the queue before resubmitting.

Limits: 100 tubes, 1–8 photos per tube, 250 MiB compressed ZIP, 512 MiB total uncompressed photos, 10 MiB per source photo, and 20 megapixels per photo. Non-photo notes, hidden files and macOS metadata are ignored. Unsupported common photo formats, unsafe paths, links, encrypted files, invalid images, and duplicate photo paths are rejected. Archive paths are not extracted onto the filesystem.

JPG, PNG and WebP use the app's existing Pillow support. HEIC/HEIF import requires the optional Pillow HEIF reader in the Pi environment:

```bash
.venv-ocr/bin/python -m pip install pillow-heif
```

Install it once with internet available, then restart the server. Import itself is offline. HEIC images are converted one at a time to orientation-corrected JPEGs; the originals in your ZIP are unchanged. If the reader is missing, the batch is rejected before any tubes are queued. JPEG batches do not need this dependency. HEIC decoding has not been verified on this particular Pi yet.

New imported samples follow the same review, accuracy and current-session CSV rules as ordinary uploads. Processing times exclude archive upload and preparation/conversion, so they are not a measure of total ZIP import turnaround. Inspect wall-clock batch time separately if that matters to your throughput requirement.
