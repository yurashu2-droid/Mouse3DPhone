# SPDX-License-Identifier: GPL-3.0-or-later
"""Main-thread Blender state. No threads, global mouse hooks or remote execution."""
from __future__ import annotations
import math
import secrets
import time
import traceback
import bpy
from mathutils import Vector
from .core import Pose, PoseMapper, SessionGate, advance_keyboard, smooth_pose
from .transport import UDPReceiver
from . import visuals


class Runtime:
    def __init__(self):
        self.source = 'STOPPED'
        self.scene = None
        self.pose = Pose((0, 0, 1))
        self.mapper = PoseMapper(self.pose)
        self.helpers = {}
        self.keys = set()
        self.precision = False
        self.input_pose = Pose()
        self.receiver = None
        self.gate = SessionGate()
        self.last_time = 0.0
        self.generation = 0
        self.grabbed = None
        self.history = []
        self.remote_follow = False
        self.remote_tracking = False
        self.remote_armed = False
        self.remote_generation = 0
        self.packets = 0
        self.dropped = 0
        self.status = 'Stopped'
        self.notice = ''

    @property
    def running(self):
        return self.source != 'STOPPED'

    @property
    def following(self):
        if not self.running or self.scene is None:
            return False
        if not self.scene.spatial_pointer_settings.follow:
            return False
        return self.source == 'KEYBOARD' or (self.remote_follow and self.remote_tracking)

    def start(self, scene, source):
        if source not in {'KEYBOARD', 'UDP'}:
            raise ValueError('Unknown input source')
        self.stop()
        if self.scene != scene:
            self.history.clear()
        settings = scene.spatial_pointer_settings
        self.scene = scene
        old = visuals.find_helpers(scene).get('pointer')
        if old is not None:
            self.pose = Pose(tuple(old.matrix_world.translation), tuple(old.matrix_world.to_quaternion()))
        else:
            self.pose = Pose((0, 0, 1))
        self.helpers = visuals.ensure_pointer(scene, self.pose, settings.pointer_size)
        self.mapper = PoseMapper(self.pose)
        self.input_pose = Pose()
        self.keys.clear()
        self.precision = False
        self.last_time = time.monotonic()
        self.notice = ''
        self.gate = SessionGate(timeout=.75)
        self.remote_generation = 0
        self.remote_armed = False
        self.remote_follow = False
        self.remote_tracking = False
        self.packets = self.dropped = 0
        if source == 'UDP':
            if settings.allow_lan:
                if not bpy.app.online_access:
                    raise RuntimeError('LAN mode requires Blender Preferences > System > Allow Online Access')
                if len(settings.pair_token) < 8:
                    settings.pair_token = secrets.token_hex(6)
            host = '0.0.0.0' if settings.allow_lan else '127.0.0.1'
            token = settings.pair_token if settings.allow_lan else ''
            try:
                self.receiver = UDPReceiver(host, settings.port, token)
            except OSError as exc:
                self.status = 'Could not open UDP port'
                raise RuntimeError(f'UDP {settings.port}: port unavailable or blocked ({exc})') from exc
        self.source = source
        self.generation += 1
        self.status = 'Keyboard test active' if source == 'KEYBOARD' else 'Waiting for UDP packets'
        if source == 'UDP' and not bpy.app.timers.is_registered(timer_tick):
            bpy.app.timers.register(timer_tick, first_interval=.01)
        self.apply_pose()
        visuals.tag_redraw()

    def stop(self, cancel_grab=False, message='Stopped', unregister_timer=True):
        try:
            self.release(cancel=cancel_grab)
        finally:
            if self.receiver is not None:
                self.receiver.close()
                self.receiver = None
            if unregister_timer and bpy.app.timers.is_registered(timer_tick):
                bpy.app.timers.unregister(timer_tick)
            self.source = 'STOPPED'
            self.keys.clear()
            self.precision = False
            self.mapper.set_target(self.pose)
            self.remote_follow = self.remote_tracking = False
            self.remote_armed = False
            self.generation += 1
            self.status = message
        visuals.tag_redraw()

    def set_pose(self, pose):
        self.pose = pose
        self.mapper.set_target(pose)

    def recenter(self):
        self.mapper.set_target(self.pose)
        self.notice = 'Reference reset; pointer stays in place'

    def snap_to(self, obj):
        if self.grabbed:
            self.notice = 'Release the object before snapping the pointer'
            return False
        if obj is None or obj.get('_sp_helper'):
            self.notice = 'Select an object first'
            return False
        self.set_pose(Pose(tuple(obj.matrix_world.translation), self.pose.rotation))
        self.apply_pose()
        self.notice = 'Pointer moved to the selected object origin'
        return True

    def grab(self, obj):
        if not self.running:
            self.notice = 'Start an input mode before grabbing'
            return False
        if obj is not None and self.scene is not None and obj.name not in self.scene.objects:
            self.notice = 'Target must belong to the active input scene'
            return False
        if self.grabbed is not None:
            return True
        if obj is None or obj.get('_sp_helper'):
            self.notice = 'Select the target object first'
            return False
        if obj.library is not None:
            self.notice = 'Linked/read-only objects are not supported'
            return False
        if obj.mode != 'OBJECT':
            self.notice = 'Switch to Object Mode before grabbing'
            return False
        if (any(obj.lock_location) or any(obj.lock_rotation)
                or (obj.rotation_mode in {'QUATERNION', 'AXIS_ANGLE'}
                    and obj.lock_rotations_4d and obj.lock_rotation_w)):
            self.notice = 'Unlock object transforms before grabbing'
            return False
        if any(not c.mute and c.influence > 0 for c in obj.constraints):
            self.notice = 'Use an unconstrained object for this prototype'
            return False
        try:
            original = obj.matrix_world.copy()
            offset = visuals.pose_matrix(self.pose).inverted_safe() @ original
            self.grabbed = (obj, original, offset)
            self.notice = f'Grabbed: {obj.name}'
            return True
        except (ReferenceError, RuntimeError):
            self.notice = 'Target is no longer available'
            return False

    def release(self, cancel=False):
        held = self.grabbed
        self.grabbed = None
        if held is None:
            return
        obj, original, _ = held
        try:
            if cancel:
                obj.matrix_world = original
                self.notice = 'Current grab cancelled; original transform restored'
            else:
                # Our explicit history is independent of Blender's global undo stack.
                self.history.append((obj, original.copy()))
                self.history = self.history[-20:]
                self.notice = f'Released: {obj.name}'
        except (ReferenceError, RuntimeError):
            self.notice = 'Grab target was removed'

    def restore_last(self):
        if self.scene is not None and bpy.context.scene != self.scene:
            self.notice = 'Switch back to the input scene before restoring'
            return False
        if self.grabbed is not None:
            self.notice = 'Release the current grab first'
            return False
        while self.history:
            obj, original = self.history.pop()
            try:
                obj.matrix_world = original
                self.notice = f'Restored: {obj.name}'
                return True
            except (ReferenceError, RuntimeError):
                continue
        self.notice = 'No previous grab to restore'
        return False

    def apply_pose(self):
        if not self.helpers or self.scene is None:
            return
        settings = self.scene.spatial_pointer_settings
        visuals.apply_pointer(self.helpers, self.pose, settings.pointer_size,
                              self.grabbed is not None, self.following)
        if self.grabbed is not None:
            obj, _, offset = self.grabbed
            try:
                obj.matrix_world = visuals.pose_matrix(self.pose) @ offset
            except (ReferenceError, RuntimeError):
                self.grabbed = None
                self.notice = 'Grab target was removed'
        if settings.sync_cursor:
            self.scene.cursor.location = self.pose.position
            self.scene.cursor.rotation_mode = 'QUATERNION'
            self.scene.cursor.rotation_quaternion = self.pose.rotation

    def _active_object(self):
        if bpy.context.scene != self.scene:
            return None
        return bpy.context.view_layer.objects.active

    def _consume(self, packet, peer, now):
        if not self.gate.accept(packet, peer, now):
            self.dropped += 1
            return
        if self.gate.generation != self.remote_generation:
            self.remote_generation = self.gate.generation
            self.mapper.set_target(self.pose)
            self.release()
            self.remote_armed = False
        self.packets += 1
        self.remote_follow, self.remote_tracking = packet.follow, packet.tracking
        follow = packet.follow and self.scene.spatial_pointer_settings.follow
        if not follow or not packet.tracking:
            # Stop the smoothing tail immediately when clutching or losing tracking.
            self.mapper.set_target(self.pose)
        self.mapper.update(packet.pose, follow, self.scene.spatial_pointer_settings.gain, packet.tracking)
        if not packet.tracking:
            self.release()
            self.remote_armed = False
            self.status = 'Tracking lost; pointer frozen'
            return
        self.status = 'UDP connected' if follow else 'UDP connected · follow paused'
        if not packet.grab:
            self.release()
            self.remote_armed = True
        elif self.remote_armed:
            self.remote_armed = False
            self.grab(self._active_object())

    def tick(self, now=None):
        if not self.running:
            return
        now = time.monotonic() if now is None else now
        dt = min(max(now-self.last_time, 0.0), .05)
        self.last_time = now
        if self.scene is None or bpy.context.scene != self.scene:
            self.stop(message='Stopped after scene change', unregister_timer=False)
            return
        if bpy.context.mode != 'OBJECT':
            self.stop(message='Stopped: use Object Mode', unregister_timer=False)
            return
        settings = self.scene.spatial_pointer_settings
        if self.source == 'KEYBOARD':
            self.input_pose = advance_keyboard(self.input_pose, self.keys, dt,
                settings.move_speed, math.radians(settings.rotation_speed), self.precision)
            if not settings.follow:
                self.mapper.set_target(self.pose)
            self.mapper.update(self.input_pose, settings.follow, settings.gain)
            self.status = 'Keyboard test active' if settings.follow else 'Keyboard · follow paused'
        elif self.source == 'UDP':
            previous_bad = self.receiver.rejected
            for packet, peer in self.receiver.poll(limit=64):
                self._consume(packet, peer, now)
            self.dropped += self.receiver.rejected-previous_bad
            if self.gate.stale(now):
                self.mapper.set_target(self.pose)
                self.release()
                self.remote_follow = self.remote_tracking = False
                self.remote_armed = False
                self.status = 'Waiting for UDP packets' if self.packets == 0 else 'Signal timeout · pointer frozen'
            elif not settings.follow:
                self.mapper.set_target(self.pose)
        self.pose = smooth_pose(self.pose, self.mapper.target, dt, settings.smoothing)
        self.apply_pose()
        visuals.tag_redraw()


RUNTIME = Runtime()


def timer_tick():
    if not RUNTIME.running or RUNTIME.source != 'UDP':
        return None
    try:
        RUNTIME.tick()
    except Exception as exc:
        traceback.print_exc()
        RUNTIME.stop(message=f'Stopped: {str(exc)[:90]}', unregister_timer=False)
        return None
    return 1.0/60.0 if RUNTIME.source == 'UDP' else None
