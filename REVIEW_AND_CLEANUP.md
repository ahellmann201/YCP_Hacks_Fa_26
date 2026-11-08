# Focused review and finishing a session

New review cards show fields needing attention beside their selected source crops. Other fields, the label-type selector, the combined label, and full original photos are expandable. All fields remain editable; there is no automatic confirmation. Crop lookup tries the saved selected field image, the preview's selected-photo reference, then the same field's crops from all photos in that analysis run. If no crop exists, the row displays every original photo from the tube with a numbered enlarge link, rather than assuming photo 1 contains that field. No extra OCR or processing is triggered by this fallback.

Review hints cover missing fields, conflicting photo readings, clipping warnings, and field OCR confidence below 0.95. Readings without recorded confidence also require checking. Dates and Small-label circled selections always require visual review. The cutoff is a conservative heuristic, not calibrated field accuracy; even high-confidence readings may be wrong. Sample IDs come from decoded barcodes. Confidence is collected during existing recognition calls, without another OCR pass. Older samples lacking these hints show all applicable photo fields for checking. Newly generated previews save their selected individual field crops as well as the combined image.

## Download and cleanup

**Download current CSV** remains a reusable interim export and does not delete files.

**Download CSV & finish session** fetches the CSV into browser memory, starts the browser download, then asks the Pi to clear the finished session's upload folders. The confirmation describes the deletion. The browser cannot verify that a user completed the final Save step; retain the downloaded CSV. On iPhone, check Files/Downloads or the browser's download list.

The finish action is blocked while uploads or review saves are pending, while any tube is queued/processing/failed, or while unreviewed tubes would be omitted from the CSV. To intentionally skip review, select **Include unreviewed samples in CSV** before finishing. The server compares the exported CSV's SHA-256 receipt with its current fields under the same database transaction that closes the session. If edits or new samples changed the export, it refuses cleanup and asks for a new download.

Cleanup removes only that session's UUID folders under `uploads/`, including original photos, OCR JSON snapshots, alignments, individual crops and combined previews. It does not remove other sessions' upload folders, models, training data, or external source ZIPs. UUID/path checks reject links and paths outside uploads. Finishing is idempotent so a failed connection can be retried. If file deletion fails, the session remains closed, metadata remains in SQLite, and cleanup can be retried.

SQLite field records, original field snapshots, metrics, and review metadata are retained so the CSV can still be generated again; photo evidence becomes unavailable after cleanup. The UI starts a new current session after successful cleanup. No cleanup runs merely from opening a CSV URL or fetching a preview.

Verification includes 18 unit tests across review, preview, cleanup, queue, ZIP import, thread settings and benchmark summaries, plus disposable API checks for ZIP upload, field-crop serving, stale export rejection, session-only deletion, retained CSV contents and cleanup retries. Browser script syntax checks passed. Physical iPhone download behavior still needs checking on the device.
