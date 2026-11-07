import json
import os
import re
import socket
import sys
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"


# Recognition must not contact outside services or download models.
# Run the earlier test_handwriting.py once to download models first.
def block_network(*args, **kwargs):
    raise OSError("Network disabled in offline OCR worker.")


socket.socket.connect = block_network
socket.socket.connect_ex = block_network
socket.create_connection = block_network


FIELD_NAMES = [
    "sample_id",
    "date_sampled",
    "machine",
    "component",
    "serial_number",
    "reference_lube",
]


def group_lines(result):
    """Combine text boxes that occupy approximately the same row."""
    if result.txts is None:
        return []

    items = []

    for text, score, box in zip(
        result.txts,
        result.scores,
        result.boxes,
    ):
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]

        items.append({
            "text": str(text),
            "score": float(score),
            "x": min(xs),
            "y": (min(ys) + max(ys)) / 2,
            "height": max(ys) - min(ys),
        })

    rows = []

    for item in sorted(items, key=lambda value: value["y"]):
        matching = None

        for row in rows:
            tolerance = max(item["height"], row["height"]) * 0.5

            if abs(item["y"] - row["y"]) <= tolerance:
                matching = row
                break

        if matching is None:
            rows.append({
                "y": item["y"],
                "height": item["height"],
                "items": [item],
            })
        else:
            matching["items"].append(item)

    return [
        " ".join(
            item["text"]
            for item in sorted(row["items"], key=lambda value: value["x"])
        )
        for row in rows
    ]


def extract_candidates(lines, label_type):
    candidates = {name: [] for name in FIELD_NAMES}

    if label_type == "large":
        anchors = [
            ("machine", r"\bequip(?:ment)?\s*(?:id)?\b"),
            ("component", r"\bsample\s*point\b"),
            ("reference_lube", r"\bref(?:erence)?\s*lube\b"),
            ("date_sampled", r"\bdate\b"),
        ]
    else:
        anchors = [
            ("machine", r"\bRN\b"),
            ("serial_number", r"\bSN\b"),
            ("date_sampled", r"\bdate"),
        ]

    combined = re.compile(
        "|".join(
            f"(?P<{name}>{pattern})"
            for name, pattern in anchors
        ),
        re.IGNORECASE,
    )

    for line in lines:
        matches = list(combined.finditer(line))

        for index, match in enumerate(matches):
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(line)
            )

            value = line[match.end():end].strip(" \t:;._-")
            field = match.lastgroup

            if not value:
                continue

            if field == "date_sampled":
                # Preserve the written date; don't invent separators
                # or decide whether an ambiguous date is day/month.
                found = re.search(
                    r"\b\d{1,2}\s*[/.-]\s*\d{1,2}"
                    r"\s*[/.-]\s*\d{2,4}\b",
                    value,
                )

                if not found:
                    continue

                value = re.sub(r"\s+", "", found.group())

            candidates[field].append(value)

        # Read the printed number, not the barcode itself.
        # A whole standalone numeric box is a possible label ID.
        for value in re.findall(r"(?<!\w)\d{4,12}(?!\w)", line):
            if matches:
                continue

            if value in {"1234", "12345", "123456"}:
                continue

            candidates["sample_id"].append(value)

    # Circled selections are confirmed by the operator.
    if label_type == "small":
        candidates["component"] = []
        candidates["reference_lube"] = []
    else:
        candidates["serial_number"] = []

    return candidates


def recognize(job):
    from PIL import Image, ImageOps
    from rapidocr import RapidOCR, ModelType, OCRVersion

    engine = RapidOCR(
        params={
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.model_type": ModelType.MOBILE,
            "Det.limit_side_len": 640,
            "Det.limit_type": "max",
            "Rec.rec_batch_num": 1,
            "Cls.cls_batch_num": 1,
            "EngineConfig.onnxruntime.intra_op_num_threads": 1,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
        }
    )

    all_candidates = {name: [] for name in FIELD_NAMES}
    images = []

    for image_path in job["images"]:
        path = Path(image_path)
        image_result = {
            "filename": path.name,
            "lines": [],
            "error": None,
        }

        try:
            with Image.open(path) as original:
                if original.width * original.height > 20_000_000:
                    raise ValueError("Photo exceeds 20 megapixels.")

                original.draft("RGB", (1200, 1200))
                photo = ImageOps.exif_transpose(original).convert("RGB")
                photo.thumbnail((1200, 1200))

            result = engine(photo)
            photo.close()

            lines = group_lines(result)
            image_result["lines"] = lines

            # Also retain separate boxes for standalone printed numbers.
            separate = (
                [str(text) for text in result.txts]
                if result.txts is not None
                else []
            )

            candidates = extract_candidates(lines, job["label_type"])
            numeric_candidates = extract_candidates(
                separate,
                job["label_type"],
            )

            candidates["sample_id"].extend(
                numeric_candidates["sample_id"]
            )

            for name in FIELD_NAMES:
                all_candidates[name].extend(candidates[name])

        except Exception as error:
            image_result["error"] = str(error)[:250]

        images.append(image_result)

    suggestions = {}
    alternatives = {}

    for name, values in all_candidates.items():
        unique = {}

        for value in values:
            cleaned = re.sub(r"\s+", " ", value).strip()
            key = cleaned.casefold()

            if key and key not in unique:
                unique[key] = cleaned

        choices = list(unique.values())
        alternatives[name] = choices

        # Conflicting photos must not silently overwrite one another.
        suggestions[name] = choices[0] if len(choices) == 1 else ""

    return {
        "label_type": job["label_type"],
        "images": images,
        "suggestions": suggestions,
        "alternatives": alternatives,
    }


if __name__ == "__main__":
    output_path = Path(sys.argv[2])

    try:
        job = json.loads(
            Path(sys.argv[1]).read_text(encoding="utf-8")
        )
        output = recognize(job)

    except Exception as error:
        output = {
            "error":
                "Offline OCR could not initialize. Run the earlier "
                "test_handwriting.py in this same environment to make "
                "sure its models are downloaded. Details: "
                + str(error)[:250]
        }

    output_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )