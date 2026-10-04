"""Serve a private author-review UI on loopback; never invokes any model."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import hmac
import json
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.rq2.human_review_ui import ReviewStore, load_source, demo_source, REVIEW


def make_handler(store, port):
    token = secrets.token_urlsafe(32)
    assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'application/javascript'),
              '/style.css': ('style.css', 'text/css')}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, value, content_type='application/json'):
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8') if content_type == 'application/json' else value
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {'error': 'Loopback only'})
            path = urlsplit(self.path)
            try:
                if path.path in assets:
                    name, mime = assets[path.path]
                    return self.send(200, (ROOT / 'apps/rq2_review' / name).read_bytes(), mime)
                if path.path == '/api/state':
                    return self.send(200, {**store.state(), 'token': token})
                if path.path == '/api/case':
                    index = int(parse_qs(path.query)['index'][0])
                    return self.send(200, store.case(index))
                if path.path == '/api/summary':
                    return self.send(200, store.summary())
                return self.send(404, {'error': 'Not found'})
            except (ValueError, KeyError, TypeError):
                return self.send(400, {'error': 'Phiếu không hợp lệ.'})

        def do_POST(self):
            if (not self.allowed() or not hmac.compare_digest(self.headers.get('X-Review-Token', ''), token) or
                    self.headers.get('Origin') not in (None, f'http://127.0.0.1:{port}', f'http://localhost:{port}')):
                return self.send(403, {'error': 'Invalid local session'})
            if self.path != '/api/save' or self.headers.get('Content-Type') != 'application/json':
                return self.send(400, {'error': 'Invalid save request'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 64000:
                    raise ValueError('Request quá lớn hoặc rỗng.')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('Invalid save request')
                return self.send(200, store.save(body))
            except (ValueError, KeyError, TypeError) as error:
                return self.send(400, {'error': str(error)})
            except OSError:
                return self.send(500, {'error': 'Chưa lưu được vào ổ đĩa. Giữ phiếu mở và thử lưu lại.'})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=9411)
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    source = demo_source() if args.demo else load_source()
    directory = REVIEW.with_name('author_review_demo') if args.demo else REVIEW
    store = ReviewStore(*source, directory=directory, demo=args.demo)
    server = HTTPServer(('127.0.0.1', args.port), make_handler(store, args.port))
    print(f'Review UI: http://127.0.0.1:{args.port} | local only | demo={args.demo}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
