#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Viewport overlay for BlendMark landmarks/semilandmarks.

Points are never turned into mesh geometry: they are drawn every frame as
screen-space circles (and connecting lines for semilandmark curves) using the
`gpu` module, the same approach used by the aligner-blender add-on. This
keeps the scene free of extra geometry and makes points trivial to move.
"""

import colorsys
import hashlib
import math

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import location_3d_to_region_2d

from .utils import is_landmark_set

LANDMARK_COLOR = (1.0, 0.55, 0.05, 1.0)
ACTIVE_COLOR = (1.0, 1.0, 0.15, 1.0)
HOVER_COLOR = (1.0, 1.0, 1.0, 1.0)
STROKE_COLOR = (0.25, 0.9, 1.0, 0.95)
BANNER_BG = (0.05, 0.05, 0.05, 0.75)
POINT_SEGMENTS = 16

# State of the interactive editing tool, kept here so the overlay can show what
# is going on and the panel can offer a "Finish" button (see landmark_ops.py).
TOOL_STATE = {
    "active": False,
    "set_name": "",
    "target_name": "",
    "hover_index": -1,
    "region": None,
    # World-space points of the freehand stroke currently being drawn.
    "stroke": [],
    "hint": "",
}


def set_tool_state(**kwargs):
    TOOL_STATE.update(kwargs)


def is_tool_active():
    return TOOL_STATE["active"]


_handler = None
_shader = None


def _get_shader():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


def _curve_color(curve_id):
    h = int(hashlib.md5(str(curve_id).encode()).hexdigest(), 16)
    hue = (h % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.95)
    return (r, g, b, 1.0)


def _circle_verts(cx, cy, radius, segments=POINT_SEGMENTS):
    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        verts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return verts


def _draw_filled_circle(cx, cy, radius, color):
    shader = _get_shader()
    verts = _circle_verts(cx, cy, radius)
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": verts})
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_line_strip(points_2d, color, width=2.0):
    if len(points_2d) < 2:
        return
    shader = _get_shader()
    gpu.state.line_width_set(width)
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points_2d})
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)


def _draw_label(cx, cy, text):
    font_id = 0
    blf.position(font_id, cx + 8, cy + 6, 0)
    blf.size(font_id, 12)
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
    blf.draw(font_id, text)


def _draw_rect(x0, y0, x1, y1, color):
    shader = _get_shader()
    verts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": verts})
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_tool_banner(region):
    """Make it obvious the modal tool is running, and how to leave it."""
    font_id = 0
    text = (
        f"BlendMark: editing '{TOOL_STATE['set_name']}' on '{TOOL_STATE['target_name']}'  ·  "
        f"{TOOL_STATE['hint']}  ·  Esc/Enter/RMB finish"
    )
    blf.size(font_id, 12)
    text_width, text_height = blf.dimensions(font_id, text)

    margin, padding = 12, 8
    x0 = margin
    y1 = region.height - margin
    y0 = y1 - text_height - padding * 2
    _draw_rect(x0, y0, x0 + text_width + padding * 2, y1, BANNER_BG)

    blf.position(font_id, x0 + padding, y0 + padding, 0)
    blf.color(font_id, 1.0, 0.75, 0.25, 1.0)
    blf.draw(font_id, text)


def _draw_callback():
    context = bpy.context
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return

    scene = context.scene
    radius = max(2.0, getattr(scene, "blendmark_point_size", 6.0))
    show_labels = getattr(scene, "blendmark_show_labels", True)
    active_set = context.active_object if is_landmark_set(context.active_object) else None
    hover_index = TOOL_STATE["hover_index"] if TOOL_STATE["active"] else -1

    gpu.state.blend_set('ALPHA')

    for obj in context.visible_objects:
        if not is_landmark_set(obj):
            continue

        points = obj.blendmark_points
        curves = {}
        is_active_set = obj is active_set
        active_index = obj.blendmark_active_index if is_active_set else -1

        for i, point in enumerate(points):
            co_2d = location_3d_to_region_2d(region, rv3d, point.co)
            if co_2d is None:
                continue

            if point.kind == 'SEMI':
                curves.setdefault(point.curve_id, []).append((point.curve_index, co_2d))
                color = _curve_color(point.curve_id)
                point_radius = radius * 0.6
            else:
                color = LANDMARK_COLOR
                point_radius = radius

            if is_active_set and i == hover_index:
                _draw_filled_circle(co_2d.x, co_2d.y, point_radius + 5, HOVER_COLOR)

            if i == active_index:
                _draw_filled_circle(co_2d.x, co_2d.y, point_radius + 3, ACTIVE_COLOR)

            _draw_filled_circle(co_2d.x, co_2d.y, point_radius, color)

            if show_labels:
                _draw_label(co_2d.x, co_2d.y, point.point_name)

        for curve_id, entries in curves.items():
            entries.sort(key=lambda e: e[0])
            _draw_line_strip([e[1] for e in entries], _curve_color(curve_id))

    if TOOL_STATE["active"] and TOOL_STATE["region"] == region:
        stroke = TOOL_STATE["stroke"]
        if stroke:
            stroke_2d = [location_3d_to_region_2d(region, rv3d, co) for co in stroke]
            _draw_line_strip([p for p in stroke_2d if p is not None], STROKE_COLOR, width=3.0)
        _draw_tool_banner(region)

    gpu.state.blend_set('NONE')


def register_overlay():
    global _handler
    if _handler is None:
        _handler = bpy.types.SpaceView3D.draw_handler_add(_draw_callback, (), 'WINDOW', 'POST_PIXEL')


def unregister_overlay():
    global _handler
    if _handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, 'WINDOW')
        _handler = None
    set_tool_state(active=False, set_name="", target_name="", hover_index=-1,
                   region=None, stroke=[], hint="")


class VIEW3D_OT_BlendMark_ToggleOverlayOperator(bpy.types.Operator):
    bl_idname = "view3d.blendmark_toggle_overlay"
    bl_label = "Show/Hide Landmarks"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Toggle viewport visibility of the active landmark set"

    def execute(self, context):
        obj = context.active_object
        if not is_landmark_set(obj):
            self.report({'ERROR'}, "Active object is not a BlendMark landmark set")
            return {'CANCELLED'}
        obj.hide_viewport = not obj.hide_viewport
        state = "hidden" if obj.hide_viewport else "visible"
        self.report({'INFO'}, f"Landmark set '{obj.name}' is now {state}")
        return {'FINISHED'}


classes = (VIEW3D_OT_BlendMark_ToggleOverlayOperator,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blendmark_point_size = bpy.props.FloatProperty(
        name="Point Size", description="Screen-space radius of landmark markers, in pixels",
        default=6.0, min=2.0, max=30.0,
    )
    bpy.types.Scene.blendmark_show_labels = bpy.props.BoolProperty(
        name="Show Labels", description="Draw landmark names next to their markers", default=True,
    )
    register_overlay()


def unregister():
    unregister_overlay()
    del bpy.types.Scene.blendmark_show_labels
    del bpy.types.Scene.blendmark_point_size
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
