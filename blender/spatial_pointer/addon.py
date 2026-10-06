# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender panel/operators. Property annotations must evaluate (no future annotations)."""
import secrets
import traceback
import bpy
import blf
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.app.handlers import persistent
from .core import Pose
from .runtime import RUNTIME
from . import visuals

_DRAW_HANDLE = None
_REGISTERED = False
_KEYBOARD_OPERATORS = []


class SPATIALPOINTER_Settings(bpy.types.PropertyGroup):
    follow: BoolProperty(name='Follow input', default=True,
        description='Off freezes the pointer; input can move independently. On re-anchors without jumping')
    gain: FloatProperty(name='Motion gain', default=1.0, min=.01, max=100.0,
        description='Blender units per input unit (meters for ARKit)')
    move_speed: FloatProperty(name='Test move speed', default=2.0, min=.05, max=100.0,
        description='Keyboard simulator input units per second before gain')
    rotation_speed: FloatProperty(name='Test rotation speed', default=90.0, min=1.0, max=360.0,
        description='Keyboard simulator degrees per second')
    smoothing: FloatProperty(name='Smooth half-life (s)', default=.035, min=0.0, max=.3, precision=3,
        description='0 disables smoothing; 0.035 halves position error every 35 ms, not a latency guarantee')
    pointer_size: FloatProperty(name='Pointer size', default=.12, min=.02, max=2.0)
    sync_cursor: BoolProperty(name='Also move Blender 3D Cursor', default=False,
        description='Optional: writes the native 3D Cursor location and rotation as well')
    port: IntProperty(name='UDP port', default=5005, min=1024, max=65535)
    allow_lan: BoolProperty(name='Allow LAN devices', default=False,
        description='Listen on all IPv4 interfaces instead of localhost; use only a trusted private network')
    pair_token: StringProperty(name='Pairing token', default='', maxlen=64,
        description='Required in LAN packets; plain text pairing, not encryption')
    show_network: BoolProperty(name='UDP / future phone input', default=False)
    show_tuning: BoolProperty(name='Tuning', default=False)
    show_help: BoolProperty(name='Keys & limits', default=True)


def _stop_keyboard_handlers():
    for operator in list(_KEYBOARD_OPERATORS):
        operator.cleanup()


class SPATIALPOINTER_OT_demo(bpy.types.Operator):
    bl_idname = 'spatial_pointer.demo_scene'
    bl_label = 'Open Practice Scene'
    bl_description = 'Create or reopen a separate scene; your existing scenes and objects are not deleted'
    bl_options = {'REGISTER'}

    def execute(self, context):
        RUNTIME.stop()
        _stop_keyboard_handlers()
        scene = visuals.create_demo(context)
        if RUNTIME.scene != scene:
            RUNTIME.history.clear()
        RUNTIME.scene = scene
        root = visuals.find_helpers(scene)['pointer']
        RUNTIME.set_pose(Pose(tuple(root.matrix_world.translation), tuple(root.matrix_world.to_quaternion())))
        RUNTIME.helpers = visuals.find_helpers(scene)
        self.report({'INFO'}, 'Practice scene opened. Start Keyboard Test, then hold Space to grab the selected cube')
        return {'FINISHED'}


class SPATIALPOINTER_OT_create(bpy.types.Operator):
    bl_idname = 'spatial_pointer.create'
    bl_label = 'Create Pointer Here'
    bl_description = 'Add viewport helpers to this scene without altering existing objects'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        RUNTIME.stop()
        _stop_keyboard_handlers()
        if RUNTIME.scene != context.scene:
            RUNTIME.history.clear()
        RUNTIME.scene = context.scene
        old = visuals.find_helpers(context.scene).get('pointer')
        pose = Pose(tuple(old.matrix_world.translation), tuple(old.matrix_world.to_quaternion())) if old else Pose((0, 0, 1))
        RUNTIME.set_pose(pose)
        RUNTIME.helpers = visuals.ensure_pointer(context.scene, pose, context.scene.spatial_pointer_settings.pointer_size)
        return {'FINISHED'}


