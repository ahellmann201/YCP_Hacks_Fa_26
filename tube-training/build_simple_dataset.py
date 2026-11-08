"""Build a held-out-tube dataset from scanner field crops of simple_samples."""
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('SCANNER_OCR_THREADS', '2')

from scanner.reading.scanner_auto import process

# Visible text only. Blank fields are omitted. Whole tubes are held out.
LABELS = {
    '1': {'split': 'train', 'kind': 'large', 'fields': {
        'machine': '53279869', 'component': '420 NPF', 'reference_lube': 'Adjusting side'}},
    '2': {'split': 'train', 'kind': 'large', 'fields': {
        'machine': '27', 'component': 'Rear MoBr', 'reference_lube': 'SKF', 'date_sampled': '4.13.26'}},
    '3': {'split': 'val', 'kind': 'large', 'fields': {
        'machine': 'ASCN GPS ANTENNA', 'component': 'AZ RING', 'reference_lube': 'AEROSHELL 14',
        'date_sampled': '8/12/26'}},
    '4': {'split': 'train', 'kind': 'small', 'fields': {
        'machine': '6500q', 'serial_number': 'PP9706198', 'date_sampled': '9/28/26'}},
    '5': {'split': 'val', 'kind': 'small', 'fields': {
        'machine': '6500q', 'serial_number': 'PP04101544', 'date_sampled': '9/28/26'}},
    '6': {'split': 'train', 'kind': 'small', 'fields': {
        'machine': '2642', 'date_sampled': '7/20'}},
    '7': {'split': 'train', 'kind': 'small', 'fields': {
        'machine': '7738', 'serial_number': 'PP04020258', 'date_sampled': '9.2'}},
    '8': {'split': 'val', 'kind': 'small', 'fields': {
        'machine': '7738', 'serial_number': 'PP9810149', 'date_sampled': '9/20'}},
    '9': {'split': 'train', 'kind': 'small', 'fields': {
        'machine': '2642', 'date_sampled': '7/20'}},
}

ZIP = Path(r'C:\Hackathons\YCP_Hack_Fa_26\Sample Images\simple_samples.zip')
WORK = Path(__file__).resolve().parent / 'simple-sample-run'
PHOTOS = WORK / 'photos'
DEBUG = WORK / 'debug'
EXPORT = Path(__file__).resolve().parent / 'exports' / 'simple-samples-holdout'


def main():
    if PHOTOS.exists():
        shutil.rmtree(PHOTOS)
    PHOTOS.mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as archive:
        archive.extractall(PHOTOS)
    base = PHOTOS / 'simple_samples'
    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    (EXPORT / 'crops').mkdir(parents=True)
    lines = {'train': [], 'val': []}
    manifest = []
    for tube, spec in LABELS.items():
        folder = base / tube
        images = sorted(p for p in folder.iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'})
        digest = hashlib.sha256(images[0].read_bytes()).hexdigest()
        process({'images': [str(images[0])], 'debug_dir': str(DEBUG / tube)})
        for field, text in spec['fields'].items():
            source = DEBUG / tube / f'photo_1_{field}.jpg'
            if not source.is_file():
                raise SystemExit(f'Missing crop {source}')
            identifier = hashlib.md5(f'{tube}:{field}'.encode()).hexdigest()
            relative = f'crops/{identifier}.png'
            shutil.copy2(source, EXPORT / relative)
            lines[spec['split']].append(f'{relative}\t{text}')
            manifest.append({
                'id': identifier, 'field': field, 'text': text, 'tube_id': tube,
                'label_type': spec['kind'], 'group_id': tube, 'split': spec['split'],
                'source_sha256': digest, 'crop': relative, 'task': 'recognition',
            })
    for split, rows in lines.items():
        (EXPORT / f'{split}.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    (EXPORT / 'manifest.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in manifest), encoding='utf-8')
    summary = {
        'training_crops': len(lines['train']), 'validation_crops': len(lines['val']),
        'held_out_tubes': [tube for tube, spec in LABELS.items() if spec['split'] == 'val'],
        'note': 'Tubes 3, 5, and 8 are validation. Blank fields were not labeled.',
    }
    (EXPORT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
