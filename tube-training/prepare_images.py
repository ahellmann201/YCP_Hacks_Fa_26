"""Convert copies of the user's HEIC images without changing the originals."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--magick', default='magick')
    args = parser.parse_args()
    sources = sorted(
        [p for p in args.source.rglob('*') if p.suffix.lower() in {'.heic', '.jpg', '.jpeg', '.png'}],
        key=lambda p: (int(re.search(r'\d+', p.parent.name).group()), p.name),
    )
    if not sources:
        raise SystemExit('No images found.')
    previous_path = ROOT / 'manifest.json'
    previous = {row['image_id']: row for row in json.loads(previous_path.read_text(encoding='utf-8'))} if previous_path.exists() else {}
    def convert(path):
        tube = 'tube_' + re.search(r'\d+', path.parent.name).group().zfill(3)
        image_id = tube + '_' + path.stem.lower()
        destination = ROOT / 'images' / tube / (image_id + '.jpg')
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        old = previous.get(image_id, {})
        if not destination.exists() or old.get('source_sha256') != digest:
            subprocess.run([
                args.magick, '-limit', 'thread', '2', '-limit', 'memory', '256MiB',
                str(path), '-auto-orient', '-quality', '95', str(destination),
            ], check=True, capture_output=True)
        with Image.open(destination) as image:
            width, height = image.size
        return {'image_id': image_id, 'tube_id': tube,
                'source_folder': path.parent.name, 'source_file': str(path.resolve()),
                'source_sha256': digest, 'image': destination.relative_to(ROOT).as_posix(),
                'view_rotation': old.get('view_rotation', 0),
                'width': width, 'height': height}
    with ThreadPoolExecutor(max_workers=2) as pool:
        manifest = list(pool.map(convert, sources))
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    groups = {m['tube_id'] for m in manifest}
    print(f'Prepared {len(manifest)} images from {len(groups)} tubes.', flush=True)
    preview = ROOT / 'contact-sheets'
    preview.mkdir(exist_ok=True)
    for offset in range(0, len(manifest), 12):
        page = Image.new('RGB', (1200, 1200), 'white')
        draw = ImageDraw.Draw(page)
        for index, row in enumerate(manifest[offset:offset+12]):
            left = (index % 3) * 400
            top = (index // 3) * 300
            with Image.open(ROOT / row['image']) as image:
                thumb = ImageOps.contain(image, (390, 265))
                page.paste(thumb, (left+(400-thumb.width)//2, top+25))
            draw.text((left+8, top+7), row['image_id'], fill='black')
        page.save(preview / f'page_{offset//12+1}.jpg', quality=90)


if __name__ == '__main__':
    main()
