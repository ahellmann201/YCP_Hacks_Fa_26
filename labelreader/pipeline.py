"""Read a folder of label images into a CSV, field crops and a review list."""
from __future__ import annotations

import csv
import difflib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import cv2

from .choices import read_choice
from .handwriting import Reader, clean_variant, is_blank, trim
from .normalize import normalize
from .register import RegistrationError, Registered, load_templates, register

COLUMNS = ["Sample ID", "Date Sampled", "Date Received", "Machine", "Component", "Serial Number", "Refrence Lube"]
REVIEW_BELOW = 0.80
IMAGE_TYPES = {".jpg", ".jpeg", ".png"}


@dataclass
class Field:
    column: str
    value: str
    confidence: float
    crop: str = ""
    note: str = ""


def _read_field(label: Registered, name: str, spec: dict, reader: Reader, today: date, crop_path: Path) -> Field:
    crop = label.crop(spec["box"], spec["caption"])
    cv2.imwrite(str(crop_path), crop)
    caption_score = label.captions[spec["caption"]].score
    if is_blank(crop):
        return Field(spec["column"], "", round(min(0.95, caption_score), 3), crop_path.name, "blank")

    # Two views of the same ink. Agreement is the main evidence of a good read.
    trimmed = trim(crop)
    first, second = reader.read(trimmed), reader.read(clean_variant(trimmed))
    a, b = normalize(first.text, spec, today), normalize(second.text, spec, today)
    agreement = difflib.SequenceMatcher(None, a.value.lower(), b.value.lower()).ratio()
    best = a if (a.valid or not b.valid) else b

    confidence = 0.55 * agreement + 0.30 * first.probability + 0.15 * caption_score
    if not best.valid:
        confidence = min(confidence, 0.4)
    notes = [n for n in (best.note, "" if best.valid else "failed format check") if n]
    return Field(spec["column"], best.value, round(confidence, 3), crop_path.name, "; ".join(notes))


def process_image(path: Path, templates: list[dict], reader: Reader, today: date, out: Path) -> dict:
    label = register(cv2.imread(str(path)), templates)
    template = label.template
    sample_dir = out / "samples" / label.sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(sample_dir / "label.jpg"), label.image)

    fields = [Field("Sample ID", label.sample_id, 0.99, "label.jpg", "from barcode"),
              Field("Date Received", today.strftime("%-m/%-d/%Y"), 1.0, note="today")]
    for name, spec in template["fields"].items():
        fields.append(_read_field(label, name, spec, reader, today, sample_dir / f"{name}.jpg"))
    if template["choices"]:
        picks = {name: read_choice(label, name) for name in template["choices"]}
        value = template["component"].format(**{k: v.value for k, v in picks.items()}).strip()
        confidence = min(min(1.0, p.confidence / 0.5) for p in picks.values())
        fields.append(Field("Component", value, round(confidence, 3), "label.jpg", "from circled options"))
    return {"image": path.name, "template": template["name"], "sample_id": label.sample_id,
            "fields": [asdict(f) for f in fields]}


def write_csv(results: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:  # BOM, as the template has
        writer = csv.DictWriter(handle, COLUMNS)
        writer.writeheader()
        for result in results:
            row = {f["column"]: f["value"] for f in result.get("fields", [])}
            writer.writerow({c: row.get(c, "") for c in COLUMNS})


def run_batch(folder: Path, out: Path, name: str, reader: Reader, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out.mkdir(parents=True, exist_ok=True)
    templates = load_templates()
    results_path = out / "results.jsonl"
    done = {}
    if results_path.exists():  # resume: a crash loses nothing already read
        for line in results_path.read_text().splitlines():
            record = json.loads(line)
            done[record["image"]] = record
    with results_path.open("a") as log:
        for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES):
            if path.name in done:
                continue
            try:
                record = process_image(path, templates, reader, today, out)
            except RegistrationError as error:
                record = {"image": path.name, "error": str(error), "fields": []}
            done[path.name] = record
            log.write(json.dumps(record) + "\n")
            log.flush()
    results = list(done.values())
    write_csv([r for r in results if "error" not in r], out / f"{name}.csv")
    return results
