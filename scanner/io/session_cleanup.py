"""Remove upload folders for a finished session, or empty uploads at startup."""
import re
import shutil
from pathlib import Path


def clear_uploads(root, record_ids):
    root = root.resolve()
    targets = []
    for record_id in record_ids:
        if not re.fullmatch(r'[0-9a-f]{32}', record_id):
            raise ValueError('Invalid sample folder')
        target = root/record_id
        if target.is_symlink() or target.resolve().parent != root:
            raise ValueError('Sample folder is outside uploads')
        targets.append(target)
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
    return len(targets)


def empty_uploads(root):
    """Delete everything inside uploads and keep the folder itself."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    anchor = root.resolve()
    removed = 0
    for child in list(root.iterdir()):
        if child.is_symlink():
            child.unlink()
            removed += 1
            continue
        if child.resolve().parent != anchor:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed
