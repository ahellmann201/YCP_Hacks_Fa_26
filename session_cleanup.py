"""Remove only the explicitly finished session's UUID upload folders."""
import re
import shutil


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
