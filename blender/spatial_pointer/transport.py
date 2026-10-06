# SPDX-License-Identifier: GPL-3.0-or-later
"""Small, bounded, non-blocking UDP receiver. Contains no Blender calls."""
from __future__ import annotations
import socket
from .core import MAX_PACKET_BYTES, PacketError, parse_packet


class UDPReceiver:
    def __init__(self, host: str = '127.0.0.1', port: int = 5005, token: str = ''):
        self.socket = None
        self.token = token
        self.rejected = 0
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Do not enable SO_REUSEADDR: a second receiver should fail clearly.
            sock.setblocking(False)
            sock.bind((host, port))
            self.address = sock.getsockname()
            self.socket = sock
        except OSError:
            sock.close()
            raise

    def poll(self, limit: int = 64) -> list:
        if self.socket is None:
            return []
        packets = []
        for _ in range(max(0, min(limit, 256))):
            try:
                data, peer = self.socket.recvfrom(MAX_PACKET_BYTES + 1)
            except BlockingIOError:
                break
            except OSError as exc:
                # Windows can signal oversized UDP datagrams with WSAEMSGSIZE.
                if getattr(exc, 'winerror', None) == 10040 or exc.errno == 90:
                    self.rejected += 1
                    continue
                raise
            try:
                packets.append((parse_packet(data, self.token), peer))
            except PacketError:
                self.rejected += 1
        return packets

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None