class SPATIALPOINTER_OT_keyboard(bpy.types.Operator):
    bl_idname = 'spatial_pointer.keyboard'
    bl_label = 'Start Keyboard Test'
    bl_description = 'PC-only simulator: WASD/QE move, IK/JL/UO rotate, hold Space grabs, C clutch, Enter exits'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}
    _timer = None
    _wm = None
    _workspace = None
    _generation = -1

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        _stop_keyboard_handlers()
        try:
            RUNTIME.start(context.scene, 'KEYBOARD')
        except Exception as exc:
            RUNTIME.stop(message='Could not start keyboard test')
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._generation = RUNTIME.generation
        self._wm = context.window_manager
        self._workspace = context.workspace
        self._timer = self._wm.event_timer_add(1.0/60.0, window=context.window)
        self._wm.modal_handler_add(self)
        _KEYBOARD_OPERATORS.append(self)
        context.workspace.status_text_set('SPATIAL POINTER | WASD/QE Move | IK/JL/UO Rotate | Hold Space Grab | C Follow | Shift Fine | Enter Finish | Esc Cancel Grab')
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return self.invoke(context, None)

    def cleanup(self):
        if self._timer is not None and self._wm is not None:
            try:
                self._wm.event_timer_remove(self._timer)
            except (ReferenceError, RuntimeError):
                pass
            self._timer = None
        if self._workspace is not None:
            try:
                self._workspace.status_text_set(None)
            except (ReferenceError, RuntimeError):
                pass
        if self in _KEYBOARD_OPERATORS:
            _KEYBOARD_OPERATORS.remove(self)

    def cancel(self, context):
        if RUNTIME.source == 'KEYBOARD' and RUNTIME.generation == self._generation:
            RUNTIME.stop(cancel_grab=True)
        self.cleanup()

    def modal(self, context, event):
        if (self._timer is None or RUNTIME.source != 'KEYBOARD'
                or RUNTIME.generation != self._generation):
            self.cleanup()
            return {'FINISHED'}
        if event.type == 'WINDOW_DEACTIVATE':
            RUNTIME.keys.clear()
            RUNTIME.precision = False
            RUNTIME.release(cancel=True)
            RUNTIME.recenter()
            return {'PASS_THROUGH'}
        if event.type == 'TIMER':
            try:
                RUNTIME.tick()
            except Exception as exc:
                traceback.print_exc()
                RUNTIME.stop(cancel_grab=True, message=f'Stopped: {str(exc)[:90]}')
                self.cleanup()
                self.report({'ERROR'}, str(exc))
                return {'FINISHED'}
            return {'PASS_THROUGH'}
        RUNTIME.precision = event.shift
        if event.type in {'ESC', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            RUNTIME.stop(cancel_grab=(event.type == 'ESC'))
            self.cleanup()
            return {'FINISHED'}
        if event.ctrl or event.alt:
            RUNTIME.keys.clear()
            return {'PASS_THROUGH'}
        if event.type in {'W', 'A', 'S', 'D', 'Q', 'E', 'I', 'K', 'J', 'L', 'U', 'O'}:
            if event.value == 'PRESS':
                RUNTIME.keys.add(event.type)
            elif event.value == 'RELEASE':
                RUNTIME.keys.discard(event.type)
            return {'RUNNING_MODAL'}
        if event.type == 'SPACE':
            if event.value == 'PRESS' and not event.is_repeat:
                RUNTIME.grab(context.view_layer.objects.active)
            elif event.value == 'RELEASE':
                RUNTIME.release()
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and not event.is_repeat:
            if event.type == 'C':
                context.scene.spatial_pointer_settings.follow = not context.scene.spatial_pointer_settings.follow
                RUNTIME.recenter()
                return {'RUNNING_MODAL'}
            if event.type == 'R':
                RUNTIME.recenter()
                return {'RUNNING_MODAL'}
            if event.type == 'F':
                RUNTIME.snap_to(context.view_layer.objects.active)
                return {'RUNNING_MODAL'}
        # Normal middle-mouse orbit, wheel zoom and mouse selection still work.
        return {'PASS_THROUGH'}


class SPATIALPOINTER_OT_network(bpy.types.Operator):
    bl_idname = 'spatial_pointer.network'
    bl_label = 'Start UDP Receiver'
    bl_description = 'Receive validated pose data; loopback only unless Allow LAN devices is checked'

    def execute(self, context):
        _stop_keyboard_handlers()
        try:
            RUNTIME.start(context.scene, 'UDP')
        except Exception as exc:
            RUNTIME.stop(message='Could not start UDP receiver')
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class SPATIALPOINTER_OT_stop(bpy.types.Operator):
    bl_idname = 'spatial_pointer.stop'
    bl_label = 'Stop Input'
    bl_description = 'Stop receiving input and release the object at its current position'

    def execute(self, context):
        RUNTIME.stop()
        _stop_keyboard_handlers()
        return {'FINISHED'}


class SPATIALPOINTER_OT_grab(bpy.types.Operator):
    bl_idname = 'spatial_pointer.grab'
    bl_label = 'Grab Selected'
    bl_description = 'Grab the active selected object; this prototype does not pick surfaces by pointer proximity'

    def execute(self, context):
        if not RUNTIME.grab(context.view_layer.objects.active):
            self.report({'WARNING'}, RUNTIME.notice)
        return {'FINISHED'}


class SPATIALPOINTER_OT_release(bpy.types.Operator):
    bl_idname = 'spatial_pointer.release'
    bl_label = 'Release'

    def execute(self, context):
        RUNTIME.release()
        return {'FINISHED'}


class SPATIALPOINTER_OT_cancel_grab(bpy.types.Operator):
    bl_idname = 'spatial_pointer.cancel_grab'
    bl_label = 'Cancel Grab'
    bl_description = 'Restore the object to the transform it had when the current grab began'

    def execute(self, context):
        RUNTIME.release(cancel=True)
        return {'FINISHED'}


class SPATIALPOINTER_OT_restore(bpy.types.Operator):
    bl_idname = 'spatial_pointer.restore'
    bl_label = 'Restore Last Grab'
    bl_description = 'Restore the most recently released object transform (up to 20 grabs per session)'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not RUNTIME.restore_last():
            self.report({'INFO'}, RUNTIME.notice)
        visuals.tag_redraw()
        return {'FINISHED'}


class SPATIALPOINTER_OT_snap(bpy.types.Operator):
    bl_idname = 'spatial_pointer.snap'
    bl_label = 'Pointer to Selection'
    bl_description = 'Move the pointer to the active object origin without moving that object'

    def execute(self, context):
        if RUNTIME.scene != context.scene or not RUNTIME.helpers:
            if RUNTIME.scene != context.scene:
                RUNTIME.stop()
                _stop_keyboard_handlers()
                RUNTIME.history.clear()
            RUNTIME.scene = context.scene
            RUNTIME.helpers = visuals.ensure_pointer(context.scene, RUNTIME.pose, context.scene.spatial_pointer_settings.pointer_size)
        RUNTIME.snap_to(context.view_layer.objects.active)
        visuals.tag_redraw()
        return {'FINISHED'}


class SPATIALPOINTER_OT_recenter(bpy.types.Operator):
    bl_idname = 'spatial_pointer.recenter'
    bl_label = 'Rebase / No Jump'
    bl_description = 'Keep the pointer where it is and establish a fresh input reference'

    def execute(self, context):
        RUNTIME.recenter()
        return {'FINISHED'}


class SPATIALPOINTER_OT_token(bpy.types.Operator):
    bl_idname = 'spatial_pointer.new_token'
    bl_label = 'New Pairing Token'

    def execute(self, context):
        context.scene.spatial_pointer_settings.pair_token = secrets.token_hex(6)
        return {'FINISHED'}


class SPATIALPOINTER_OT_remove(bpy.types.Operator):
    bl_idname = 'spatial_pointer.remove_helpers'
    bl_label = 'Remove Pointer Helpers'
    bl_description = 'Remove only tagged Spatial Pointer helper objects from this scene'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        RUNTIME.stop()
        _stop_keyboard_handlers()
        visuals.remove_helpers(context.scene)
        RUNTIME.helpers = {}
        return {'FINISHED'}


class SPATIALPOINTER_PT_main(bpy.types.Panel):
    bl_label = 'Spatial Pointer · 0.1'
    bl_idname = 'VIEW3D_PT_spatial_pointer'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Spatial'

    def draw(self, context):
        layout = self.layout
        s = context.scene.spatial_pointer_settings
        same_scene = RUNTIME.scene == context.scene
        active = RUNTIME.running and same_scene
        box = layout.box()
        box.label(text=RUNTIME.status if same_scene else 'Stopped', icon='PLAY' if active else 'PAUSE')
        if RUNTIME.source == 'KEYBOARD' and active:
            box.label(text='PC simulator · not phone tracking', icon='INFO')
        if same_scene:
            x, y, z = RUNTIME.pose.position
            box.label(text=f'X {x:+.2f}    Y {y:+.2f}    Z {z:+.2f}')
        box = layout.box()
        box.label(text='1  /  SET UP')
        box.operator('spatial_pointer.demo_scene', icon='MESH_CUBE')
        box.operator('spatial_pointer.create', icon='EMPTY_AXIS')
        box = layout.box()
        box.label(text='2  /  TEST 3D INPUT')
        row = box.row()
        row.scale_y = 1.4
        if active:
            row.operator('spatial_pointer.stop', icon='PAUSE')
        else:
            row.operator('spatial_pointer.keyboard', icon='PLAY')
        box.prop(s, 'follow', toggle=True)
        box.operator('spatial_pointer.recenter', icon='FILE_REFRESH')
        box = layout.box()
        box.label(text='3  /  GRAB AN OBJECT')
        target = context.view_layer.objects.active
        box.label(text='Selected: ' + (target.name[:26] if target else '(none)'))
        row = box.row(align=True)
        row.enabled = active
        if RUNTIME.grabbed and same_scene:
            row.operator('spatial_pointer.release', icon='UNLINKED')
            row.operator('spatial_pointer.cancel_grab', text='Cancel', icon='LOOP_BACK')
        else:
            row.operator('spatial_pointer.grab', icon='LINKED')
        row = box.row()
        row.enabled = not (same_scene and RUNTIME.grabbed)
        row.operator('spatial_pointer.snap', icon='SNAP_ON')
        row = box.row()
        row.enabled = same_scene and bool(RUNTIME.history) and RUNTIME.grabbed is None
        row.operator('spatial_pointer.restore', icon='LOOP_BACK')
        if same_scene and RUNTIME.notice:
            # Two short lines prevent a narrow N-panel from becoming unreadable.
            text = RUNTIME.notice
            box.label(text=text[:40])
            if len(text) > 40:
                box.label(text=text[40:80])
        box = layout.box()
        box.prop(s, 'show_tuning', icon='TRIA_DOWN' if s.show_tuning else 'TRIA_RIGHT', emboss=False)
        if s.show_tuning:
            box.prop(s, 'gain')
            box.prop(s, 'smoothing')
            box.prop(s, 'pointer_size')
            box.prop(s, 'move_speed')
            box.prop(s, 'rotation_speed')
            box.prop(s, 'sync_cursor')
            box.operator('spatial_pointer.remove_helpers', icon='X')
        box = layout.box()
        box.prop(s, 'show_network', icon='TRIA_DOWN' if s.show_network else 'TRIA_RIGHT', emboss=False)
        if s.show_network:
            col = box.column()
            col.enabled = RUNTIME.source != 'UDP'
            col.prop(s, 'port')
            col.prop(s, 'allow_lan')
            if s.allow_lan:
                col.prop(s, 'pair_token')
                col.operator('spatial_pointer.new_token', icon='FILE_REFRESH')
                col.label(text='Trusted LAN only · not encrypted', icon='ERROR')
            else:
                col.label(text='127.0.0.1 · this PC only')
            if RUNTIME.source != 'UDP':
                box.operator('spatial_pointer.network', icon='PLAY')
            else:
                box.operator('spatial_pointer.stop', icon='PAUSE')
                box.label(text=f'Accepted {RUNTIME.packets}  |  Dropped {RUNTIME.dropped}')
            box.label(text='iPhone tracking app not included', icon='INFO')
        box = layout.box()
        box.prop(s, 'show_help', icon='TRIA_DOWN' if s.show_help else 'TRIA_RIGHT', emboss=False)
        if s.show_help:
            for line in ('A / D   left / right  (X)', 'W / S   forward / back  (Y)',
                         'Q / E   down / up  (Z)', 'I K / J L / U O   rotate',
                         'Hold Space   grab selected', 'Shift   fine movement',
                         'C   follow / clutch', 'F   pointer to selection',
                         'R   rebase, no jump', 'Enter   finish | Esc   cancel grab',
                         'Object Mode only · no sculpt yet'):
                box.label(text=line)


def _draw_hud():
    if not RUNTIME.running or bpy.context.scene != RUNTIME.scene:
        return
    region = bpy.context.region
    if region is None or region.width < 300:
        return
    scale = bpy.context.preferences.system.ui_scale
    x, y = 78*scale, region.height-105*scale
    lines = [
        ('SPATIAL POINTER  /  ' + ('PC TEST' if RUNTIME.source == 'KEYBOARD' else 'UDP INPUT'), 18),
        (RUNTIME.status, 13),
        (f'X {RUNTIME.pose.position[0]:+.2f}   Y {RUNTIME.pose.position[1]:+.2f}   Z {RUNTIME.pose.position[2]:+.2f}', 13),
        ('SPACE: grab   C: clutch   SHIFT: fine   ENTER: stop' if RUNTIME.source == 'KEYBOARD' else
         f'Packets {RUNTIME.packets}   |   N-panel > Spatial to stop', 12),
    ]
    for i, (text, size) in enumerate(lines):
        blf.size(0, int(size*scale))
        blf.position(0, x, y, 0)
        blf.color(0, .15, .82, 1, 1) if i == 0 else blf.color(0, .92, .94, .98, 1)
        blf.draw(0, text)
        y -= (size+9)*scale


@persistent
def _before_data_change(*args):
    RUNTIME.stop(message='Stopped after file/undo/render event')
    _stop_keyboard_handlers()
    RUNTIME.history.clear()
    RUNTIME.helpers = {}
    RUNTIME.scene = None


_CLASSES = (
    SPATIALPOINTER_Settings, SPATIALPOINTER_OT_demo, SPATIALPOINTER_OT_create,
    SPATIALPOINTER_OT_keyboard, SPATIALPOINTER_OT_network, SPATIALPOINTER_OT_stop,
    SPATIALPOINTER_OT_grab, SPATIALPOINTER_OT_release, SPATIALPOINTER_OT_cancel_grab,
    SPATIALPOINTER_OT_restore, SPATIALPOINTER_OT_snap, SPATIALPOINTER_OT_recenter,
    SPATIALPOINTER_OT_token, SPATIALPOINTER_OT_remove, SPATIALPOINTER_PT_main,
)
_HANDLER_NAMES = ('load_pre', 'undo_pre', 'redo_pre', 'render_pre')


def register():
    global _REGISTERED, _DRAW_HANDLE
    if _REGISTERED:
        return
    registered = []
    try:
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.Scene.spatial_pointer_settings = PointerProperty(type=SPATIALPOINTER_Settings)
        for name in _HANDLER_NAMES:
            handlers = getattr(bpy.app.handlers, name)
            if _before_data_change not in handlers:
                handlers.append(_before_data_change)
        if not bpy.app.background:
            _DRAW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(_draw_hud, (), 'WINDOW', 'POST_PIXEL')
        _REGISTERED = True
    except Exception:
        for name in _HANDLER_NAMES:
            handlers = getattr(bpy.app.handlers, name)
            if _before_data_change in handlers:
                handlers.remove(_before_data_change)
        if hasattr(bpy.types.Scene, 'spatial_pointer_settings'):
            del bpy.types.Scene.spatial_pointer_settings
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
        raise


def unregister():
    global _REGISTERED, _DRAW_HANDLE
    RUNTIME.stop()
    _stop_keyboard_handlers()
    RUNTIME.history.clear()
    RUNTIME.helpers = {}
    RUNTIME.scene = None
    if _DRAW_HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW_HANDLE, 'WINDOW')
        _DRAW_HANDLE = None
    for name in _HANDLER_NAMES:
        handlers = getattr(bpy.app.handlers, name)
        if _before_data_change in handlers:
            handlers.remove(_before_data_change)
    if hasattr(bpy.types.Scene, 'spatial_pointer_settings'):
        del bpy.types.Scene.spatial_pointer_settings
    if _REGISTERED:
        for cls in reversed(_CLASSES):
            bpy.utils.unregister_class(cls)
    _REGISTERED = False
