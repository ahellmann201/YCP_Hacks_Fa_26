from pathlib import Path

def build_preview(folder, run_id, result, kind):
    from PIL import (
        Image, ImageOps, ImageDraw, ImageFont,
        ImageFilter, ImageStat,
    )
    if kind not in {"small", "large"}:
        return None
    root = Path(folder) / "analysis" / run_id
    root.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        heading = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except OSError:
        font = heading = ImageFont.load_default()

    if kind == "small":
        size = (1200, 770)
        boxes = {
            "barcode": (20, 60, 1180, 225),
            "machine": (20, 235, 720, 395),
            "date_sampled": (735, 235, 1180, 395),
            "serial_number": (20, 405, 1180, 575),
            "component": (20, 585, 1180, 750),
        }
    else:
        size = (1200, 710)
        boxes = {
            "machine": (20, 60, 1180, 205),
            "component": (20, 215, 1180, 360),
            "reference_lube": (20, 370, 1180, 515),
            "date_sampled": (20, 525, 560, 690),
            "barcode": (575, 525, 1180, 690),
        }

    titles = {
        "barcode": "Sample ID barcode", "machine": "Machine",
        "date_sampled": "Date Sampled", "serial_number": "Serial Number",
        "component": "Component", "reference_lube": "Reference Lube",
    }
    sheet = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 15), f"{kind.title()} label — combined field view",
              fill="black", font=heading)
    sources = {}

    for field, box in boxes.items():
        best = None
        best_score = -1
        source_number = None
        for index, entry in enumerate(result.get("images", []), start=1):
            if entry.get("label_type") != kind:
                continue
            name = f"photo_{index}_{field}.jpg"
            try:
                if field == "barcode" or (
                    field == "component" and kind == "small"
                ):
                    with Image.open(root / f"photo_{index}_aligned.jpg") as image:
                        height = image.height
                        if field == "component":
                            region = (60, int(height*.80), 1160, height)
                        elif kind == "small":
                            region = (216, int(height*.02), 948, int(height*.25))
                        else:
                            region = (564, int(height*.65), 1020, int(height*.91))
                        crop = image.crop(region).convert("RGB")
                else:
                    if name not in entry.get("debug", []):
                        continue
                    with Image.open(root / name) as image:
                        crop = image.convert("RGB")

                thumb = ImageOps.grayscale(crop).resize((128, 48))
                score = ImageStat.Stat(
                    thumb.filter(ImageFilter.FIND_EDGES)).mean[0]
                expected = str(
                    result.get("suggestions", {}).get(field, "")).casefold()
                observed = str(
                    entry.get("fields", {}).get(field, "")).casefold()
                if expected and observed == expected:
                    score += 1000
                if score > best_score:
                    if best is not None:
                        best.close()
                    best, best_score, source_number = crop, score, index
                else:
                    crop.close()
            except (OSError, ValueError):
                continue

        left, top, right, bottom = box
        draw.rectangle(box, outline="#aab4c0", width=2)
        caption = titles[field]
        if source_number is not None:
            caption += f" — photo {source_number}"
            sources[field] = source_number
        draw.text((left+10, top+8), caption, fill="#26364a", font=font)
        if best is None:
            draw.text((left+10, top+50), "Check original photos",
                      fill="#a02020", font=font)
        else:
            # Save the selected actual field crop for the focused review row.
            best.save(root / f"field_{field}.jpg", quality=90)
            best.thumbnail((right-left-20, bottom-top-50))
            sheet.paste(best, (left+10, top+45))
            best.close()

    sheet.save(root / "combined.jpg", quality=90)
    return {
        "run_id": run_id, "filename": "combined.jpg",
        "sources": sources,
    }
