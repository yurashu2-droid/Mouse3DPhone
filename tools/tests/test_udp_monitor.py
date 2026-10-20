import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from udp_monitor import Monitor, open_udp


class MonitorTests(unittest.TestCase):
    def test_valid_and_invalid_packets_do_not_expose_payload_or_token(self):
        monitor = Monitor()
        packet = dict(v=1, session='test', seq=7, position=[1, 2, 3],
                      rotation=[1, 0, 0, 0], space='ARKIT', tracking=True,
                      clutch=False, grab=False, token='secret-do-not-log')
        monitor.record(json.dumps(packet).encode(), ('192.168.1.174', 43210))
        monitor.record(b'not-json-secret-do-not-log', ('192.168.1.174', 43210))
        result = monitor.snapshot()
        self.assertEqual((result['received'], result['valid'], result['invalid']), (2, 1, 1))
        self.assertEqual(result['source'], '192.168.1.174:43210')
        self.assertEqual(result['packet']['seq'], 7)
        self.assertNotIn('secret-do-not-log', json.dumps(result))
        self.assertNotIn('token', result['packet'])

    def test_udp_receive_and_port_conflict(self):
        with open_udp('127.0.0.1', 0) as receiver:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(b'probe', receiver.getsockname())
            self.assertEqual(receiver.recvfrom(65535)[0], b'probe')
            with self.assertRaises(OSError):
                with open_udp(*receiver.getsockname()):
                    pass

    def test_dashboard_receives_real_udp_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'status.json'
            process = subprocess.Popen([
                sys.executable, str(Path(__file__).resolve().parents[1] / 'udp_monitor.py'),
                '--bind', '127.0.0.1', '--port', '0', '--http-port', '0',
                '--report', str(report), '--duration', '10'])
            try:
                deadline = time.monotonic() + 5
                while not report.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                state = json.loads(report.read_text(encoding='utf-8'))
                base = f"http://127.0.0.1:{state['http_port']}"
                with urllib.request.urlopen(base, timeout=2) as response:
                    self.assertIn('UDP受信テスト', response.read().decode())
                packet = dict(v=1, session='test', seq=9, position=[1, 2, 3],
                              token='secret-from-network')
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(json.dumps(packet).encode(), ('127.0.0.1', state['port']))
                    sender.sendto(b'bad-secret-from-network', ('127.0.0.1', state['port']))
                while time.monotonic() < deadline:
                    with urllib.request.urlopen(base + '/status', timeout=2) as response:
                        raw_status = response.read()
                    status = json.loads(raw_status)
                    if status['received'] == 2:
                        break
                    time.sleep(0.05)
                self.assertEqual((status['received'], status['valid'], status['invalid']), (2, 1, 1))
                self.assertNotIn(b'secret-from-network', raw_status)
                request = urllib.request.Request(base + '/stop', method='POST',
                                                 headers={'X-Monitor-Stop': '1'})
                with urllib.request.urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                self.assertEqual(process.wait(timeout=3), 0)
                final_report = report.read_text(encoding='utf-8')
                self.assertEqual(json.loads(final_report)['status'], 'stopped')
                self.assertNotIn('secret-from-network', final_report)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
