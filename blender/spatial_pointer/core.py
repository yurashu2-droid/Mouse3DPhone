# SPDX-License-Identifier: GPL-3.0-or-later
"""Dependency-free pose math and the version-1 spatial input protocol.

Vectors use Blender's right-handed X-right, Y-forward, Z-up basis.
Quaternions are ALWAYS (w, x, y, z), including on the wire.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import json
import math
from typing import Iterable

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]
MAX_PACKET_BYTES = 4096


class PacketError(ValueError):
    """Untrusted data failed validation; the receiver should discard it."""


@dataclass(frozen=True)
class Pose:
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Quat = (1.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class Packet:
    pose: Pose
    session: str
    seq: int
    follow: bool = True
    grab: bool = False
    tracking: bool = True
    space: str = 'BLENDER'


def qmul(a: Quat, b: Quat) -> Quat:
    w, x, y, z = a
    W, X, Y, Z = b
    return (w*W-x*X-y*Y-z*Z,
            w*X+x*W+y*Z-z*Y,
            w*Y-x*Z+y*W+z*X,
            w*Z+x*Y-y*X+z*W)


def qconj(q: Quat) -> Quat:
    return (q[0], -q[1], -q[2], -q[3])


def qnormalize(q: Iterable[float]) -> Quat:
    q = tuple(q)
    n = math.sqrt(sum(x*x for x in q))
    if len(q) != 4 or not math.isfinite(n) or n < 1e-12:
        raise ValueError('Quaternion must have four finite, nonzero components')
    return tuple(x/n for x in q)


def qaxis(axis: Vec3, angle: float) -> Quat:
    n = math.sqrt(sum(x*x for x in axis))
    if n < 1e-12:
        raise ValueError('Rotation axis must be nonzero')
    s = math.sin(angle/2) / n
    return (math.cos(angle/2), axis[0]*s, axis[1]*s, axis[2]*s)


def qrotate(q: Quat, v: Vec3) -> Vec3:
    r = qmul(qmul(q, (0.0, *v)), qconj(q))
    return r[1:]


def to_blender(pose: Pose, space: str) -> Pose:
    if space == 'BLENDER':
        return pose
    if space != 'ARKIT':
        raise PacketError('space must be BLENDER or ARKIT')
    # ARKit: +Y up, -Z forward. C is a +90 degree rotation about X.
    c = (math.sqrt(.5), math.sqrt(.5), 0.0, 0.0)
    x, y, z = pose.position
    return Pose((x, -z, y), qnormalize(qmul(qmul(c, pose.rotation), qconj(c))))


def _finite_vector(value, n: int, bound: float, field: str) -> tuple:
    if not isinstance(value, list) or len(value) != n:
        raise PacketError(f'{field} must be an array of length {n}')
    out = []
    for x in value:
        if type(x) not in (int, float):
            raise PacketError(f'{field} contains a non-number')
        try:
            f = float(x)
        except (OverflowError, ValueError) as exc:
            raise PacketError(f'{field} overflows') from exc
        if not math.isfinite(f) or abs(f) > bound:
            raise PacketError(f'{field} contains a non-finite or excessive value')
        out.append(f)
    return tuple(out)


def _bool(obj, key: str, default: bool) -> bool:
    value = obj.get(key, default)
    if type(value) is not bool:
        raise PacketError(f'{key} must be true or false')
    return value


def _no_constant(value):
    raise PacketError(f'{value} is not valid finite JSON input')


def parse_packet(raw: bytes, token: str = '') -> Packet:
    """Validate a single datagram, never eval/execute it, and convert its basis."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_PACKET_BYTES:
        raise PacketError('Empty or oversized packet')
    try:
        obj = json.loads(raw.decode('utf-8'), parse_constant=_no_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PacketError('Invalid JSON') from exc
    if not isinstance(obj, dict):
        raise PacketError('Packet must be an object')
    if type(obj.get('v')) is not int or obj['v'] != 1:
        raise PacketError('v must be integer 1')
    session = obj.get('session')
    if (not isinstance(session, str) or not 1 <= len(session) <= 64
            or not all(c.isascii() and (c.isalnum() or c in '-_.') for c in session)):
        raise PacketError('session must be 1..64 ASCII letters/digits/-/./_')
    seq = obj.get('seq')
    if type(seq) is not int or not 0 <= seq < 2**63:
        raise PacketError('seq must be a non-negative 63-bit integer')
    if token:
        got = obj.get('token')
        if not isinstance(got, str):
            raise PacketError('Pairing token mismatch')
        try:
            matched = hmac.compare_digest(got.encode('utf-8'), token.encode('utf-8'))
        except UnicodeError as exc:
            raise PacketError('Invalid token encoding') from exc
        if not matched:
            raise PacketError('Pairing token mismatch')
    p = _finite_vector(obj.get('position'), 3, 100000, 'position')
    q = _finite_vector(obj.get('rotation', [1, 0, 0, 0]), 4, 1e6, 'rotation')
    try:
        q = qnormalize(q)
    except ValueError as exc:
        raise PacketError(str(exc)) from exc
    space = obj.get('space', 'BLENDER')
    pose = to_blender(Pose(p, q), space)
    return Packet(pose, session, seq, _bool(obj, 'clutch', True),
                  _bool(obj, 'grab', False), _bool(obj, 'tracking', True), space)


class PoseMapper:
    """Relative position/rotation mapping with a no-jump clutch.

    Losing tracking, disabling follow, changing gain or recentering invalidates
    the input anchor. The next good sample becomes the new input reference;
    the current output is kept, rather than jumping to the incoming position.
    """
    def __init__(self, initial: Pose = Pose()):
        self.target = initial
        self._anchor_in = None
        self._anchor_out = initial
        self._gain = None

    def recenter(self) -> None:
        self._anchor_in = None

    def set_target(self, pose: Pose) -> None:
        self.target = pose
        self._anchor_out = pose
        self.recenter()

    def update(self, pose: Pose, follow: bool, gain: float,
               tracking: bool = True) -> Pose:
        if not math.isfinite(gain) or gain <= 0:
            raise ValueError('gain must be positive and finite')
        if not follow or not tracking:
            self.recenter()
            return self.target
        if self._anchor_in is None or gain != self._gain:
            self._anchor_in, self._anchor_out, self._gain = pose, self.target, gain
            return self.target
        p = tuple(o + gain*(a-b) for o, a, b in zip(
            self._anchor_out.position, pose.position, self._anchor_in.position))
        delta = qmul(pose.rotation, qconj(self._anchor_in.rotation))
        q = qnormalize(qmul(delta, self._anchor_out.rotation))
        self.target = Pose(p, q)
        return self.target


def smooth_pose(current: Pose, target: Pose, dt: float, half_life: float) -> Pose:
    if dt <= 0:
        return current
    if half_life <= 0:
        return target
    alpha = 1.0 - math.pow(.5, dt / half_life)
    p = tuple(a + alpha*(b-a) for a, b in zip(current.position, target.position))
    bq = target.rotation
    if sum(a*b for a, b in zip(current.rotation, bq)) < 0:
        bq = tuple(-v for v in bq)
    q = qnormalize(tuple(a + alpha*(b-a) for a, b in zip(current.rotation, bq)))
    return Pose(p, q)


def advance_keyboard(pose: Pose, keys: set[str], dt: float,
                     speed: float, rotation_speed: float, precision: bool) -> Pose:
    """Integrate test input. Keyboard motion is NOT phone tracking."""
    dt = min(max(dt, 0.0), .05)
    factor = .15 if precision else 1.0
    move = (int('D' in keys)-int('A' in keys),
            int('W' in keys)-int('S' in keys),
            int('E' in keys)-int('Q' in keys))
    n = max(1.0, math.sqrt(sum(v*v for v in move)))
    p = tuple(a + v/n*speed*factor*dt for a, v in zip(pose.position, move))
    q = pose.rotation
    rotations = (((1, 0, 0), 'I', 'K'), ((0, 0, 1), 'J', 'L'), ((0, 1, 0), 'U', 'O'))
    for axis, pos, neg in rotations:
        angle = (int(pos in keys)-int(neg in keys)) * rotation_speed * factor * dt
        if angle:
            q = qmul(q, qaxis(axis, angle))
    return Pose(p, qnormalize(q))


class SessionGate:
    """Only the live sender/session and increasing sequence numbers may drive."""
    def __init__(self, timeout: float = .75):
        self.timeout = timeout
        self.identity = None
        self.last_seen = None
        self.last_seq = -1
        self.generation = 0

    def stale(self, now: float) -> bool:
        return self.last_seen is None or now-self.last_seen >= self.timeout

    def accept(self, packet: Packet, peer: tuple, now: float) -> bool:
        identity = (peer, packet.session)
        if self.identity is None or self.stale(now):
            self.identity, self.last_seq = identity, -1
            self.generation += 1
        if identity != self.identity or packet.seq <= self.last_seq:
            return False
        self.last_seq, self.last_seen = packet.seq, now
        return True
