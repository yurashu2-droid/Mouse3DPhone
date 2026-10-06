#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Standard-library PC pose simulator. Not a smartphone motion tracker.

Example: python tools/udp_sender.py --duration 30 --clutch-demo
Start the Blender add-on's UDP receiver first. No response/ACK is expected.
"""
from __future__ import annotations
import argparse
import json
import math
import socket
import sys
import time
import uuid


def make_packet(t: float, seq: int, session: str, *, pattern='orbit',
                amplitude=.6, token='', clutch_demo=False, grab_demo=False,
                space='BLENDER') -> dict:
    phase = t * .8
    if pattern == 'orbit':
        position = [amplitude*(math.cos(phase)-1), amplitude*math.sin(phase),
                    amplitude*.4*math.sin(phase*2)]
        angle = .65*math.sin(phase)
    elif pattern == 'line':
        position = [amplitude*math.sin(phase), 0.0, 0.0]
        angle = 0.0
    elif pattern == 'static':
        position, angle = [0.0, 0.0, 0.0], 0.0
    else:
        raise ValueError(f'Unknown pattern: {pattern}')
    return {
        'v': 1, 'session': session, 'seq': seq,
        'position': position,
        'rotation': [math.cos(angle/2), 0.0, 0.0, math.sin(angle/2)],
        'space': space,
        'clutch': not (clutch_demo and 3.0 <= t % 8.0 < 5.0),
        'grab': bool(grab_demo and .5 <= t % 4.0 < 2.5),
        'tracking': True,
        'token': token,
    }


def _finite(minimum, maximum):
    def convert(raw):
        value = float(raw)
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise argparse.ArgumentTypeError(f'Expected a finite number from {minimum} to {maximum}')
        return value
    return convert


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1', help='Blender PC IPv4 address (default: this PC)')
    parser.add_argument('--port', type=int, default=5005)
    parser.add_argument('--token', default='', help='Pairing token, required only for LAN mode')
    parser.add_argument('--duration', type=_finite(0, 86400), default=30.0, help='Seconds; 0 runs until Ctrl+C')
    parser.add_argument('--hz', type=_finite(1, 120), default=60.0)
    parser.add_argument('--amplitude', type=_finite(.01, 100), default=.6)
    parser.add_argument('--pattern', choices=['orbit', 'line', 'static'], default='orbit')
    parser.add_argument('--space', choices=['BLENDER', 'ARKIT'], default='BLENDER')
    parser.add_argument('--clutch-demo', action='store_true', help='Pause following during seconds 3..5 of each 8-second cycle')
    parser.add_argument('--grab-demo', action='store_true', help='WARNING: periodically grab/move the selected Blender object')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('--port must be 1..65535')
    seq, start = 0, time.monotonic()
    session = uuid.uuid4().hex
    next_frame = start
    target = (args.host, args.port)
    print(f'PC SIMULATOR -> {args.host}:{args.port} | {args.pattern} | {args.hz:g} Hz')
    print('Sending only; this is not proof of a Blender connection. Ctrl+C stops.')
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                while True:
                    now = time.monotonic()
                    elapsed = now-start
                    if args.duration and elapsed >= args.duration:
                        break
                    data = make_packet(elapsed, seq, session, pattern=args.pattern,
                        amplitude=args.amplitude, token=args.token, clutch_demo=args.clutch_demo,
                        grab_demo=args.grab_demo, space=args.space)
                    sock.sendto(json.dumps(data, allow_nan=False).encode('utf-8'), target)
                    seq += 1
                    next_frame = max(next_frame + 1.0/args.hz, now)
                    time.sleep(max(0.0, next_frame-time.monotonic()))
            except KeyboardInterrupt:
                pass
            finally:
                # Send an explicit release/freeze before closing; the receiver also
                # independently times out if this packet is lost.
                end = make_packet(time.monotonic()-start, seq, session, pattern=args.pattern,
                                  amplitude=args.amplitude, token=args.token, space=args.space)
                end.update(grab=False, clutch=False)
                sock.sendto(json.dumps(end, allow_nan=False).encode('utf-8'), target)
        print(f'Sent {seq+1} packets. Released and frozen; no response/ACK is expected.')
        return 0
    except (OSError, ValueError) as exc:
        print(f'UDP sender error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
