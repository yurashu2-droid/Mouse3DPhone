# SPDX-License-Identifier: GPL-3.0-or-later
"""In-memory PNG snapshots and paired HTTP transport. No Blender/GPU imports.

Only immutable frame bytes and a short locked status snapshot cross threads.
HTTP handlers never invoke a producer, so a slow viewer cannot hold up input.
"""
from __future__ import annotations
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
import threading
import time
import zlib


def encode_rgba_png(width: int, height: int, rgba: bytes, *, bottom_up=False) -> bytes:
    """Encode RGBA8, optionally reversing the bottom-first GPU scanlines."""
    if width <= 0 or height <= 0 or len(rgba) != width * height * 4:
        raise ValueError('PNG requires positive dimensions and a complete RGBA8 buffer')

    def chunk(kind, data):
        return (struct.pack('!I', len(data)) + kind + data
                + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff))

    stride = width * 4
    rows = range(height - 1, -1, -1) if bottom_up else range(height)
    scanlines = b''.join(b'\x00' + rgba[row * stride:(row + 1) * stride] for row in rows)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines, level=3))
            + chunk(b'IEND', b''))


class PreviewState:
    """Small mailbox shared by a main-thread producer and HTTP readers."""
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._captured_at = None
        self._requested_at = None
        self._frames = 0
        self._message = 'Waiting for a phone viewer and a visible 3D View'

    def request_frame(self, now=None):
        with self._lock:
            self._requested_at = time.monotonic() if now is None else now

    def wants_frame(self, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            return self._requested_at is not None and now - self._requested_at < 2.0

    def publish(self, png: bytes, now=None):
        frame = bytes(png)
        now = time.monotonic() if now is None else now
        with self._lock:
            self._frame, self._captured_at = frame, now
            self._frames += 1
            self._message = 'Pointer view ready'

    def unavailable(self, message):
        with self._lock:
            self._frame = self._captured_at = None
            self._message = message

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            frame, captured_at = self._frame, self._captured_at
            frames, message = self._frames, self._message
        age = max(0.0, now - captured_at) if captured_at is not None else None
        if age is not None and age >= 2.0:
            frame, message = None, 'Waiting for a visible 3D View to refresh the image'
        return frame, dict(ready=frame is not None, message=message,
                          frames=frames, age_seconds=age)


class _PreviewHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False

    def get_request(self):
        client, address = super().get_request()
        client.settimeout(.5)
        return client, address


class PreviewServer:
    """A read-only server with a token copied at construction, never in a URL."""
    def __init__(self, host: str, port: int, token: str, state: PreviewState):
        if not token:
            raise ValueError('Preview requires a pairing token')
        expected = ('Bearer ' + token).encode('utf-8')

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                # The default logger includes the request URL. Never log requests.
                pass

            def _reply(self, status, content_type, body):
                try:
                    self.send_response(status)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(body)
                except (ConnectionError, TimeoutError, OSError):
                    pass

            def do_GET(self):
                authorization = self.headers.get_all('Authorization', [])
                candidate = authorization[0].encode('utf-8') if len(authorization) == 1 else b''
                if not hmac.compare_digest(candidate, expected):
                    self._reply(401, 'text/plain; charset=utf-8', b'Pairing token required')
                    return
                if self.path not in {'/frame.png', '/status'}:
                    self._reply(404, 'text/plain; charset=utf-8', b'Not found')
                    return
                state.request_frame()
                frame, status = state.snapshot()
                if self.path == '/status':
                    self._reply(200, 'application/json', json.dumps(status).encode('utf-8'))
                elif frame is None:
                    self._reply(503, 'text/plain; charset=utf-8', status['message'].encode('utf-8'))
                else:
                    self._reply(200, 'image/png', frame)

        self.server = _PreviewHTTPServer((host, port), Handler)
        self.address = self.server.server_address
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .05},
                                       name='SpatialPointerPreview', daemon=True)
        self._closed = False
        try:
            self.thread.start()
        except Exception:
            self.server.server_close()
            raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=.5)
