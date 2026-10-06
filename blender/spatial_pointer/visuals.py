# SPDX-License-Identifier: GPL-3.0-or-later
"""Tagged viewport helpers and an opt-in, non-destructive practice scene."""
from __future__ import annotations
import math
import bpy
import bmesh
from mathutils import Euler, Matrix, Quaternion, Vector
from .core import Pose


def pose_matrix(pose: Pose) -> Matrix:
    return Matrix.Translation(pose.position) @ Quaternion(pose.rotation).to_matrix().to_4x4()


def _material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = color
    return mat


def _collection(scene):
    for col in scene.collection.children:
        if col.get('_sp_helper_collection'):
            return col
    col = bpy.data.collections.new('SP · Viewport Helpers')
    col['_sp_helper_collection'] = True
    scene.collection.children.link(col)
    return col


def _helper(collection, name, data, role):
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj['_sp_helper'] = True
    obj['_sp_role'] = role
    obj.hide_render = True
    obj.hide_select = True
    obj.show_in_front = True
    return obj


def find_helpers(scene):
    return {obj.get('_sp_role'): obj for obj in scene.objects if obj.get('_sp_helper')}


def sphere_mesh(name, radius=1.0):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    for face in mesh.polygons:
        face.use_smooth = True
    return mesh


def ensure_pointer(scene, pose: Pose, radius: float):
    col = _collection(scene)
    helpers = find_helpers(scene)
    cyan = _material('SP · Pointer Cyan', (.04, .62, .95, 1))
    amber = _material('SP · Grab Amber', (1.0, .42, .06, 1))
    if 'pointer' not in helpers:
        mesh = sphere_mesh('SP · Pointer Mesh')
        mesh.materials.append(cyan)
        helpers['pointer'] = _helper(col, 'SP · 3D Pointer', mesh, 'pointer')
    root = helpers['pointer']
    if 'axes' not in helpers:
        axes = _helper(col, 'SP · Orientation', None, 'axes')
        axes.empty_display_type = 'ARROWS'
        axes.empty_display_size = 3.4
        axes.parent = root
        helpers['axes'] = axes
    if 'halo' not in helpers:
        halo = _helper(col, 'SP · Pointer Outline', None, 'halo')
        halo.empty_display_type = 'SPHERE'
        halo.empty_display_size = 1.5
        halo.parent = root
        helpers['halo'] = halo
    if 'floor' not in helpers:
        floor = _helper(col, 'SP · Ground Projection', None, 'floor')
        floor.empty_display_type = 'CIRCLE'
        floor.empty_display_size = .25
        # Blender circle empties lie in local XY; no rotation needed.
        helpers['floor'] = floor
    if 'stem' not in helpers:
        curve = bpy.data.curves.new('SP · Depth Guide', type='CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = .006
        curve.bevel_resolution = 0
        spline = curve.splines.new('POLY')
        spline.points.add(1)
        curve.materials.append(cyan)
        helpers['stem'] = _helper(col, 'SP · Depth Guide', curve, 'stem')
    apply_pointer(helpers, pose, radius, grabbed=False, following=True)
    return helpers


def apply_pointer(helpers, pose: Pose, radius: float, grabbed: bool, following: bool):
    root = helpers['pointer']
    root.matrix_world = pose_matrix(pose) @ Matrix.Scale(radius, 4)
    name = 'SP · Grab Amber' if grabbed else 'SP · Pointer Cyan'
    mat = bpy.data.materials.get(name)
    if mat is not None and root.data.materials:
        if root.data.materials[0] != mat:
            root.data.materials[0] = mat
    root.color = (1, .42, .06, 1) if grabbed else (.04, .62, .95, 1)
    x, y, z = pose.position
    helpers['floor'].location = (x, y, .025)
    helpers['floor'].empty_display_size = radius*2
    points = helpers['stem'].data.splines[0].points
    points[0].co = (x, y, .025, 1)
    points[1].co = (x, y, z, 1)
    helpers['halo'].empty_display_size = 1.8 if not following else 1.5


def remove_helpers(scene):
    for obj in list(scene.objects):
        if obj.get('_sp_helper'):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)
    for col in list(scene.collection.children):
        if col.get('_sp_helper_collection') and not col.objects and not col.children:
            bpy.data.collections.remove(col)


def _cube_mesh(name):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _demo_obj(scene, name, mesh, pos, mat):
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.location = pos
    mesh.materials.append(mat)
    return obj


def create_demo(context):
    """Create/reopen our own scene. Never clear the user's current scene."""
    scene = next((s for s in bpy.data.scenes if s.get('_sp_demo')), None)
    if scene is None:
        scene = bpy.data.scenes.new('Spatial Pointer Lab')
        scene['_sp_demo'] = True
        target = _demo_obj(scene, 'Practice Cube', _cube_mesh('SP Lab Cube'), (0, 0, 1),
                           _material('SP Lab · Coral', (.95, .24, .13, 1)))
        bevel = target.modifiers.new('Soft edges', 'BEVEL')
        bevel.width, bevel.segments = .08, 3
        _demo_obj(scene, 'Practice Sphere', sphere_mesh('SP Lab Sphere', .6), (2.3, 1.0, .6),
                  _material('SP Lab · Blue', (.08, .30, .72, 1)))
        small = _demo_obj(scene, 'Practice Block', _cube_mesh('SP Lab Block'), (-2.3, 1.0, .8),
                          _material('SP Lab · Lime', (.42, .65, .14, 1)))
        small.scale = (.8, .8, 1.6)
        # The native Blender grid remains the ground plane; no plane hides it.
        scene.cursor.location = (0, 0, 0)
        ensure_pointer(scene, Pose((0, 0, 1)), .12)
    if context.window:
        context.window.scene = scene
        view_layer = context.window.view_layer
        for obj in view_layer.objects:
            obj.select_set(False)
        target = next((o for o in scene.objects if o.name.startswith('Practice Cube')), None)
        if target is not None:
            target.select_set(True)
            view_layer.objects.active = target
        for area in context.window.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_location = (0, 0, 1)
                space.region_3d.view_distance = 8
                space.region_3d.view_rotation = Euler((math.radians(65), 0, math.radians(30)), 'XYZ').to_quaternion()
                space.region_3d.view_perspective = 'PERSP'
                space.show_region_ui = True
                space.overlay.show_floor = True
                space.shading.type = 'SOLID'
                space.shading.color_type = 'MATERIAL'
    return scene


def tag_redraw():
    wm = bpy.context.window_manager
    if wm:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
