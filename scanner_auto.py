import json
import os
import re
import socket
import sys
from datetime import datetime
from pathlib import Path
from ocr_settings import ocr_threads, rapidocr_parameters
from field_text import strip_heading, visually_empty
from reading_quality import crop_quality
from sample_dates import extract_written_date

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"


def no_network(*args, **kwargs):
    raise OSError(
        "Offline mode: models must already be downloaded."
    )


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network


FIELDS = [
    "sample_id",
    "date_sampled",
    "machine",
    "component",
    "serial_number",
    "reference_lube",
]


TEMPLATES = {
    "small": {
        "size": (1200, 680),
        "barcode": (0.18, 0.02, 0.79, 0.25),
        "fields": {
            "machine": (0.26, 0.36, 0.59, 0.57),
            "date_sampled": (0.74, 0.33, 1.10, 0.60),
            "serial_number": (0.16, 0.59, 0.77, 0.84),
        },
    },
    "large": {
        "layout": "large",
        "size": (1200, 330),
        "barcode": (0.47, 0.65, 0.85, 0.91),
        "fields": {
            "machine": (0.17, 0.01, 0.73, 0.20),
            "component": (0.24, 0.20, 0.76, 0.41),
            "reference_lube": (0.18, 0.40, 0.79, 0.63),
            "date_sampled": (0.10, 0.65, 0.46, 0.89),
        },
    },
}


def clean(value):
    return re.sub(r"\s+", " ", value).strip(" \t:;_-")


def identify_type(text):
    small = 0
    large = 0

    if re.search(r"\bRN\b", text, re.I):
        small += 2

    if re.search(r"\bSN\b", text, re.I):
        small += 2

    if re.search(r"\bNGS\b", text, re.I):
        small += 1

    if re.search(r"\bGS\b", text, re.I):
        small += 1

    if re.search(r"\bequip", text, re.I):
        large += 2

    if re.search(r"\bsample\s*point", text, re.I):
        large += 2

    if re.search(r"\bref(?:erence)?\s*lube", text, re.I):
        large += 2

    if small >= 2 and large == 0:
        return "small"

    if large >= 2 and small == 0:
        return "large"

    return "unknown"


def valid_written_date(text):
    return extract_written_date(text)


def read_text(engine, image, line=False, confidence=None):
    result = engine(
        image,
        use_det=not line,
        use_cls=not line,
        use_rec=True,
    )

    if confidence is not None:
        scores = getattr(result, 'scores', None)
        if scores is not None:
            confidence.extend(float(score) for score in scores)
    if result.txts is None:
        return []

    return [
        value
        for value in (
            clean(str(text))
            for text in result.txts
        )
        if value
    ]


def raw_values(text, label_type):
    values = {key: "" for key in FIELDS}

    if label_type == "small":
        patterns = {
            "machine":
                r"\bRN\s*:?\s*(.*?)(?=\bDate|\bSN\b|$)",

            "serial_number":
                r"\bSN\s*:?\s*(.*?)(?=\bDate|$)",
        }

    else:
        patterns = {
            "machine":
                r"\bEquip(?:ment)?\s*(?:ID)?\s*:?\s*(.*?)"
                r"(?=\bSample\s*point|\bRef|\bDate|$)",

            "component":
                r"\bSample\s*point\s*:?\s*(.*?)"
                r"(?=\bRef|\bDate|$)",

            "reference_lube":
                r"\bRef(?:erence)?\s*lube\s*:?\s*(.*?)"
                r"(?=\bDate|$)",
        }

    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.I)

        if match:
            values[name] = strip_heading(clean(match.group(1)),name,label_type)

    match = re.search(
        r"\bDate\s*:?\s*(.*)",
        text,
        re.I,
    )

    if match:
        values["date_sampled"] = valid_written_date(
            match.group(1)
        )

    return values


