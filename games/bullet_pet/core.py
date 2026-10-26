"""Authoritative, engine-independent rules for the two-screen prototype."""
from __future__ import annotations

import math
import random
import threading


def ball_radius(level):
    return .038 + level * .009


class InputError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Game:
    def __init__(self, now=0.0, seed=None):
        self.lock = threading.RLock()
        self.rng = random.Random(seed)
        self.reset(now)

    def reset(self, now):
        with self.lock:
            self.phase = 'waiting'
            self.resume_phase = 'catch'
            self.phase_left = 8.0
            self.time_left = 120.0
            self.elapsed = 0.0
            self.wave = 1
            self.score = 0
            self.lives = 5
            self.hp = 100
            self.boss_x = .5
            self.x = 0.0
            self.tilt_x = self.tilt_y = 0.0
            self.owner = self.mode = None
            self.last_input = None
            self.last_seq = -1
            self.spawn_in = .3
            self.clash_until = 0.0
            self.balls, self.bullets, self.shots, self.fx = [], [], [], []
            self.tick = 0
            self.next_id = 1
            self.now = now

    def _id(self):
        result = self.next_id
        self.next_id += 1
        return result

    @staticmethod
    def _axis(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise InputError('入力値が不正です。')
        return max(-1.0, min(1.0, float(value)))

    def input(self, data, now):
        client = data.get('client')
        seq = data.get('seq')
        action = data.get('action', 'none')
        active = data.get('active', True)
        mode = data.get('mode', 'phone')
        if not isinstance(client, str) or not 1 <= len(client) <= 80:
            raise InputError('clientが必要です。')
        if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq <= 2**53 - 1:
            raise InputError('seqが不正です。')
        if action not in ('none', 'join', 'fire') or type(active) is not bool or mode not in ('phone', 'demo'):
            raise InputError('操作が不正です。')
        x = self._axis(data.get('x', 0))
        tx = self._axis(data.get('tiltX', 0))
        ty = self._axis(data.get('tiltY', 0))
        with self.lock:
            self._expire_owner(now)
            if self.owner is not None and self.owner != client:
                raise InputError('別の端末が操作中です。PCの「やり直す」で切り替えられます。', 409)
            if self.owner == client and seq <= self.last_seq:
                raise InputError('古い入力を破棄しました。', 409)
            if not active:
                if self.owner == client:
                    self._pause()
                return
            if self.owner is None:
                if action != 'join':
                    raise InputError('接続してはじめるボタンを押してください。', 409)
                self.owner, self.mode, self.last_seq = client, mode, -1
                if self.phase == 'waiting':
                    self.phase = 'catch'
                elif self.phase == 'paused':
                    self.phase = self.resume_phase
            self.last_seq = seq
            self.last_input = now
            self.x, self.tilt_x, self.tilt_y = x, tx, ty
            if action == 'fire':
                self._fire()

    def _pause(self):
        if self.phase in ('catch', 'grow', 'fire'):
            self.resume_phase = self.phase
            self.phase = 'paused'
        self.owner = self.mode = None
        self.tilt_x = self.tilt_y = 0.0

    def _expire_owner(self, now):
        if self.owner is not None and self.last_input is not None and now - self.last_input > 1.5:
            self._pause()

    def _effect(self, kind, x, y, color='cyan'):
        self.fx.append(dict(id=self._id(), type=kind, x=x, y=y, color=color, born=self.elapsed))

    def _fire(self):
        if self.phase not in ('grow', 'fire') or not self.balls:
            return
        if self.phase == 'grow':
            self.phase, self.phase_left = 'fire', 6.0
        ball = max(self.balls, key=lambda b: (b['level'], -b['id']))
        self.balls.remove(ball)
        aim = .5 + .4 * self.x
        self.shots.append(dict(id=self._id(), x=aim, y=.83, color=ball['color'],
                               level=ball['level'], hit=abs(aim - self.boss_x) < .16))

    def _capture(self, bullet):
        if len(self.balls) >= 6:
            self._effect('miss', bullet['x'], .86, bullet['color'])
            return
        self.balls.append(dict(id=self._id(), x=self.rng.uniform(.23, .77), y=.16,
                               vx=self.rng.uniform(-.12, .12), vy=.15, color=bullet['color'],
                               level=1, born=self.elapsed))
        self.score += 5
        self._effect('capture', bullet['x'], .86, bullet['color'])

    def _step_balls(self, dt):
        damping = math.exp(-1.4 * dt)
        for ball in self.balls:
            ball['vx'] = (ball['vx'] + self.tilt_x * 1.8 * dt) * damping
            ball['vy'] = (ball['vy'] + self.tilt_y * 1.8 * dt) * damping
            ball['x'] += ball['vx'] * dt
            ball['y'] += ball['vy'] * dt
            radius = ball_radius(ball['level'])
            for axis, velocity in (('x', 'vx'), ('y', 'vy')):
                if ball[axis] < radius:
                    ball[axis], ball[velocity] = radius, abs(ball[velocity]) * .65
                elif ball[axis] > 1 - radius:
                    ball[axis], ball[velocity] = 1 - radius, -abs(ball[velocity]) * .65
        removed = set()
        additions = []
        for i, a in enumerate(self.balls):
            if a['id'] in removed:
                continue
            for b in self.balls[i + 1:]:
                if b['id'] in removed or min(self.elapsed - a['born'], self.elapsed - b['born']) < .4:
                    continue
                dx, dy = b['x'] - a['x'], b['y'] - a['y']
                distance = math.hypot(dx, dy)
                required = ball_radius(a['level']) + ball_radius(b['level'])
                if distance >= required:
                    continue
                if a['color'] == b['color'] and a['level'] == b['level'] and a['level'] < 5:
                    removed.update((a['id'], b['id']))
                    additions.append(dict(id=self._id(), x=(a['x']+b['x'])/2, y=(a['y']+b['y'])/2,
                                          vx=(a['vx']+b['vx'])/2, vy=(a['vy']+b['vy'])/2,
                                          color=a['color'], level=a['level']+1, born=self.elapsed))
                    self.score += 15 * a['level']
                    self._effect('merge', additions[-1]['x'], additions[-1]['y'], a['color'])
                    break
                if a['color'] != b['color'] and self.elapsed >= self.clash_until:
                    removed.update((a['id'], b['id']))
                    self.lives -= 1
                    self.clash_until = self.elapsed + .8
                    self._effect('clash', (a['x']+b['x'])/2, (a['y']+b['y'])/2, 'coral')
                    break
                # Resolve surviving contacts without adding energy to the vessel.
                nx, ny = (dx/distance, dy/distance) if distance > 1e-8 else (1.0, 0.0)
                overlap = (required-distance)/2
                a['x'] -= nx*overlap
                a['y'] -= ny*overlap
                b['x'] += nx*overlap
                b['y'] += ny*overlap
                approaching = (b['vx']-a['vx'])*nx + (b['vy']-a['vy'])*ny
                if approaching < 0:
                    a['vx'] += approaching*nx*.8
                    a['vy'] += approaching*ny*.8
                    b['vx'] -= approaching*nx*.8
                    b['vy'] -= approaching*ny*.8
        self.balls = [b for b in self.balls if b['id'] not in removed] + additions

    def step(self, dt, now):
        with self.lock:
            self.now = now
            self.tick += 1
            self._expire_owner(now)
            if self.phase not in ('catch', 'grow', 'fire'):
                return
            dt = max(0, min(.05, dt))
            self.elapsed += dt
            self.time_left = max(0, self.time_left-dt)
            self.phase_left -= dt
            self.boss_x = .5 + .27 * math.sin(self.elapsed * .65)
            self.fx = [e for e in self.fx if self.elapsed-e['born'] < .65]
            if self.phase == 'catch':
                self.spawn_in -= dt
                if self.spawn_in <= 0:
                    # First pairs share a color to teach merging before mixing colors.
                    color = 'cyan' if self.wave == 1 and self.elapsed < 4 else self.rng.choice(('cyan', 'coral'))
                    self.bullets.append(dict(id=self._id(), x=self.rng.uniform(.16, .84), y=.14,
                                             color=color))
                    self.spawn_in = max(.65, 1.05-self.wave*.035)
                remaining = []
                for bullet in self.bullets:
                    bullet['y'] += (.24 + self.wave*.015) * dt
                    if bullet['y'] >= .86:
                        if abs(bullet['x']-(.5+.4*self.x)) <= .11:
                            self._capture(bullet)
                        else:
                            self.score = max(0, self.score-1)
                            self._effect('miss', bullet['x'], .86, bullet['color'])
                    else:
                        remaining.append(bullet)
                self.bullets = remaining
            self._step_balls(dt)
            remaining_shots = []
            for shot in self.shots:
                shot['y'] -= 1.7*dt
                if shot['y'] <= .16:
                    if shot['hit']:
                        # Merging is worth the risk, not merely two shots in one click.
                        self.hp = max(0, self.hp - round(8 * 2.5**(shot['level']-1)))
                        self.score += 40 * shot['level']
                        self._effect('hit', shot['x'], .16, shot['color'])
                    else:
                        self._effect('miss', shot['x'], .16, shot['color'])
                else:
                    remaining_shots.append(shot)
            self.shots = remaining_shots
            if self.hp <= 0:
                self.phase = 'won'
            elif self.lives <= 0 or self.time_left <= 0:
                self.phase = 'lost'
            elif self.phase_left <= 0:
                if self.phase == 'catch':
                    self.phase, self.phase_left = 'grow', 6.0
                    self.bullets.clear()
                elif self.phase == 'grow':
                    self.phase, self.phase_left = 'fire', 6.0
                else:
                    self.phase, self.phase_left = 'catch', 8.0
                    self.wave += 1
                    self.spawn_in = .3

    def snapshot(self, now):
        with self.lock:
            def visible(items):
                return [{k: round(v, 4) if isinstance(v, float) else v
                         for k, v in item.items() if k not in ('born', 'hit')} for item in items]
            connected = self.owner is not None and self.last_input is not None and now-self.last_input <= 1.5
            return dict(v=1, tick=self.tick, serverTime=round(now, 4), phase=self.phase,
                        phaseLeft=round(max(0, self.phase_left), 2), timeLeft=round(self.time_left, 2),
                        wave=self.wave, score=self.score, lives=max(0, self.lives),
                        boss=dict(hp=self.hp, maxHp=100, x=round(self.boss_x, 4)),
                        receiver=dict(x=round(.5+.4*self.x, 4), width=.22), aim=round(.5+.4*self.x, 4),
                        balls=visible(self.balls), bullets=visible(self.bullets), shots=visible(self.shots),
                        fx=visible(self.fx), connected=connected, controller=self.mode if connected else None,
                        inputAge=round(max(0, now-self.last_input), 2) if self.last_input is not None else None)
