"""Work out which printed option has been circled, with no text recognition."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .register import Registered

SEARCH_X, SEARCH_Y = 90, 30
NOTHING_CIRCLED = 0.03


@dataclass
class ChoiceResult:
    value: str
    confidence: float  # 0..1, how clearly the winner beats the runner-up
    scores: dict[str, float]


def _ink(gray: np.ndarray) -> np.ndarray:
    """Pixels darker than their surroundings, ignoring stains and shading."""
    background = cv2.medianBlur(gray, 51)
    return (background.astype(np.int16) - gray) > 35


def _row_offset(gray: np.ndarray, reference: np.ndarray, spec: dict, base: tuple[int, int]) -> tuple[int, int]:
    """Find where this option row sits, trusting only the glyphs that match well.

    The spacing between option groups differs between print runs, and a circled
    glyph won't match, so each glyph votes and the weak matches are dropped.
    """
    iw, ih = spec["inner"]
    votes = []
    for cx, cy in spec["options"].values():
        patch = reference[cy - ih // 2:cy + ih // 2, cx - iw // 2:cx + iw // 2]
        x0 = max(0, cx + base[0] - iw // 2 - SEARCH_X)
        y0 = max(0, cy + base[1] - ih // 2 - SEARCH_Y)
        window = gray[y0:cy + base[1] + ih // 2 + SEARCH_Y, x0:cx + base[0] + iw // 2 + SEARCH_X]
        if window.shape[0] < patch.shape[0] or window.shape[1] < patch.shape[1]:
            continue
        _, score, _, (px, py) = cv2.minMaxLoc(cv2.matchTemplate(window, patch, cv2.TM_CCOEFF_NORMED))
        votes.append((score, px + x0 + iw // 2 - cx, py + y0 + ih // 2 - cy))
    if not votes:
        return base
    strongest = max(v[0] for v in votes)
    kept = [v for v in votes if v[0] >= 0.75 * strongest]
    return int(np.median([v[1] for v in kept])), int(np.median([v[2] for v in kept]))


def read_choice(label: Registered, name: str) -> ChoiceResult:
    spec = label.template["choices"][name]
    caption = label.captions[spec["caption"]]
    gray = cv2.cvtColor(label.image, cv2.COLOR_BGR2GRAY)
    dx, dy = _row_offset(gray, label.template["_reference"], spec, (caption.dx, caption.dy))
    ink = _ink(gray)
    (ow, oh), (iw, ih) = spec["outer"], spec["inner"]
    scores = {}
    for option, (cx, cy) in spec["options"].items():
        cx, cy = cx + dx, cy + dy
        ring = np.zeros(ink.shape, bool)
        ring[max(0, cy - oh // 2):cy + oh // 2, max(0, cx - ow // 2):cx + ow // 2] = True
        ring[max(0, cy - ih // 2):cy + ih // 2, max(0, cx - iw // 2):cx + iw // 2] = False
        scores[option] = float(ink[ring].mean()) if ring.any() else 0.0
    ranked = sorted(scores, key=scores.get, reverse=True)
    top, second = scores[ranked[0]], scores[ranked[1]]
    if top < NOTHING_CIRCLED:  # nothing circled: leave blank, as the label does
        return ChoiceResult("", 0.5, scores)
    return ChoiceResult(ranked[0], round(1 - second / top, 3), scores)
