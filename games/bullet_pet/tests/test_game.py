import http.client
import json
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Game, InputError, ball_radius
from server import PetServer


def packet(client='phone-a', seq=1, **values):
    return dict(client=client, seq=seq, x=0, tiltX=0, tiltY=0,
                active=True, mode='phone', action='join', **values)


def ball(identifier, x, color='cyan', level=1):
    return dict(id=identifier, x=x, y=.5, vx=0, vy=0, color=color, level=level, born=-1)


class GameTests(unittest.TestCase):
    def test_first_input_requires_join_and_other_client_cannot_steer(self):
        g = Game()
        data = packet()
        data['action'] = 'none'
        with self.assertRaises(InputError):
            g.input(data, 0)
        g.input(packet(), 0)
        with self.assertRaises(InputError):
            g.input(packet(client='other'), .1)
        self.assertEqual(g.owner, 'phone-a')

    def test_timeout_freezes_state_and_requires_explicit_resume(self):
        g = Game()
        g.input(packet(), 0)
        g.step(.05, .05)
        before = g.snapshot(.05)
        g.step(.05, 2)
        g.step(.05, 3)
        self.assertEqual(g.phase, 'paused')
        self.assertEqual(g.time_left, before['timeLeft'])
        data = packet(seq=2)
        data['action'] = 'none'
        with self.assertRaises(InputError):
            g.input(data, 3)
        data['action'] = 'join'
        g.input(data, 3)
        self.assertEqual(g.phase, 'catch')

    def test_background_release_is_not_a_restart(self):
        g = Game()
        g.input(packet(), 0)
        g.input(packet(seq=2) | {'active': False}, .1)
        self.assertEqual(g.phase, 'paused')
        self.assertIsNone(g.owner)
        self.assertEqual(g.wave, 1)

    def test_invalid_axes_and_old_sequence_cannot_mutate_state(self):
        g = Game()
        g.input(packet(), 0)
        with self.assertRaises(InputError):
            g.input(packet(seq=2) | {'tiltX': float('nan')}, .1)
        with self.assertRaises(InputError):
            g.input(packet() | {'x': 1}, .1)
        self.assertEqual(g.x, 0)

    def test_equal_color_and_level_merge_once_without_double_spend(self):
        g = Game()
        g.input(packet(), 0)
        g.balls = [ball(101, .45), ball(102, .5), ball(103, .55)]
        g.step(.01, .01)
        self.assertEqual(sorted(b['level'] for b in g.balls), [1, 2])
        self.assertEqual(sum(2**(b['level']-1) for b in g.balls), 3)

    def test_other_color_clash_loses_one_life_and_removes_both(self):
        g = Game()
        g.input(packet(), 0)
        g.balls = [ball(101, .48), ball(102, .52, color='coral')]
        g.step(.01, .01)
        self.assertEqual(g.lives, 4)
        self.assertEqual(g.balls, [])

    def test_capture_removes_bullet_from_pc_and_adds_same_color_to_vessel(self):
        g = Game(seed=1)
        g.input(packet(), 0)
        g.bullets = [dict(id=123, x=.5, y=.859, color='coral')]
        g.spawn_in = 10
        g.step(.01, .01)
        self.assertEqual(g.bullets, [])
        self.assertEqual(len(g.balls), 1)
        self.assertEqual(g.balls[0]['color'], 'coral')

    def test_fire_consumes_one_ball_and_damage_only_after_projectile_arrives(self):
        g = Game()
        g.input(packet(), 0)
        g.phase = 'grow'
        g.balls = [ball(101, .4, level=2), ball(102, .8)]
        g.input(packet(seq=2) | {'action': 'fire'}, .1)
        self.assertEqual(len(g.balls), 1)
        self.assertEqual(g.phase, 'fire')
        self.assertEqual(g.hp, 100)
        for i in range(50):
            g.step(.01, .11+i*.01)
        self.assertEqual(g.hp, 80)
        self.assertEqual(g.shots, [])

    def test_grow_phase_spawns_no_attacks_and_tilt_keeps_balls_inside(self):
        g = Game()
        g.input(packet() | {'tiltX': 1, 'tiltY': -1}, 0)
        g.phase = 'grow'
        g.balls = [ball(101, .5)]
        for i in range(70):
            g.step(.02, i*.02)
        self.assertEqual(g.bullets, [])
        b = g.balls[0]
        r = ball_radius(b['level'])
        self.assertTrue(r <= b['x'] <= 1-r)
        self.assertTrue(r <= b['y'] <= 1-r)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = PetServer(('127.0.0.1', 0), code='123456')
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .02}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.stopping.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def request(self, method, path, data=None):
        c = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            body = json.dumps(data) if data is not None else None
            c.request(method, path, body, {'Content-Type': 'application/json'} if body else {})
            r = c.getresponse()
            return r.status, r.read()
        finally:
            c.close()

    def test_pairing_is_required_for_state_and_input(self):
        self.assertEqual(self.request('GET', '/api/state?code=wrong')[0], 403)
        self.assertEqual(self.request('POST', '/api/input', packet() | {'code': 'wrong'})[0], 403)
        self.assertEqual(self.request('GET', '/api/state?code=123456')[0], 200)

    def test_join_conflict_and_reset_contract(self):
        self.assertEqual(self.request('POST', '/api/input', packet() | {'code': '123456'})[0], 200)
        self.assertEqual(self.request('POST', '/api/input', packet(client='other') | {'code': '123456'})[0], 409)
        self.assertEqual(self.request('POST', '/api/reset', {'code': '123456'})[0], 200)
        self.assertEqual(self.request('POST', '/api/input', packet(client='other') | {'code': '123456'})[0], 200)

    def test_server_streams_thirty_state_events_per_second(self):
        c = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        c.request('GET', '/api/events?code=123456')
        response = c.getresponse()
        self.assertEqual(response.status, 200)
        started = None
        count = 0
        while count < 16:
            line = response.readline()
            if line.startswith(b'data: '):
                self.assertEqual(json.loads(line[6:])['v'], 1)
                count += 1
                if started is None:
                    started = time.monotonic()
        elapsed = time.monotonic()-started
        c.close()
        self.assertTrue(.35 < elapsed < 1.2, elapsed)


if __name__ == '__main__':
    unittest.main()
