"""Check packets emitted by actual Swift code against the shipped Blender parser."""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blender'))
from spatial_pointer.core import SessionGate, parse_packet

raw = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert len(raw) == 13
packets = [parse_packet(json.dumps(item).encode(), token='fixture-token') for item in raw]
for index, packet in enumerate(packets[:-1]):
    assert packet.seq == index
    assert packet.session == packets[0].session
    assert type(raw[index]['clutch']) is bool
    assert type(raw[index]['grab']) is bool
    assert type(raw[index]['tracking']) is bool
assert packets[-1].seq == 0 and packets[-1].session != packets[0].session
assert packets[3].pose.position == (0.1, 0.3, 0.2)
assert math.isclose(packets[3].pose.rotation[0], math.sqrt(.5))
assert math.isclose(packets[3].pose.rotation[3], math.sqrt(.5))
assert abs(packets[3].pose.rotation[2]) < 1e-12
assert packets[4].grab and packets[4].follow
assert packets[5].grab and not packets[5].follow
assert not packets[6].grab and not packets[6].tracking
assert all(not packet.grab for packet in packets[7:10])
assert packets[10].grab
assert not packets[11].grab and not packets[11].tracking
gate = SessionGate()
peer = ('192.168.1.10', 50001)
for index, packet in enumerate(packets[:-1]):
    assert gate.accept(packet, peer, index / 60)
assert not gate.accept(packets[-1], peer, .3)
assert gate.accept(packets[-1], peer, 1.1)  # New AR world after .85 s hold-off.
print('Swift -> Blender protocol: PASS (13 packets, basis/quaternion/clutch/recovery/session gate)')
