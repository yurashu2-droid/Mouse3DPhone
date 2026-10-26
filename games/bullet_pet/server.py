"""LAN-only prototype server: python games/bullet_pet/server.py [--port 8767]."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import parse_qs, urlsplit

from core import Game, InputError

WEB = Path(__file__).resolve().parent / 'web'


def addresses():
    candidates = set()
    try:
        candidates.update(a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))
            candidates.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in candidates if not a.startswith(('127.', '169.254.')))


class PetServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = os.name != 'nt'

    def __init__(self, address, code=None):
        self.code = code or f'{secrets.randbelow(1000000):06d}'
        self.game = Game(time.monotonic())
        self.stopping = threading.Event()
        super().__init__(address, Handler)

    def simulation(self):
        last = time.monotonic()
        while not self.stopping.wait(1/60):
            now = time.monotonic()
            self.game.step(now-last, now)
            last = now

    def server_close(self):
        self.stopping.set()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, *args):
        pass  # No pairing codes or request bodies in logs.

    def _reply(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(body)

    def _local(self):
        return ipaddress.ip_address(self.client_address[0]).is_loopback

    def _authorized(self, code):
        return isinstance(code, str) and hmac.compare_digest(code.encode(), self.server.code.encode())

    def do_GET(self):
        target = urlsplit(self.path)
        route = target.path
        code = parse_qs(target.query).get('code', [''])[0]
        try:
            if route == '/api/config':
                if not self._local():
                    return self._reply(403, {'error': 'PC上で開いてください。'})
                port = self.server.server_port
                return self._reply(200, dict(code=self.server.code, port=port, version='0.4.0',
                                             urls=[f'http://{a}:{port}/phone?code={self.server.code}' for a in addresses()]))
            if route in ('/api/events', '/api/state'):
                if not self._authorized(code):
                    return self._reply(403, {'error': '接続コードを確認してください。'})
                if route.endswith('state'):
                    return self._reply(200, self.server.game.snapshot(time.monotonic()))
                return self._events()
            static = {'/': 'desktop.html', '/phone': 'phone.html'}
            for name in ('desktop.js', 'phone.js', 'shared.js', 'style.css'):
                static['/assets/'+name] = name
            if route not in static:
                return self._reply(404, {'error': 'Not found'})
            file = WEB / static[route]
            if not file.is_file():
                return self._reply(503, {'error': '画面ファイルを準備しています。'})
            content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            if file.suffix == '.js':
                content_type = 'text/javascript'
            self._reply(200, file.read_bytes(), content_type+'; charset=utf-8')
        except (BrokenPipeError, ConnectionError, OSError):
            self.close_connection = True

    def _events(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(b'retry: 1000\n\n')
        self.wfile.flush()
        while not self.server.stopping.is_set():
            payload = json.dumps(self.server.game.snapshot(time.monotonic()), separators=(',', ':'),
                                 ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.wfile.write(b'event: state\ndata: '+payload+b'\n\n')
            self.wfile.flush()
            self.server.stopping.wait(1/30)

    def do_POST(self):
        route = urlsplit(self.path).path
        try:
            if route not in ('/api/input', '/api/reset', '/api/shutdown'):
                return self._reply(404, {'error': 'Not found'})
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                return self._reply(403, {'error': '別サイトからの操作は許可されていません。'})
            if self.headers.get_content_type() != 'application/json':
                self.close_connection = True
                return self._reply(415, {'error': 'JSONが必要です。'})
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                self.close_connection = True
                return self._reply(413, {'error': '入力が長すぎます。'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('JSON object required')
            if not self._authorized(data.get('code')):
                return self._reply(403, {'error': '接続コードを確認してください。'})
            if route in ('/api/reset', '/api/shutdown'):
                if not self._local():
                    return self._reply(403, {'error': 'PCからやり直してください。'})
                if route == '/api/reset':
                    self.server.game.reset(time.monotonic())
                else:
                    self._reply(200, {'ok': True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
            else:
                self.server.game.input(data, time.monotonic())
            self._reply(200, {'ok': True})
        except InputError as error:
            self._reply(error.status, {'error': str(error)})
        except (ValueError, TypeError, UnicodeError, OverflowError):
            self._reply(400, {'error': '入力形式を確認してください。'})
        except (BrokenPipeError, ConnectionError, OSError):
            self.close_connection = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--ready-file', type=Path)
    args = parser.parse_args()
    server = PetServer((args.host, args.port))
    simulation = threading.Thread(target=server.simulation, daemon=True, name='BulletPetRules')
    simulation.start()
    print(f'Bullet Pet: http://127.0.0.1:{server.server_port}/', flush=True)
    print('接続コードはPC画面に表示します。終了はCtrl+C。', flush=True)
    if args.ready_file:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text(json.dumps(dict(pid=os.getpid(), port=server.server_port)), encoding='utf-8')
    try:
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        simulation.join(timeout=1)
        if args.ready_file:
            args.ready_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
