import json
import math
import pytest

from spatial_pointer.core import (
    Pose, PacketError, parse_packet, qmul, qconj, qrotate, qaxis,
    to_blender, PoseMapper, smooth_pose, SessionGate,
)


def wire(**kwargs):
    obj = dict(v=1, session='test-session', seq=0, position=[0, 0, 0],
               rotation=[1, 0, 0, 0], space='BLENDER', clutch=True,
               grab=False, tracking=True)
    obj.update(kwargs)
    return json.dumps(obj).encode()


def packet(**kwargs):
    return parse_packet(wire(**kwargs))


def test_parse_minimum_packet():
    p = packet()
    assert p.pose == Pose()
    assert p.follow and not p.grab and p.tracking
    assert p.seq == 0


def test_normalizes_quaternion():
    assert packet(rotation=[2, 0, 0, 0]).pose.rotation == (1, 0, 0, 0)


@pytest.mark.parametrize('change', [
    {'position': [1, 2]}, {'position': [True, 0, 0]},
    {'position': ['1', 2, 3]}, {'position': [1e8, 0, 0]},
    {'position': [float('inf'), 0, 0]}, {'position': [float('nan'), 0, 0]},
    {'rotation': [0, 0, 0, 0]}, {'rotation': [1, 2, 3]},
    {'rotation': [True, 0, 0, 0]}, {'clutch': 1}, {'grab': 'true'},
    {'tracking': None}, {'space': 'UNKNOWN'}, {'v': 2}, {'v': True},
    {'seq': -1}, {'seq': 1.5}, {'seq': True}, {'seq': 2**64},
    {'session': ''}, {'session': 'a' * 65}, {'session': []},
])
def test_rejects_invalid_packet(change):
    with pytest.raises(PacketError):
        packet(**change)


@pytest.mark.parametrize('raw', [b'[]', b'null', b'{', b'\xff', b'{}', b' ' * 4097])
def test_rejects_bad_wire(raw):
    with pytest.raises(PacketError):
        parse_packet(raw)


def test_token_is_required_only_when_configured():
    parse_packet(wire(token='match-123'), 'match-123')
    with pytest.raises(PacketError):
        parse_packet(wire(token='wrong'), 'match-123')
    with pytest.raises(PacketError):
        parse_packet(wire(), 'match-123')
    parse_packet(wire())


def test_quaternion_rotation():
    q = qaxis((0, 0, 1), math.pi / 2)
    assert qrotate(q, (1, 0, 0)) == pytest.approx((0, 1, 0), abs=1e-10)
    assert qmul(q, qconj(q)) == pytest.approx((1, 0, 0, 0))


def test_arkit_position_and_rotation_basis():
    a = Pose((1, 2, 3), qaxis((0, 1, 0), math.pi / 2))
    b = to_blender(a, 'ARKIT')
    assert b.position == (1, -3, 2)
    assert qrotate(b.rotation, (1, 0, 0)) == pytest.approx((0, 1, 0), abs=1e-10)


def test_first_sample_is_reference_not_a_teleport():
    mapper = PoseMapper(Pose((10, 20, 30)))
    out = mapper.update(Pose((100, 100, 100)), True, 2)
    assert out.position == (10, 20, 30)
    assert mapper.update(Pose((101, 102, 99)), True, 2).position == (12, 24, 28)


def test_clutch_reanchors_translation_without_jump():
    m = PoseMapper()
    m.update(Pose(), True, 1)
    assert m.update(Pose((1, 0, 0)), True, 1).position == (1, 0, 0)
    assert m.update(Pose((50, 0, 0)), False, 1).position == (1, 0, 0)
    assert m.update(Pose((60, 0, 0)), True, 1).position == (1, 0, 0)
    assert m.update(Pose((61, 0, 0)), True, 1).position == (2, 0, 0)


def test_clutch_reanchors_rotation_without_jump():
    m = PoseMapper()
    m.update(Pose(), True, 1)
    q1 = qaxis((0, 0, 1), .3)
    q2 = qaxis((0, 0, 1), 1.2)
    m.update(Pose(rotation=q1), True, 1)
    m.update(Pose(rotation=q2), False, 1)
    assert m.update(Pose(rotation=q2), True, 1).rotation == pytest.approx(q1)


