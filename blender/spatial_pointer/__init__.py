# SPDX-License-Identifier: GPL-3.0-or-later
"""Spatial Pointer — Blender-first 6DoF input prototype."""


def register():
    from . import addon
    addon.register()


def unregister():
    from . import addon
    addon.unregister()
