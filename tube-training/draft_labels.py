"""Human approval of visually prepared draft field labels."""
import json
import re
import shutil
from datetime import datetime, timezone
from dataset import load, write, state


def approve(root, request):
    identifier = request.get('id', '')
    drafts = load(root / 'draft_annotations.json', [])
    draft = next((row for row in drafts if row['id'] == identifier), None)
    if draft is None or not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise ValueError('Draft not found.')
    status = request.get('status')
    if status not in {'verified', 'blank', 'uncertain'}:
        raise ValueError('Choose a label status.')
    text = str(request.get('text', '')).strip()
    if draft['field'] == 'serial_number':
        text = text.upper()
    if len(text) > 200 or any(c in text for c in '\r\n\t'):
        raise ValueError('Use one line, maximum 200 characters.')
    if status == 'verified' and (not text or request.get('human_checked') is not True):
        raise ValueError('Check the full crop and transcription before approving it for training.')
    if status == 'blank':
        text = ''
    crop = root / 'draft-crops' / (identifier + '.png')
    if not crop.is_file():
        raise ValueError('Draft crop is missing.')
    current = state(root)
    annotation = {
        key: draft[key] for key in ('id', 'image_id', 'tube_id', 'field', 'rotation', 'box')
    }
    annotation.update(
        status=status, text=text, notes=str(request.get('notes', ''))[:2000],
        origin='assistant_draft_human_reviewed',
        approved_at=datetime.now(timezone.utc).isoformat(),
    )
    # Replace earlier annotations for this tube/field only after human review.
    # Keep all replaced records in a recoverable history file.
    previous = [row for row in current['annotations']
                if row['tube_id'] == draft['tube_id'] and row['field'] == draft['field']]
    history = load(root / 'annotation_history.json', [])
    history.extend({'archived_at': annotation['approved_at'], 'annotation': row}
                   for row in previous if row['id'] != identifier)
    write(root / 'annotation_history.json', history)
    (root / 'crops').mkdir(exist_ok=True)
    shutil.copy2(crop, root / 'crops' / (identifier + '.png'))
    remaining = [row for row in current['annotations'] if not (
        row['tube_id'] == draft['tube_id'] and row['field'] == draft['field'])]
    remaining.append(annotation)
    write(root / 'annotations.json', remaining)
    draft.update(review_status='approved', approved_annotation_id=identifier,
                 approved_status=status, approved_text=text)
    write(root / 'draft_annotations.json', drafts)
    return annotation
