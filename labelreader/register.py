"""Find a label's codes, pick its template, and locate its printed captions.

Barcodes are printed separately from the form, so they only give the label's
scale. Every field is positioned from its own printed caption instead.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import zxingcpp

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
SEARCH_RADIUS = 110
SCALES = (0.94, 0.97, 1.0, 1.03, 1.06)


@dataclass
class Caption:
    dx: int  # offset from the caption's position on the reference label
    dy: int
    score: float  # 0..1 match against the reference caption


@dataclass
class Registered:
    template: dict
    sample_id: str
    image: np.ndarray  # label scaled to match the reference
    captions: dict[str, Caption]

    def crop(self, box: list[int], caption: str) -> np.ndarray:
        c = self.captions[caption]
        h, w = self.image.shape[:2]
        x0, y0, x1, y1 = box
        x0, x1 = (max(0, min(w, v + c.dx)) for v in (x0, x1))
        y0, y1 = (max(0, min(h, v + c.dy)) for v in (y0, y1))
        return self.image[y0:y1, x0:x1]


class RegistrationError(Exception):
    """The image could not be matched to a known label layout."""


def load_templates(directory: Path = TEMPLATE_DIR) -> list[dict]:
    templates = []
    for path in sorted(directory.glob("*.json")):
        template = json.loads(path.read_text())
        reference = cv2.imread(str(directory / template["reference"]), cv2.IMREAD_GRAYSCALE)
        if reference is None:
            raise FileNotFoundError(f"{path.name}: missing reference image")
        template["_reference"] = reference
        templates.append(template)
    return templates


def _codes(image: np.ndarray):
    linear = qr = None
    for code in zxingcpp.read_barcodes(image):
        if code.format == zxingcpp.BarcodeFormat.QRCode:
            qr = code
        elif code.text.isdigit():
            linear = code
    return linear, qr


def _width(code) -> float:
    p = code.position
    return float(np.hypot(p.top_right.x - p.top_left.x, p.top_right.y - p.top_left.y))


def _find_caption(gray: np.ndarray, patch: np.ndarray, box: list[int]) -> Caption:
    """Best match for a reference caption near where it should be."""
    h, w = gray.shape
    x0 = max(0, box[0] - SEARCH_RADIUS)
    y0 = max(0, box[1] - SEARCH_RADIUS)
    window = gray[y0:min(h, box[3] + SEARCH_RADIUS), x0:min(w, box[2] + SEARCH_RADIUS)]
    best = Caption(0, 0, 0.0)
    for scale in SCALES:
        scaled = cv2.resize(patch, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scaled.shape[0] > window.shape[0] or scaled.shape[1] > window.shape[1]:
            continue
        result = cv2.matchTemplate(window, scaled, cv2.TM_CCOEFF_NORMED)
        _, score, _, (px, py) = cv2.minMaxLoc(result)
        if score > best.score:
            # Compare centres so a scaled match doesn't shift the offset.
            dx = px + x0 + scaled.shape[1] / 2 - (box[0] + box[2]) / 2
            dy = py + y0 + scaled.shape[0] / 2 - (box[1] + box[3]) / 2
            best = Caption(round(dx), round(dy), float(score))
    return best


def register(image: np.ndarray, templates: list[dict]) -> Registered:
    linear, qr = _codes(image)
    if linear is None:
        raise RegistrationError("no barcode found")
    for template in templates:
        if template["match"]["has_qr"] != (qr is not None):
            continue
        rule = template["scale_from"]
        code = qr if rule["code"] == "qr" else linear
        scale = rule["width"] / _width(code)
        scaled = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        reference = template["_reference"]
        captions = {
            name: _find_caption(gray, reference[box[1]:box[3], box[0]:box[2]], box)
            for name, box in template["captions"].items()
        }
        return Registered(template, linear.text, scaled, captions)
    raise RegistrationError("no template matches this label")
