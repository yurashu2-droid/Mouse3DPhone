"""Run inside Blender, not ordinary pytest.

blender --background --factory-startup --python tests/blender_smoke.py
This script creates throwaway data and exits nonzero if an assertion fails.
"""
import json
import math
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    import bpy
    from mathutils import Matrix, Quaternion, Vector
    import spatial_pointer
    from spatial_pointer import visuals
    from spatial_pointer.core import Pose, qaxis
    from spatial_pointer.runtime import RUNTIME

    spatial_pointer.register()
    assert hasattr(bpy.types.Scene, 'spatial_pointer_settings')
    original_scene = bpy.context.scene
    original_objects = set(original_scene.objects)
    visuals.ensure_pointer(original_scene, Pose((0, 0, 1)), .12)
    assert original_objects <= set(original_scene.objects)
    helpers = [o for o in original_scene.objects if o.get('_sp_helper')]
    assert len(helpers) >= 4 and all(o.hide_render for o in helpers)

    RUNTIME.start(original_scene, 'KEYBOARD')
    obj = bpy.data.objects.new('Smoke_Target', None)
    original_scene.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation((1, 2, 3))
    saved = obj.matrix_world.copy()
    obj.rotation_mode = 'XYZ'
    obj.lock_rotation_w = True  # Inactive W lock must not block Euler rotation.
    RUNTIME.set_pose(Pose())
    assert RUNTIME.grab(obj)
    RUNTIME.set_pose(Pose((2, 0, 0)))
    RUNTIME.apply_pose()
    assert (obj.matrix_world.translation - Vector((3, 2, 3))).length < 1e-5
    RUNTIME.release(cancel=True)
    assert (obj.matrix_world.translation - saved.translation).length < 1e-5

    RUNTIME.set_pose(Pose())
    assert RUNTIME.grab(obj)
    RUNTIME.set_pose(Pose((0, 0, 0), qaxis((0, 0, 1), math.pi / 2)))
    RUNTIME.apply_pose()
    assert (obj.matrix_world.translation - Vector((-2, 1, 3))).length < 1e-5
    RUNTIME.release()
    assert RUNTIME.restore_last()
    assert (obj.matrix_world.translation - saved.translation).length < 1e-5
    RUNTIME.stop()
    assert not RUNTIME.grab(obj), 'Stopped input must not grab through a direct operator call'

    old_scenes = set(bpy.data.scenes)
    demo = visuals.create_demo(bpy.context)
    assert original_scene in list(bpy.data.scenes)
    assert demo.get('_sp_demo')
    assert len(set(bpy.data.scenes) - old_scenes) == 1
    assert original_objects <= set(original_scene.objects)
    assert visuals.create_demo(bpy.context) == demo
    RUNTIME.history.append((obj, saved.copy()))
    RUNTIME.start(demo, 'KEYBOARD')
    assert not RUNTIME.history, 'History must not leak into a different scene'
    RUNTIME.stop()

    spatial_pointer.unregister()
    assert not RUNTIME.running
    assert not hasattr(bpy.types.Scene, 'spatial_pointer_settings')
    spatial_pointer.register()
    spatial_pointer.unregister()
    print('SPATIAL_POINTER_BLENDER_SMOKE: PASS')
    print(json.dumps({'blender': bpy.app.version_string, 'result': 'PASS'}))


if __name__ == '__main__':
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
