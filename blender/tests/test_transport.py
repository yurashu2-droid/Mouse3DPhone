import json
import socket
import time
import pytest
from spatial_pointer.transport import UDPReceiver


def msg(seq=0, **kw):
    d = dict(v=1, session='socket-test', seq=seq,
             position=[1, 2, 3], rotation=[1, 0, 0, 0])
    d.update(kw)
    return json.dumps(d).encode()


def test_loopback_socket_receives_valid_packet_and_closes():
    r = UDPReceiver('127.0.0.1', 0)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(msg(), r.address)
        time.sleep(.005)
        items = r.poll()
        assert len(items) == 1
        assert items[0][0].pose.position == (1, 2, 3)
    port = r.address[1]
    r.close()
    r.close()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', port))


def test_poll_is_bounded_and_nonblocking():
    r = UDPReceiver('127.0.0.1', 0)
    try:
        assert r.poll() == []
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            for i in range(8):
                s.sendto(msg(i), r.address)
            time.sleep(.005)
            assert len(r.poll(limit=3)) == 3
            assert len(r.poll()) == 5
    finally:
        r.close()


def test_oversized_bad_json_and_wrong_token_are_dropped():
    r = UDPReceiver('127.0.0.1', 0, token='pair-code')
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            for data in [b'x' * 6000, b'{', msg(token='wrong'), msg(token='pair-code')]:
                s.sendto(data, r.address)
            time.sleep(.005)
        assert len(r.poll()) == 1
        assert r.rejected == 3
    finally:
        r.close()
