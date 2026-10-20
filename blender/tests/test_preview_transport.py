import http.client
import json
import socket
import struct
import time
import zlib

import pytest

from spatial_pointer.preview_transport import PreviewServer, PreviewState, encode_rgba_png


def test_png_preserves_rgba_and_flips_gpu_rows():
    # GPU's first row is the bottom row. PNG's first row must be the top row.
    pixels = bytes((255, 0, 0, 255, 0, 255, 0, 128,
                    0, 0, 255, 64, 255, 255, 255, 0))
    png = encode_rgba_png(2, 2, pixels, bottom_up=True)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    chunks = {}
    offset = 8
    while offset < len(png):
        size, kind = struct.unpack('!I4s', png[offset:offset + 8])
        data = png[offset + 8:offset + 8 + size]
        crc, = struct.unpack('!I', png[offset + 8 + size:offset + 12 + size])
        assert crc == zlib.crc32(kind + data) & 0xffffffff
        chunks[kind] = chunks.get(kind, b'') + data
        offset += size + 12
    assert struct.unpack('!IIBBBBB', chunks[b'IHDR']) == (2, 2, 8, 6, 0, 0, 0)
    assert zlib.decompress(chunks[b'IDAT']) == b'\x00' + pixels[8:] + b'\x00' + pixels[:8]
    assert chunks[b'IEND'] == b''


@pytest.mark.parametrize('width,height,rgba', [(0, 1, b''), (1, 0, b''), (2, 1, b'1234')])
def test_png_rejects_invalid_dimensions_or_short_buffer(width, height, rgba):
    with pytest.raises(ValueError):
        encode_rgba_png(width, height, rgba)


def request(server, path, authorization=None):
    connection = http.client.HTTPConnection(*server.address, timeout=1)
    try:
        headers = {'Authorization': authorization} if authorization else {}
        connection.request('GET', path, headers=headers)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_server_requires_header_token_and_serves_only_snapshots(capsys):
    state = PreviewState()
    server = PreviewServer('127.0.0.1', 0, 'secret-pair-token', state)
    try:
        for path in ('/frame.png', '/status'):
            for auth in (None, 'Bearer wrong', 'Basic secret-pair-token'):
                assert request(server, path, auth)[0] == 401
        assert request(server, '/frame.png?token=secret-pair-token')[0] == 401
        assert not state.wants_frame(), 'Unauthorized requests must not schedule GPU work'
        status, headers, body = request(server, '/frame.png', 'Bearer secret-pair-token')
        assert status == 503
        assert headers['Cache-Control'] == 'no-store'
        assert state.wants_frame()
        now = time.monotonic()
        state.publish(b'png-snapshot', now=now)
        status, headers, body = request(server, '/frame.png', 'Bearer secret-pair-token')
        assert (status, headers['Content-Type'], body) == (200, 'image/png', b'png-snapshot')
        status, _, body = request(server, '/status', 'Bearer secret-pair-token')
        info = json.loads(body)
        assert status == 200 and info['ready'] and info['frames'] == 1
        assert 0 <= info['age_seconds'] < 1
        assert request(server, '/unknown', 'Bearer secret-pair-token')[0] == 404
        assert request(server, '/frame.png?token=secret-pair-token', 'Bearer secret-pair-token')[0] == 404
        state.unavailable('Open a 3D View')
        assert request(server, '/frame.png', 'Bearer secret-pair-token')[0] == 503
        info = json.loads(request(server, '/status', 'Bearer secret-pair-token')[2])
        assert info == {'ready': False, 'message': 'Open a 3D View', 'frames': 1, 'age_seconds': None}
    finally:
        server.close()
    assert 'secret-pair-token' not in capsys.readouterr().err


def test_demand_expires_and_shutdown_releases_port_even_with_idle_client():
    state = PreviewState()
    server = PreviewServer('127.0.0.1', 0, 'pair-token', state)
    address = server.address
    idle_client = socket.create_connection(address, timeout=1)
    try:
        request(server, '/status', 'Bearer pair-token')
        assert state.wants_frame()
        assert not state.wants_frame(now=time.monotonic() + 4)
        started = time.monotonic()
        server.close()
        server.close()
        assert time.monotonic() - started < 1
        assert not server.thread.is_alive()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(address)
    finally:
        idle_client.close()
        server.close()


def test_empty_token_never_creates_unauthenticated_listener():
    with pytest.raises(ValueError):
        PreviewServer('127.0.0.1', 0, '', PreviewState())


def test_published_frame_is_immutable_and_old_frames_are_not_served():
    state = PreviewState()
    source = bytearray(b'original')
    state.publish(source, now=10)
    source[:] = b'changed!'
    frame, status = state.snapshot(now=10.5)
    assert frame == b'original'
    assert status['ready'] and status['age_seconds'] == .5
    frame, status = state.snapshot(now=12.1)
    assert frame is None and not status['ready']
    assert status['frames'] == 1 and status['age_seconds'] == pytest.approx(2.1)