def align_to_template(image, barcode, template, metadata=None):
    import cv2
    import numpy as np

    template_width, height = template["size"]
    left, top, right, bottom = template["barcode"]

    # Extend the canvas without moving the original template coordinates.
    canvas_width = round(template_width * 1.12)

    position = barcode.position

    source = np.float32([
        [position.top_left.x, position.top_left.y],
        [position.top_right.x, position.top_right.y],
        [position.bottom_right.x, position.bottom_right.y],
        [position.bottom_left.x, position.bottom_left.y],
    ])

    destination = np.float32([
        [left * template_width, top * height],
        [right * template_width, top * height],
        [right * template_width, bottom * height],
        [left * template_width, bottom * height],
    ])

    if abs(cv2.contourArea(source)) < 40:
        raise ValueError(
            "Barcode is too small for alignment."
        )

    transform = cv2.getPerspectiveTransform(
        source,
        destination,
    )
    method = 'barcode'
    if template.get('layout') == 'large':
        from label_alignment import tight_large_transform
        framed = tight_large_transform(image, barcode, template)
        if framed is not None:
            transform = framed
            method = 'tight_large_label'
    if metadata is not None:
        metadata['alignment_method'] = method
        corners = cv2.perspectiveTransform(source.reshape(1,4,2),transform)[0]
        x1,y1 = corners.min(axis=0); x2,y2 = corners.max(axis=0)
        metadata['barcode_box'] = [max(0,int(x1)-6),max(0,int(y1)-6),
                                   min(canvas_width,int(x2)+7),min(height,int(y2)+7)]

    aligned = cv2.warpPerspective(
        image,
        transform,
        (canvas_width, height),
        borderValue=(255, 255, 255),
    )

    original_mask = np.full(
        image.shape[:2],
        255,
        dtype=np.uint8,
    )

    coverage = cv2.warpPerspective(
        original_mask,
        transform,
        (canvas_width, height),
        flags=cv2.INTER_NEAREST,
        borderValue=0,
    )

    return aligned, coverage


def save_rgb(path, image):
    from PIL import Image

    Image.fromarray(image).save(path)


def prepare_field_crop(
    aligned,
    coverage,
    template,
    field,
    region,
    warnings,
    barcode_box=None,
):
    import numpy as np

    height = aligned.shape[0]

    # Use the original template width, not the expanded canvas width.
    width = template["size"][0]

    if field=='serial_number':
        from crop_adjustments import extend_serial_region
        region,extended=extend_serial_region(aligned,template,region)
        if extended:
            warnings.append('serial_number: crop widened because ink reached its right edge; verify the final characters.')

    x1, y1, x2, y2 = region

    left = max(0, round(x1 * width))
    top = max(0, round(y1 * height))
    right = min(aligned.shape[1], round(x2 * width))
    bottom = min(aligned.shape[0], round(y2 * height))

    if field=='date_sampled' and barcode_box:
        bx1,by1,_,by2=barcode_box
        if min(bottom,by2)-max(top,by1)>max(2,(bottom-top)*.10) and bx1>left+50:
            right=min(right,bx1-4)

    crop = aligned[top:bottom, left:right]
    valid = coverage[top:bottom, left:right]

    if crop.size == 0 or valid.size == 0:
        warnings.append(
            f"{field}: no image available."
        )
        return None

    coverage_fraction = float((valid > 0).mean())

    if coverage_fraction < 0.90:
        # Preserve strict coverage checks for the other fields.
        if field not in {'date_sampled','serial_number'} or coverage_fraction < 0.50:
            warnings.append(
                f"{field}: field is partly outside the photo."
            )
            return None

        # Trim extra canvas outside the photographed date region.
        rows, columns = np.nonzero(valid > 0)

        if len(rows) == 0:
            warnings.append(
                "date_sampled: no photographed pixels available."
            )
            return None

        top_edge = int(rows.min())
        bottom_edge = int(rows.max()) + 1
        left_edge = int(columns.min())
        right_edge = int(columns.max()) + 1

        crop = crop[
            top_edge:bottom_edge,
            left_edge:right_edge,
        ].copy()

        crop_mask = valid[
            top_edge:bottom_edge,
            left_edge:right_edge,
        ]

        # Perspective alignment can leave blank corners.
        crop[crop_mask == 0] = 255

        warnings.append(f'{field}: crop reaches the photo edge. Verify the complete value against the original.')

    if field=='date_sampled':
        from crop_adjustments import focus_date_ink
        crop=focus_date_ink(crop)
    return crop


