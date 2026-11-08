"""Dataset validation/export. Never export uncertain or blank crops as text."""
import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

FIELDS = {'sample_id', 'date_sampled', 'machine', 'component', 'serial_number', 'reference_lube'}


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def state(root):
    manifest = load(root / 'manifest.json', [])
    metadata = load(root / 'tube_meta.json', {})
    for row in manifest:
        metadata.setdefault(row['tube_id'], {
            'label_type': 'unknown', 'group_id': row['tube_id'],
            'split': 'unassigned', 'notes': '',
        })
    return {'manifest': manifest, 'tubes': metadata,
            'annotations': load(root / 'annotations.json', [])}


def export_dataset(root):
    data = state(root)
    images = {row['image_id']: row for row in data['manifest']}
    selected = []
    ignored = []
    group_splits = {}
    hash_splits = {}
    for annotation in data['annotations']:
        if annotation['status'] != 'verified':
            ignored.append(annotation)
            continue
        image = images[annotation['image_id']]
        meta = data['tubes'][image['tube_id']]
        split = meta['split']
        group = meta['group_id']
        if split == 'exclude':
            ignored.append(annotation)
            continue
        if split not in {'train', 'val'}:
            raise ValueError(f"Choose Train or Validation for {image['tube_id']} first.")
        if meta['label_type'] not in {'small', 'large'}:
            raise ValueError(f"Choose label type for {image['tube_id']} first.")
        if group in group_splits and group_splits[group] != split:
            raise ValueError(f'Group {group} crosses Train/Validation. Fix the tube metadata.')
        group_splits[group] = split
        digest = image['source_sha256']
        if digest in hash_splits and hash_splits[digest] != split:
            raise ValueError('The same original image occurs in both Train and Validation.')
        hash_splits[digest] = split
        identifier = annotation['id']
        if not re.fullmatch(r'[0-9a-f]{32}', identifier):
            raise ValueError('Invalid annotation ID.')
        crop = root / 'crops' / (identifier + '.png')
        if not crop.is_file():
            raise ValueError(f'Missing crop: {identifier}')
        text = annotation['text'].strip()
        if not text or any(c in text for c in '\t\r\n'):
            raise ValueError('Verified text must be nonempty and fit on one line.')
        task = 'recognition'
        if annotation['field'] == 'sample_id':
            task = 'barcode'
        if annotation['field'] == 'component' and meta['label_type'] == 'small':
            task = 'selection'
        selected.append({**annotation, 'label_type': meta['label_type'],
                         'group_id': group, 'tube_notes': meta.get('notes', ''),
                         'split': split, 'task': task,
                         'tube_id': image['tube_id'], 'source_sha256': digest,
                         'crop': 'crops/' + identifier + '.png'})
    recognition = [row for row in selected if row['task'] == 'recognition']
    if not any(row['split'] == 'train' for row in recognition):
        raise ValueError('No verified training text crops yet.')
    if not any(row['split'] == 'val' for row in recognition):
        raise ValueError('No verified validation text crops yet.')
    output = root / 'exports' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    (output / 'crops').mkdir(parents=True)
    for row in selected:
        shutil.copy2(root / row['crop'], output / row['crop'])
    for split in ('train', 'val'):
        lines = [row['crop'] + '\t' + row['text'] for row in recognition if row['split'] == split]
        (output / (split + '.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for name, rows in (
        ('manifest', selected), ('ignored', ignored),
        ('selection_labels', [r for r in selected if r['task'] == 'selection']),
        ('barcode_checks', [r for r in selected if r['task'] == 'barcode']),
    ):
        (output / (name + '.jsonl')).write_text(
            ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    write(output / 'group_splits.json', group_splits)
    summary = {
        'path': str(output), 'training_crops': sum(r['split'] == 'train' for r in recognition),
        'validation_crops': sum(r['split'] == 'val' for r in recognition),
        'training_groups': sum(s == 'train' for s in group_splits.values()),
        'validation_groups': sum(s == 'val' for s in group_splits.values()),
        'note': 'Development split only. Collect unseen tubes/writers for a final test set.',
    }
    write(output / 'summary.json', summary)
    return summary
