"""Usage: python -m labelreader FOLDER --name BATCH [--truth CSV]"""
import argparse
from pathlib import Path

from .handwriting import TrOCRReader
from .pipeline import run_batch
from .score import score

parser = argparse.ArgumentParser(prog="labelreader", description="Read sample label images into a CSV.")
parser.add_argument("folder", type=Path)
parser.add_argument("--name", required=True, help="name of the CSV file")
parser.add_argument("--out", type=Path, default=Path("out"))
parser.add_argument("--truth", type=Path, help="optional CSV to score against")
args = parser.parse_args()

results = run_batch(args.folder, args.out / args.name, args.name, TrOCRReader())
print(f"{len(results)} images -> {args.out / args.name / (args.name + '.csv')}")
if args.truth:
    print(score(results, args.truth))
