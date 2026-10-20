# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional pointer camera capture, called only on Blender's main thread."""
from __future__ import annotations
import math
import time
import bpy
import gpu
from mathutils import Matrix
from .preview_transport import PreviewServer, PreviewState, encode_rgba_png

WIDTH, HEIGHT = 480, 270
FRAME_INTERVAL = 1.0 / 5.0


def pointer_view_matrix(pose):
    from .visuals import pose_matrix
    # Blender cameras look down local -Z with +Y up. Pointer looks +Y, +Z up.
    camera_world = pose_matrix(pose) @ Matrix.Rotation(math.pi / 2, 4, 'X')
    return camera_world.inverted()


def _projection(pointer_size):
    # Clip our own helper sphere without changing its visibility or the viewport.
    near, far = max(.05, pointer_size * 1.1), 1000.0
    f = 1.0 / math.tan(math.radians(60) / 2)
    return Matrix(((f / (WIDTH / HEIGHT), 0, 0, 0),
                   (0, f, 0, 0),
                   (0, 0, -(far + near) / (far - near), -2 * far * near / (far - near)),
                   (0, 0, -1, 0)))


class PointerPreview:
    def __init__(self, runtime):
        self.runtime = runtime
        self.state = PreviewState()
        self.server = None
        self.offscreen = None
        self._handle = None
        self._config = None
        self._attempted_config = None
        self._in_draw = False
        self._next_capture = 0.0
        self.message = 'Phone pointer view off'

    @property
    def running(self):
        return self.server is not None

    def sync(self):
        """Reconcile opt-ins on the input tick; no network thread touches bpy."""
        runtime = self.runtime
        if not runtime.running or runtime.scene is None:
            self.stop()
            return
        settings = runtime.scene.spatial_pointer_settings
        if not settings.phone_pointer_view:
            self.stop()
            return
        reason = None
        if not settings.allow_lan:
            reason = 'Pointer view needs Allow LAN devices'
        elif not bpy.app.online_access:
            reason = 'Pointer view needs Blender Allow Online Access'
        elif bpy.app.background:
            reason = 'Pointer view needs a visible Blender 3D View'
        token = runtime.receiver.token if runtime.receiver is not None else settings.pair_token
        if reason is None and len(token) < 8:
            reason = 'Set a Pairing Token and restart input with LAN enabled'
        if reason:
            self.stop(reason)
            return
        config = ('0.0.0.0', settings.preview_port, token)
        if self._config != config and self._attempted_config != config:
            self.stop()
            self.state = PreviewState()
            self._attempted_config = config
            try:
                self.server = PreviewServer(*config, self.state)
                self._handle = bpy.types.SpaceView3D.draw_handler_add(
                    self._draw, (), 'WINDOW', 'POST_PIXEL')
                self._config = config
                self._next_capture = 0.0
                self.message = f'Pointer view HTTP {settings.preview_port} · waiting for phone'
            except Exception:
                self.stop('Pointer view could not open HTTP port or viewport')
                # Do not retry a busy port on every 60 Hz input tick.
                self._attempted_config = config
        if self.running and not self._has_viewport():
            self.state.unavailable('Open a visible 3D View for pointer view')
            self._free_offscreen()

    def _has_viewport(self):
        wm = bpy.context.window_manager
        return bool(wm and any(
            window.scene == self.runtime.scene and any(a.type == 'VIEW_3D' for a in window.screen.areas)
            for window in wm.windows))

    def _draw(self):
        if self._in_draw or not self.running:
            return
        context = bpy.context
        if (not self.runtime.running or context.scene != self.runtime.scene
                or context.area is None or context.area.type != 'VIEW_3D'
                or context.region is None or context.region.type != 'WINDOW'):
            return
        now = time.monotonic()
        if now < self._next_capture or not self.state.wants_frame(now):
            return
        self._next_capture = now + FRAME_INTERVAL
        self._in_draw = True
        try:
            if self.offscreen is None:
                self.offscreen = gpu.types.GPUOffScreen(WIDTH, HEIGHT, format='RGBA8')
            settings = self.runtime.scene.spatial_pointer_settings
            self.offscreen.draw_view3d(
                context.scene, context.view_layer, context.space_data, context.region,
                pointer_view_matrix(self.runtime.pose), _projection(settings.pointer_size),
                do_color_management=True, draw_background=True)
            with self.offscreen.bind():
                buffer = gpu.state.active_framebuffer_get().read_color(0, 0, WIDTH, HEIGHT, 4, 0, 'UBYTE')
                buffer.dimensions = WIDTH * HEIGHT * 4
                rgba = bytes(buffer)
            self.state.publish(encode_rgba_png(WIDTH, HEIGHT, rgba, bottom_up=True))
            self.message = f'Pointer view HTTP {self.server.address[1]} · 480 × 270, up to 5 fps'
        except Exception:
            self.state.unavailable('GPU frame unavailable; keep a visible 3D View open')
            self.message = 'Pointer view waiting for a usable 3D View'
            self._free_offscreen()
        finally:
            self._in_draw = False

    def _free_offscreen(self):
        if self.offscreen is not None:
            try:
                self.offscreen.free()
            except (ReferenceError, RuntimeError):
                pass  # Closing a window can already have destroyed its GPU context.
            self.offscreen = None

    def stop(self, message='Phone pointer view off'):
        if self._handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            except (ReferenceError, RuntimeError, ValueError):
                pass
            self._handle = None
        if self.server is not None:
            self.server.close()
            self.server = None
        self._free_offscreen()
        self._config = self._attempted_config = None
        self.state.unavailable(message)
        self.message = message
