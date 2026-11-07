"""Compare a batch against a truth CSV, per column and against the review flag."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .pipeline import REVIEW_BELOW

SCORED = ["Date Sampled", "Machine", "Component", "Serial Number", "Refrence Lube"]


def _key(text: str) -> str:
    return " ".join(text.lower().split())


def score(results: list[dict], truth_path: Path) -> str:
    with truth_path.open(encoding="utf-8-sig") as handle:
        truth = {row["Sample ID"]: row for row in csv.DictReader(handle) if row["Sample ID"]}
    tally = defaultdict(lambda: [0, 0])
    outcomes = {"right, passed": 0, "right, flagged": 0, "wrong, flagged": 0, "wrong, PASSED": 0}
    lines, misses = [], []
    for result in results:
        expected = truth.get(result.get("sample_id"))
        if expected is None:
            lines.append(f"no truth row: {result['image']} ({result.get('sample_id', result.get('error'))})")
            continue
        found = {f["column"]: f for f in result["fields"]}
        for column in SCORED:
            field = found.get(column, {"value": "", "confidence": 1.0})
            right = _key(field["value"]) == _key(expected[column])
            flagged = field["confidence"] < REVIEW_BELOW
            tally[column][0] += right
            tally[column][1] += 1
            outcomes[("right, " if right else "wrong, ") + (("flagged" if flagged else "passed") if right else ("flagged" if flagged else "PASSED"))] += 1
            if not right:
                misses.append(f"  {result['sample_id']} {column}: got {field['value']!r} want {expected[column]!r} conf {field['confidence']}")
    lines += [f"{c:15} {r}/{n}" for c, (r, n) in tally.items()]
    right = sum(v[0] for v in tally.values())
    total = sum(v[1] for v in tally.values())
    lines.append(f"{'ALL FIELDS':15} {right}/{total} ({right / total:.0%})")
    lines.append(str(outcomes))
    return "\n".join(lines + ["misses:"] + misses)
