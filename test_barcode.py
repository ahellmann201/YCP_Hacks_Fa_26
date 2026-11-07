import sys
from pathlib import Path

import numpy as np
import zxingcpp
from PIL import Image, ImageOps


if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: python test_barcode.py uploads/SAMPLE_FOLDER/image_1.jpg"
    )

path = Path(sys.argv[1])

if not path.is_file():
    raise SystemExit(f"Photo not found: {path}")

with Image.open(path) as original:
    if original.width * original.height > 20_000_000:
        raise SystemExit("Use a photo under 20 megapixels.")

    # Keep the barcode's original detail.
    image = ImageOps.exif_transpose(original).convert("RGB")
    pixels = np.asarray(image)

    barcodes = zxingcpp.read_barcodes(pixels)

if not barcodes:
    print("No barcode decoded.")
    print(
        "Include the entire barcode with clear space at both ends. "
        "Keep the bars sharp and facing the camera."
    )
else:
    for barcode in barcodes:
        print(f"Decoded value: {barcode.text}")
        print(f"Barcode format: {barcode.format}")
        print()