def read_circled_component(engine, aligned):
    import cv2
    import numpy as np

    height, width = aligned.shape[:2]

    start = int(height * 0.80)
    row = aligned[start:, :]

    hsv = cv2.cvtColor(
        row,
        cv2.COLOR_RGB2HSV,
    )

    ink = cv2.inRange(
        hsv,
        np.array([95, 35, 25], dtype=np.uint8),
        np.array([175, 255, 255], dtype=np.uint8),
    )

    ink = cv2.morphologyEx(
        ink,
        cv2.MORPH_CLOSE,
        np.ones((3, 3), np.uint8),
    )

    contours, _ = cv2.findContours(
        ink,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    numbers = set()
    kinds = set()
    checked = set()

    for contour in contours:
        if len(contour) < 5:
            continue

        ellipse = cv2.fitEllipse(contour)
        (cx, cy), (axis_a, axis_b), angle = ellipse

        short = min(axis_a, axis_b)
        long = max(axis_a, axis_b)

        if short < height * 0.055:
            continue

        if long > height * 0.30:
            continue

        if long / max(short, 1) > 2.3:
            continue

        key = (
            round(cx / 15),
            round(cy / 15),
        )

        if key in checked:
            continue

        checked.add(key)

        x, y, box_width, box_height = cv2.boundingRect(
            contour
        )

        pad_x = int(box_width * 0.17)
        pad_y = int(box_height * 0.17)

        crop = row[
            max(0, y + pad_y):
                min(row.shape[0], y + box_height - pad_y),

            max(0, x + pad_x):
                min(width, x + box_width - pad_x),
        ]

        if crop.size == 0:
            continue

        text = "".join(
            read_text(engine, crop, line=True)
        )

        text = re.sub(
            r"[^A-Z0-9]",
            "",
            text.upper(),
        )

        if text in {"1", "2", "3", "4", "5", "6"}:
            numbers.add(text)

        elif text in {"GS", "NGS"}:
            kinds.add(text)

    if len(numbers) == 1 and len(kinds) == 1:
        number = next(iter(numbers))
        kind = next(iter(kinds))
        return f"{number} {kind}"

    return ""


def decode_barcodes(pixels):
    import zxingcpp

    return [
        barcode
        for barcode in zxingcpp.read_barcodes(pixels)
        if (
            barcode.valid
            and str(barcode.format).replace(" ", "") == "Code128"
        )
    ]


def process(job):
    from field_recognizer import FieldReader
    field_reader = FieldReader()
    import cv2
    import numpy as np

    from PIL import Image, ImageOps
    from rapidocr import RapidOCR

    cv2.setNumThreads(1)

    engine = RapidOCR(params=rapidocr_parameters())

    output_dir = Path(job["debug_dir"])
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []
    candidates = {
        key: []
        for key in FIELDS
    }

    detected_types = set()
    barcode_ids = set()
    warnings = []

    for index, image_path in enumerate(
        job["images"],
        start=1,
    ):
        entry = {
            "filename": Path(image_path).name,
            "label_type": "unknown",
            "text": [],
            "fields": {},
            "debug": [],
            "warnings": [],
            "error": None,
        }

        try:
            with Image.open(image_path) as original:
                if (
                    original.width * original.height
                    > 20_000_000
                ):
                    raise ValueError(
                        "Photo exceeds 20 megapixels."
                    )

                original.draft(
                    "RGB",
                    (1800, 1800),
                )

                photo = ImageOps.exif_transpose(
                    original
                ).convert("RGB")

                photo.thumbnail((1800, 1800))

                pixels = np.array(photo)
                photo.close()

            decoded = decode_barcodes(pixels)

            for barcode in decoded:
                value = barcode.text.strip()

                if value:
                    barcode_ids.add(value)

            if len({
                barcode.text.strip()
                for barcode in decoded
            }) > 1:
                raise ValueError(
                    "Different sample barcodes appear in one photo."
                )

            if decoded and decoded[0].orientation:
                rotated = Image.fromarray(pixels).rotate(
                    decoded[0].orientation,
                    expand=True,
                    fillcolor="white",
                )

                pixels = np.array(rotated)
                rotated.close()

                decoded = decode_barcodes(pixels)

                for barcode in decoded:
                    value = barcode.text.strip()

                    if value:
                        barcode_ids.add(value)

            texts = read_text(
                engine,
                pixels,
            )

            entry["text"] = texts

            raw = "\n".join(texts)
            label_type = identify_type(raw)

            entry["label_type"] = label_type

            if label_type == "unknown":
                entry["warnings"].append(
                    "Label type not recognized. Photograph the RN/SN "
                    "or Equip ID/Sample Point headings clearly."
                )

                results.append(entry)
                continue

            detected_types.add(label_type)

            values = raw_values(
                raw,
                label_type,
            )

            if decoded:
                template = TEMPLATES[label_type]

                aligned, coverage = align_to_template(
                    pixels,
                    decoded[0],
                    template,
                    metadata=entry,
                )

                aligned_name = (
                    f"photo_{index}_aligned.jpg"
                )

                save_rgb(
                    output_dir / aligned_name,
                    aligned,
                )

                entry["debug"].append(
                    aligned_name
                )

                if entry.get('alignment_method') == 'tight_large_label':
                    from label_alignment import TIGHT_LARGE_FIELDS
                    template = {**template, 'fields':TIGHT_LARGE_FIELDS}
                if label_type == 'large':
                    from label_rows import large_row_regions
                    detected_rows = large_row_regions(aligned,template)
                    if detected_rows:
                        template = {**template, 'fields':detected_rows['regions']}
                        entry['row_baselines'] = detected_rows['baselines']

                for field, region in template["fields"].items():
                    crop = prepare_field_crop(
                        aligned,
                        coverage,
                        template,
                        field,
                        region,
                        entry["warnings"],
                        barcode_box=entry.get('barcode_box'),
                    )

                    if crop is None:
                        values[field] = ""
                        continue

                    filename = (
                        f"photo_{index}_{field}.jpg"
                    )

                    save_rgb(
                        output_dir / filename,
                        crop,
                    )

                    entry["debug"].append(
                        filename
                    )

                    scores = []
                    recognized = clean(field_reader.read(
                        crop[..., ::-1].copy(), field, label_type,  # RGB crop -> BGR model input
                        fallback=lambda: " ".join(read_text(engine, crop, line=True, confidence=scores)),
                    ))
                    score = field_reader.last_confidence
                    if score is None and scores:
                        score = min(scores)
                    if os.environ.get('SCANNER_INK_RETRY')=='1' and field in {'machine','date_sampled'} and (score is None or score<.95):
                        from crop_adjustments import thin_heavy_ink, prefer_thinned_reading
                        variant=thin_heavy_ink(crop)
                        if variant is not None:
                            retry_scores=[]
                            candidate=clean(field_reader.read(variant[...,::-1].copy(),field,label_type,
                                fallback=lambda:' '.join(read_text(engine,variant,line=True,confidence=retry_scores))))
                            candidate_score=field_reader.last_confidence
                            if candidate_score is None and retry_scores:
                                candidate_score=min(retry_scores)
                            candidate=strip_heading(candidate,field,label_type)
                            base=strip_heading(recognized,field,label_type)
                            entry.setdefault('ink_attempts',{})[field]=[{'text':base,'score':score},
                                {'text':candidate,'score':candidate_score}]
                            if candidate!=base:
                                entry['warnings'].append(f'{field}: original and thin-ink OCR differ; verify the crop.')
                            if prefer_thinned_reading(base,score,candidate,candidate_score,field,job.get('date_received','')):
                                recognized,score=candidate,candidate_score
                    entry.setdefault('field_scores', {})[field] = score
                    entry.setdefault('field_quality', {})[field] = crop_quality(crop)
                    recognized = strip_heading(recognized,field,label_type)
                    if (not recognized and entry.get('alignment_method')=='tight_large_label'
                        and not any(w.startswith(field+':') for w in entry['warnings'])
                        and visually_empty(crop)):
                        entry.setdefault('blank_fields',[]).append(field)

                    if field == "date_sampled":
                        values[field] = valid_written_date(
                            recognized
                        )

                        if recognized and not values[field]:
                            entry["warnings"].append(
                                "Date needs review. OCR read: "
                                + recognized
                            )

                        elif not recognized:
                            entry["warnings"].append(
                                "Date needs review. No text recognized."
                            )

                    elif (
                        field == "machine"
                        and label_type == "small"
                    ):
                        if (
                            re.fullmatch(
                                r"\d+",
                                recognized,
                            )
                            and re.search(
                                r"\bRN\s*:?\s*UP",
                                raw,
                                re.I,
                            )
                        ):
                            recognized = (
                                "UP" + recognized
                            )

                        values[field] = recognized

                    else:
                        values[field] = recognized

                if label_type == "small":
                    values["component"] = read_circled_component(
                        engine,
                        aligned,
                    )

                    if not values["component"]:
                        entry["warnings"].append(
                            "Circled component could not be determined."
                        )

            else:
                entry["warnings"].append(
                    "No barcode decoded: automatic field alignment "
                    "was skipped. Values use raw OCR only."
                )

            if label_type == "small":
                values["reference_lube"] = ""

            else:
                values["serial_number"] = ""

            entry["fields"] = values

            for name, value in values.items():
                if value and name != "sample_id":
                    candidates[name].append(
                        clean(value)
                    )

        except Exception as error:
            entry["error"] = str(error)[:300]

        results.append(entry)

    if len(barcode_ids) > 1:
        return {
            "error":
                "Different sample IDs were decoded. These photos may "
                "show different tubes. Start a separate upload per tube."
        }

    warnings.extend(field_reader.warnings)
    if len(detected_types) > 1:
        return {
            "error":
                "Both label types were detected. Check that every "
                "photo belongs to the same tube."
        }

    label_type = (
        next(iter(detected_types))
        if detected_types
        else "unknown"
    )

    suggestions = {
        key: ""
        for key in FIELDS
    }

    alternatives = {}

    if len(barcode_ids) == 1:
        suggestions["sample_id"] = next(
            iter(barcode_ids)
        )

    else:
        warnings.append(
            "No Sample ID barcode decoded."
        )

    for name, values in candidates.items():
        unique = {}

        for value in values:
            unique.setdefault(
                value.casefold(),
                value,
            )

        choices = list(unique.values())
        alternatives[name] = choices

        if len(choices) == 1:
            suggestions[name] = choices[0]

        elif len(choices) > 1:
            warnings.append(
                f"{name}: conflicting readings; review required."
            )

    required = [
        "sample_id",
        "date_sampled",
        "machine",
        "component",
    ]

    if label_type == "small":
        required.append(
            "serial_number"
        )

    elif label_type == "large":
        required.append(
            "reference_lube"
        )

    if label_type == "unknown":
        warnings.append(
            "Label type could not be determined."
        )

    for name in required:
        if not suggestions[name]:
            warnings.append(
                f"{name}: missing or uncertain."
            )

    return {
        "ocr_threads": ocr_threads(),
        "blank_fields": [field for field in FIELDS if not suggestions[field] and results
            and all(not entry.get('error') and field in entry.get('blank_fields',[]) for entry in results)],
        "label_type": label_type,
        "suggestions": suggestions,
        "alternatives": alternatives,
        "images": results,
        "warnings": warnings,
    }


if __name__ == "__main__":
    try:
        job = json.loads(
            Path(sys.argv[1]).read_text(
                encoding="utf-8"
            )
        )

        result = process(job)

    except Exception as error:
        result = {
            "error":
                "Automatic OCR failed. Check the installed models. "
                + str(error)[:300]
        }

    Path(sys.argv[2]).write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )
