"""Prepare a field crop and read it. Readers are swappable."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np
from PIL import Image

BLANK_INK_PIXELS = 250


@dataclass
class Reading:
    text: str
    probability: float  # the reader's own 0..1 estimate


class Reader(Protocol):
    def read(self, crop: np.ndarray) -> Reading: ...


def ink_mask(crop: np.ndarray) -> np.ndarray:
    """Handwriting pixels, with stains, shading and ruled lines removed."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    mask = ((cv2.medianBlur(gray, 51).astype(np.int16) - gray) > 35).astype(np.uint8)
    ruled = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((1, 120), np.uint8))
    return mask & ~cv2.dilate(ruled, np.ones((3, 1), np.uint8)) & 1


def is_blank(crop: np.ndarray) -> bool:
    mask = ink_mask(crop)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    return sum(int(s[cv2.CC_STAT_AREA]) for s in stats[1:] if s[cv2.CC_STAT_AREA] >= 25) < BLANK_INK_PIXELS


def trim(crop: np.ndarray, pad: int = 12) -> np.ndarray:
    """Cut to the ink so the reader isn't squashing a mostly empty strip."""
    ys, xs = np.nonzero(ink_mask(crop))
    if len(xs) == 0:
        return crop
    h, w = crop.shape[:2]
    return crop[max(0, ys.min() - pad):min(h, ys.max() + pad),
                max(0, xs.min() - pad):min(w, xs.max() + pad)]


def clean_variant(crop: np.ndarray) -> np.ndarray:
    """Black ink on white: a second, independent view of the same field."""
    mask = cv2.dilate(ink_mask(crop), np.ones((2, 2), np.uint8))
    return cv2.cvtColor(np.where(mask > 0, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


class TrOCRReader:
    """Local handwriting model: no network or API key at run time."""

    def __init__(self, model: str = "microsoft/trocr-base-handwritten"):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        self._torch = torch
        self.processor = TrOCRProcessor.from_pretrained(model)
        self.model = VisionEncoderDecoderModel.from_pretrained(model).eval()

    def read(self, crop: np.ndarray) -> Reading:
        torch = self._torch
        image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        pixels = self.processor(images=image, return_tensors="pt").pixel_values
        with torch.no_grad():
            out = self.model.generate(
                pixels, max_new_tokens=24, num_beams=1,
                output_scores=True, return_dict_in_generate=True,
            )
        logprobs = [torch.log_softmax(s[0], -1).max().item() for s in out.scores]
        text = self.processor.batch_decode(out.sequences, skip_special_tokens=True)[0]
        return Reading(text.strip(), float(np.exp(np.mean(logprobs))) if logprobs else 0.0)
