import argparse
import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from uuid import uuid4
from PIL import Image
from dataset import FIELDS, state, write, export_dataset
from draft_labels import approve

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()


def rotated(image_id, rotation):
    manifest = {row['image_id']: row for row in state(ROOT)['manifest']}
    if image_id not in manifest:
        raise ValueError('Unknown image.')
    if rotation not in {0, 90, 180, 270}:
        raise ValueError('Invalid rotation.')
    with Image.open(ROOT / manifest[image_id]['image']) as source:
        return source.rotate(-rotation, expand=True).convert('RGB')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, value, status=200, content_type='application/json'):
        body = json.dumps(value, ensure_ascii=False).encode() if content_type == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/api/state':
                with LOCK:
                    self.send(state(ROOT))
            elif parsed.path == '/api/drafts':
                with LOCK:
                    data = state(ROOT)
                    path = ROOT / 'draft_annotations.json'
                    self.send({'drafts': json.loads(path.read_text(encoding='utf-8')) if path.exists() else [],
                               'tubes': data['tubes']})
            elif parsed.path == '/review':
                self.send((ROOT / 'draft_review.html').read_bytes(), content_type='text/html; charset=utf-8')
            elif parsed.path.startswith('/draft-crop/'):
                identifier = parsed.path[len('/draft-crop/'):]
                if not re.fullmatch(r'[0-9a-f]{32}', identifier):
                    raise ValueError('Invalid draft ID.')
                self.send((ROOT / 'draft-crops' / (identifier + '.png')).read_bytes(), content_type='image/png')
            elif parsed.path.startswith('/sheet/'):
                tube = parsed.path[len('/sheet/'):]
                if not re.fullmatch(r'tube_\d{3}', tube):
                    raise ValueError('Invalid tube ID.')
                self.send((ROOT / 'draft-review' / (tube + '_review.jpg')).read_bytes(), content_type='image/jpeg')
            elif parsed.path == '/':
                self.send((ROOT / 'labeling.html').read_bytes(), content_type='text/html; charset=utf-8')
            elif parsed.path.startswith('/photo/'):
                image_id = unquote(parsed.path[len('/photo/'):])
                rotation = int(parse_qs(parsed.query).get('rotate', ['0'])[0])
                image = rotated(image_id, rotation)
                output = BytesIO()
                image.save(output, format='JPEG', quality=94)
                image.close()
                self.send(output.getvalue(), content_type='image/jpeg')
            elif parsed.path.startswith('/crop/'):
                identifier = parsed.path[len('/crop/'):]
                if not re.fullmatch(r'[0-9a-f]{32}', identifier):
                    raise ValueError('Invalid crop.')
                self.send((ROOT / 'crops' / (identifier + '.png')).read_bytes(), content_type='image/png')
            else:
                self.send({'error': 'Not found'}, 404)
        except (OSError, ValueError) as error:
            self.send({'error': str(error)}, 400)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 1_000_000:
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(length))
            with LOCK:
                current = state(ROOT)
                if self.path == '/api/tube':
                    tube = data['tube_id']
                    if tube not in current['tubes']:
                        raise ValueError('Unknown tube.')
                    if data['label_type'] not in {'unknown', 'small', 'large'}:
                        raise ValueError('Invalid label type.')
                    if data['split'] not in {'unassigned', 'train', 'val', 'exclude'}:
                        raise ValueError('Invalid split.')
                    group = data['group_id'].strip()
                    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', group):
                        raise ValueError('Use letters, digits, underscores, or hyphens for the group.')
                    current['tubes'][tube] = {
                        'label_type': data['label_type'], 'split': data['split'],
                        'group_id': group, 'notes': str(data.get('notes', ''))[:2000],
                    }
                    write(ROOT / 'tube_meta.json', current['tubes'])
                    self.send({'ok': True})
                elif self.path == '/api/approve-draft':
                    self.send(approve(ROOT, data))
                elif self.path == '/api/crop':
                    image_id = data['image_id']
                    image_record = next((r for r in current['manifest'] if r['image_id'] == image_id), None)
                    if not image_record:
                        raise ValueError('Unknown image.')
                    tube = image_record['tube_id']
                    if current['tubes'][tube]['label_type'] == 'unknown':
                        raise ValueError('Set the tube label type first.')
                    if data['field'] not in FIELDS or data['status'] not in {'verified', 'blank', 'uncertain'}:
                        raise ValueError('Invalid field or status.')
                    text = str(data.get('text', '')).strip()
                    if len(text) > 200 or any(c in text for c in '\r\n\t'):
                        raise ValueError('Text must be one line, maximum 200 characters.')
                    if data['status'] == 'verified' and not text:
                        raise ValueError('Enter the correct text, or select Blank / Uncertain.')
                    rotation = int(data['rotation'])
                    image = rotated(image_id, rotation)
                    box = [int(round(float(value))) for value in data['box']]
                    if len(box) != 4:
                        raise ValueError('Draw a box first.')
                    x1, y1, x2, y2 = box
                    if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height):
                        raise ValueError('Crop is outside the photo.')
                    if x2 - x1 < 8 or y2 - y1 < 8:
                        raise ValueError('Crop is too small.')
                    identifier = uuid4().hex
                    (ROOT / 'crops').mkdir(exist_ok=True)
                    image.crop(box).save(ROOT / 'crops' / (identifier + '.png'))
                    image.close()
                    annotation = {
                        'id': identifier, 'image_id': image_id, 'tube_id': tube,
                        'field': data['field'], 'rotation': rotation, 'box': box,
                        'status': data['status'], 'text': text,
                        'notes': str(data.get('notes', ''))[:2000],
                    }
                    current['annotations'].append(annotation)
                    write(ROOT / 'annotations.json', current['annotations'])
                    self.send(annotation)
                elif self.path == '/api/remove':
                    current['annotations'] = [a for a in current['annotations'] if a['id'] != data['id']]
                    write(ROOT / 'annotations.json', current['annotations'])
                    self.send({'ok': True})
                elif self.path == '/api/export':
                    self.send(export_dataset(ROOT))
                else:
                    self.send({'error': 'Not found'}, 404)
        except (KeyError, TypeError, OSError, ValueError) as error:
            self.send({'error': str(error)}, 400)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not (ROOT / 'manifest.json').exists():
        raise SystemExit('Run prepare_images.py first.')
    url = f'http://127.0.0.1:{args.port}'
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print('Tube labeling tool:', url, flush=True)
    if not args.no_browser:
        webbrowser.open(url + ('/review' if (ROOT / 'draft_annotations.json').exists() else ''))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
