"""Serve only the public setup page and root-certificate profile on the LAN."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ip=json.loads((root/'.env.local-https/config.json').read_text())['ip']
public=root/'tmp/iphone-https-public'
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/': name,mime='index.html','text/html; charset=utf-8'
        elif self.path=='/scanner.mobileconfig': name,mime='scanner.mobileconfig','application/x-apple-aspen-config'
        else: self.send_error(404);return
        data=(public/name).read_bytes()
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
ThreadingHTTPServer((ip,8081),Handler).serve_forever()
