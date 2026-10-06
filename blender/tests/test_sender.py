import json
import subprocess
import sys
from pathlib import Path
import pytest
from spatial_pointer.core import parse_packet
from spatial_pointer.transport import UDPReceiver
from tools.udp_sender import make_packet

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('pattern', ['orbit', 'line', 'static'])
def test_sender_matches_wire_contract(pattern):
    for t in (0, .3, 1, 3.5, 5.5):
        raw = json.dumps(make_packet(t, 10, 'sender-test', pattern=pattern)).encode()
        assert parse_packet(raw).seq == 10


def test_sender_grab_demo_begins_released_for_safe_arming():
    assert make_packet(0, 0, 's', grab_demo=True)['grab'] is False
    assert make_packet(1, 60, 's', grab_demo=True)['grab'] is True
    assert make_packet(3.5, 210, 's', grab_demo=True)['grab'] is False


def test_sender_clutch_demo_and_token():
    assert not make_packet(4, 1, 's', clutch_demo=True)['clutch']
    assert make_packet(6, 2, 's', clutch_demo=True)['clutch']
    assert make_packet(0, 0, 's', token='abc')['token'] == 'abc'


def test_actual_cli_sender_to_actual_receiver():
    r = UDPReceiver('127.0.0.1', 0)
    try:
        proc = subprocess.run([
            sys.executable, str(ROOT/'tools'/'udp_sender.py'),
            '--port', str(r.address[1]), '--duration', '.16', '--hz', '30',
        ], capture_output=True, text=True, timeout=5)
        assert proc.returncode == 0, proc.stderr
        received = r.poll()
        assert len(received) >= 3
        seqs = [p.seq for p, _ in received]
        assert seqs == sorted(set(seqs))
        assert not received[-1][0].grab
        assert not received[-1][0].follow
    finally:
        r.close()