def test_tracking_loss_and_gain_change_reanchor():
    m = PoseMapper()
    m.update(Pose(), True, 1)
    m.update(Pose((2, 0, 0)), True, 1)
    assert m.update(Pose((100, 0, 0)), True, 1, tracking=False).position == (2, 0, 0)
    assert m.update(Pose((101, 0, 0)), True, 1).position == (2, 0, 0)
    assert m.update(Pose((102, 0, 0)), True, 2).position == (2, 0, 0)
    assert m.update(Pose((103, 0, 0)), True, 2).position == (4, 0, 0)


def test_recenter_keeps_target():
    m = PoseMapper(Pose((1, 2, 3)))
    m.update(Pose(), True, 1)
    m.recenter()
    assert m.update(Pose((10, 20, 30)), True, 1).position == (1, 2, 3)


def test_smoothing_half_life_and_zero():
    a, b = Pose(), Pose((2, 4, 8), qaxis((0, 0, 1), math.pi / 2))
    assert smooth_pose(a, b, .05, .05).position == pytest.approx((1, 2, 4))
    assert smooth_pose(a, b, .01, 0) == b
    assert smooth_pose(a, b, 0, .1) == a


def test_smoothing_shortest_quaternion_path():
    out = smooth_pose(Pose(), Pose(rotation=(-1, 0, 0, 0)), .1, .1)
    assert out.rotation == pytest.approx((1, 0, 0, 0))


def test_position_smoothing_is_frame_rate_independent():
    goal = Pose((9, 5, -3))
    a, b = Pose(), Pose()
    for _ in range(60):
        a = smooth_pose(a, goal, 1 / 60, .08)
    for _ in range(120):
        b = smooth_pose(b, goal, 1 / 120, .08)
    assert a.position == pytest.approx(b.position)


def test_gate_rejects_old_sequences_and_competing_senders():
    g = SessionGate(timeout=.75)
    assert g.accept(packet(seq=2), ('127.0.0.1', 1234), 0)
    assert not g.accept(packet(seq=1), ('127.0.0.1', 1234), .1)
    assert not g.accept(packet(seq=2), ('127.0.0.1', 1234), .1)
    assert not g.accept(packet(seq=3), ('127.0.0.1', 9999), .2)
    assert not g.accept(packet(seq=3, session='other'), ('127.0.0.1', 1234), .2)
    assert g.accept(packet(seq=3), ('127.0.0.1', 1234), .3)


def test_gate_timeout_allows_sender_restart():
    g = SessionGate(timeout=.75)
    assert g.accept(packet(seq=42), ('127.0.0.1', 1234), 0)
    assert not g.stale(.5)
    assert g.stale(.8)
    assert g.accept(packet(seq=0, session='new'), ('127.0.0.1', 7777), .8)
    assert g.last_seen == .8


def test_surrogate_in_token_is_a_rejected_packet_not_a_receiver_crash():
    with pytest.raises(PacketError):
        parse_packet(wire(token='\ud800'), 'pair-code')


def test_keyboard_diagonal_speed_and_precision():
    from spatial_pointer.core import advance_keyboard
    straight = advance_keyboard(Pose(), {'D'}, .05, 2, 1, False)
    diagonal = advance_keyboard(Pose(), {'D', 'W', 'E'}, .05, 2, 1, False)
    assert math.sqrt(sum(v*v for v in diagonal.position)) == pytest.approx(straight.position[0])
    fine = advance_keyboard(Pose(), {'D'}, .05, 2, 1, True)
    assert fine.position[0] == pytest.approx(.15 * straight.position[0])


def test_keyboard_rotation_is_unit_and_pause_dt_is_bounded():
    from spatial_pointer.core import advance_keyboard
    p = advance_keyboard(Pose(), {'D', 'J'}, 50, 2, math.pi, False)
    assert p.position[0] == pytest.approx(.1)
    assert sum(v*v for v in p.rotation) == pytest.approx(1)
    assert p.rotation != Pose().rotation
