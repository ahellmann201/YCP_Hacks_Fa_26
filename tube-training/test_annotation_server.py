import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from PIL import Image
import annotation_server
from dataset import write


class ServerTests(unittest.TestCase):
    def test_http_crop_and_export(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            (root / 'labeling.html').write_text('<html>test</html>')
            (root / 'images').mkdir()
            manifest = []
            metadata = {}
            for index, split in enumerate(('train', 'val'), start=1):
                tube = f'tube_{index}'
                image_path = f'images/{tube}.jpg'
                Image.new('RGB', (200, 100), 'white').save(root / image_path)
                manifest.append({'image_id': tube, 'tube_id': tube,
                                 'image': image_path, 'source_sha256': tube})
                metadata[tube] = {'label_type': 'small', 'split': split, 'group_id': tube}
            write(root / 'manifest.json', manifest)
            write(root / 'tube_meta.json', metadata)
            original_root = annotation_server.ROOT
            annotation_server.ROOT = root
            server = ThreadingHTTPServer(('127.0.0.1', 0), annotation_server.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(method, path, value=None):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=10)
                try:
                    connection.request(method, path, body=json.dumps(value) if value is not None else None,
                                       headers={'Content-Type': 'application/json'})
                    response = connection.getresponse()
                    result = json.loads(response.read())
                    self.assertEqual(response.status, 200, result)
                    return result
                finally:
                    connection.close()
            def post(path, value):
                return request('POST', path, value)
            try:
                self.assertEqual(len(request('GET', '/api/state')['manifest']), 2)
                for index in (1, 2):
                    result = post('/api/crop', {
                        'image_id': f'tube_{index}', 'field': 'machine',
                        'rotation': 90, 'box': [10, 20, 80, 150],
                        'text': 'UP123', 'status': 'verified',
                    })
                    with Image.open(root / 'crops' / (result['id'] + '.png')) as crop:
                        self.assertEqual(crop.size, (70, 130))
                exported = post('/api/export', {})
                self.assertEqual(exported['training_crops'], 1)
                self.assertEqual(exported['validation_crops'], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                annotation_server.ROOT = original_root


if __name__ == '__main__':
    unittest.main()
