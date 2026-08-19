#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interactive tools for BlendMark:

* a modal operator to click-add / drag-move / delete landmarks,
* a modal operator to draw a stroke over the target surface and turn it into
  equally-spaced semilandmarks,
* an operator that builds the same semilandmarks from an edge path selected in
  Edit Mode, when following the real mesh topology matters.
"""

import bmesh
import bpy
from bpy.props import IntProperty
from bpy.types import Operator
from bpy_extras.view3d_utils import location_3d_to_region_2d

from mathutils import Vector

from . import overlay
from .utils import (
    get_active_landmark_set, is_landmark_set, next_curve_id, next_landmark_name,
    order_selected_edge_path, pick_target_point, resample_polyline,
)

PICK_TOLERANCE_PX = 14
# Minimum screen-space gap between two samples of a freehand stroke; keeps the
# raw stroke light without losing detail before it is resampled.
MIN_SAMPLE_DIST_PX = 4.0

# Set by the "Finish Editing" button so a running modal tool can stop itself;
# the modal polls it on its timer.
_stop_requested = False


def request_stop():
    global _stop_requested
    _stop_requested = True


class _ModalToolMixin:
    """
    Shared plumbing for BlendMark's modal viewport tools: locating the 3D
    viewport region, hit-testing the pointer against it, and tearing down
    cleanly.
    """

    def _init_tool(self, context, status_text, hint):
        global _stop_requested

        landmark_set = get_active_landmark_set(context)
        if landmark_set is None:
            self.report({'ERROR'}, "Active object must be a BlendMark landmark set (use 'New Landmark Set' first)")
            return False

        target = landmark_set.blendmark_target
        if target is None:
            self.report({'ERROR'}, f"'{landmark_set.name}' has no target object. Set one in the panel first")
            return False

        if overlay.is_tool_active():
            self.report({'ERROR'}, "Another BlendMark tool is running. Finish it first")
            return False

        # The operator is launched from the sidebar, so context.region is the UI
        # region: find the actual 3D viewport region to hit-test against.
        region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if region is None or context.space_data.region_3d is None:
            self.report({'ERROR'}, "Could not find the 3D viewport region")
            return False

        self.landmark_set = landmark_set
        self.target = target
        self.area = context.area
        self.region = region
        self.rv3d = context.space_data.region_3d

        _stop_requested = False
        overlay.set_tool_state(active=True, set_name=landmark_set.name,
                               target_name=target.name, region=region,
                               hover_index=-1, stroke=[], hint=hint)

        context.workspace.status_text_set(status_text)
        self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        context.window_manager.modal_handler_add(self)
        return True

    def _mouse_over_overlapping_region(self, event):
        """
        True when the pointer sits over the sidebar, toolbar, header or any
        other region of this area. With region overlap enabled (the default)
        those are drawn *on top of* the viewport's WINDOW region, which still
        reports them as inside its own bounds -- so they must be excluded
        explicitly or clicks meant for a panel button land in the viewport.
        """
        for region in self.area.regions:
            if region.type == 'WINDOW':
                continue
            if region.width <= 1 or region.height <= 1:  # collapsed/hidden
                continue
            if (region.x <= event.mouse_x < region.x + region.width and
                    region.y <= event.mouse_y < region.y + region.height):
                return True
        return False

    def _mouse_in_region(self, event):
        """Pointer position relative to the viewport region, and whether it is usable."""
        x = event.mouse_x - self.region.x
        y = event.mouse_y - self.region.y
        inside = (
            0 <= x < self.region.width
            and 0 <= y < self.region.height
            and not self._mouse_over_overlapping_region(event)
        )
        return inside, (x, y)

    def _redraw(self):
        try:
            self.area.tag_redraw()
        except (AttributeError, ReferenceError):
            pass

    def _area_is_alive(self, context):
        try:
            return self.area in list(context.screen.areas)
        except (AttributeError, ReferenceError):
            return False

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        overlay.set_tool_state(active=False, hover_index=-1, set_name="",
                               target_name="", region=None, stroke=[], hint="")
        self._redraw()
        return {'FINISHED'}

    def cancel(self, context):
        self._finish(context)


class VIEW3D_OT_BlendMark_EditPointsOperator(_ModalToolMixin, Operator):
    bl_idname = "view3d.blendmark_edit_points"
    bl_label = "Edit Landmarks"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = (
        "Click on the target object to add a landmark, drag an existing marker "
        "to move it, hover a marker and press X to delete it. "
        "Esc, Enter, right-click or the Finish button ends the tool"
    )

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        self.drag_index = None
        self.hover_index = -1
        status = "LMB: add / drag point   |   X: delete hovered point   |   Esc, Enter or RMB: finish"
        if not self._init_tool(context, status, "LMB add/drag  ·  X delete"):
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _pick(self, coord):
        best_index, best_dist = -1, PICK_TOLERANCE_PX
        mouse = Vector(coord)
        for i, point in enumerate(self.landmark_set.blendmark_points):
            co_2d = location_3d_to_region_2d(self.region, self.rv3d, point.co)
            if co_2d is None:
                continue
            dist = (co_2d - mouse).length
            if dist < best_dist:
                best_index, best_dist = i, dist
        return best_index

    def _new_point_name(self, context):
        if context.scene.blendmark_use_auto_naming:
            return next_landmark_name(self.landmark_set)
        name = context.scene.new_landmark.strip()
        return name if name else next_landmark_name(self.landmark_set)

    def _set_hover(self, index):
        if index != self.hover_index:
            self.hover_index = index
            overlay.set_tool_state(hover_index=index)
            self._redraw()

    def modal(self, context, event):
        if _stop_requested or not self._area_is_alive(context):
            return self._finish(context)

        if event.type == 'TIMER':
            return {'PASS_THROUGH'}

        if event.type in {'ESC', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._finish(context)

        inside, coord = self._mouse_in_region(event)

        # Over a panel, the header or another area: never place points there,
        # just let Blender handle the event normally.
        if not inside:
            self._set_hover(-1)
            self.drag_index = None
            return {'PASS_THROUGH'}

        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            return self._finish(context)

        if event.type == 'MOUSEMOVE':
            if self.drag_index is not None:
                co = pick_target_point(self.target, self.region, self.rv3d, coord)
                if co is not None:
                    self.landmark_set.blendmark_points[self.drag_index].co = co
                self._redraw()
                return {'RUNNING_MODAL'}
            self._set_hover(self._pick(coord))
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                hit = self._pick(coord)
                if hit != -1:
                    self.drag_index = hit
                    self.landmark_set.blendmark_active_index = hit
                    self._redraw()
                    return {'RUNNING_MODAL'}

                co = pick_target_point(self.target, self.region, self.rv3d, coord)
                if co is None:
                    # Clicked past the object: placing a landmark in mid-air
                    # would be meaningless, so ignore it.
                    self.report({'WARNING'}, f"Click on '{self.target.name}' to place a landmark")
                    return {'RUNNING_MODAL'}

                point = self.landmark_set.blendmark_points.add()
                point.point_name = self._new_point_name(context)
                point.co = co
                point.kind = 'LANDMARK'
                self.landmark_set.blendmark_active_index = len(self.landmark_set.blendmark_points) - 1
                self.drag_index = self.landmark_set.blendmark_active_index
                self._redraw()
            elif event.value == 'RELEASE':
                self.drag_index = None
            return {'RUNNING_MODAL'}

        if event.type in {'X', 'DEL'} and event.value == 'PRESS':
            hit = self._pick(coord)
            if hit != -1:
                self.landmark_set.blendmark_points.remove(hit)
                self.drag_index = None
                self.landmark_set.blendmark_active_index = min(
                    self.landmark_set.blendmark_active_index,
                    len(self.landmark_set.blendmark_points) - 1,
                )
                self._set_hover(-1)
                self._redraw()
            return {'RUNNING_MODAL'}

        # Everything else (navigation, shortcuts) behaves as usual.
        return {'PASS_THROUGH'}


class VIEW3D_OT_BlendMark_DrawCurveOperator(_ModalToolMixin, Operator):
    bl_idname = "view3d.blendmark_draw_curve"
    bl_label = "Draw Curve on Surface"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = (
        "Drag across the target object to draw a stroke on its surface; on "
        "release the stroke is resampled into equally-spaced semilandmarks. "
        "Keep drawing for more curves, then Esc, Enter, right-click or Finish"
    )

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        self.drawing = False
        self.stroke = []
        self.last_sample_2d = None
        status = "LMB drag: draw a curve on the surface   |   Esc, Enter or RMB: finish"
        if not self._init_tool(context, status, "LMB drag to draw a curve"):
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _sample(self, coord):
        """Add a stroke sample if the pointer hit the surface and has moved enough."""
        current = Vector(coord)
        if self.last_sample_2d is not None and (current - self.last_sample_2d).length < MIN_SAMPLE_DIST_PX:
            return

        co = pick_target_point(self.target, self.region, self.rv3d, coord)
        if co is None:
            # Pointer wandered off the object; resume sampling when it returns.
            return

        self.stroke.append(co)
        self.last_sample_2d = current
        overlay.set_tool_state(stroke=list(self.stroke))
        self._redraw()

    def _finalize_stroke(self, context):
        stroke, self.stroke = self.stroke, []
        self.last_sample_2d = None
        overlay.set_tool_state(stroke=[])
        self._redraw()

        if len(stroke) < 2:
            self.report({'WARNING'}, f"Draw a stroke across '{self.target.name}' to create a curve")
            return

        num_points = context.scene.blendmark_curve_points
        try:
            resampled = resample_polyline(stroke, num_points)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return

        curve_id = next_curve_id(self.landmark_set)
        for i, co in enumerate(resampled, start=1):
            point = self.landmark_set.blendmark_points.add()
            point.point_name = f"C.{curve_id}.{i:02d}"
            point.co = co
            point.kind = 'SEMI'
            point.curve_id = curve_id
            point.curve_index = i

        self.landmark_set.blendmark_active_index = len(self.landmark_set.blendmark_points) - 1
        self.report({'INFO'}, f"Curve {curve_id}: {num_points} semilandmarks drawn on '{self.target.name}'")

    def modal(self, context, event):
        if _stop_requested or not self._area_is_alive(context):
            if self.drawing:
                self._finalize_stroke(context)
            return self._finish(context)

        if event.type == 'TIMER':
            return {'PASS_THROUGH'}

        if event.type in {'ESC', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if self.drawing:
                # Abandon the half-drawn stroke rather than committing it.
                self.drawing = False
                self.stroke = []
                overlay.set_tool_state(stroke=[])
            return self._finish(context)

        inside, coord = self._mouse_in_region(event)

        if not inside:
            if self.drawing:
                # Dragged out over a panel: close the stroke with what we have.
                self.drawing = False
                self._finalize_stroke(context)
            return {'PASS_THROUGH'}

        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS' and not self.drawing:
            return self._finish(context)

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.drawing = True
                self.stroke = []
                self.last_sample_2d = None
                self._sample(coord)
            elif event.value == 'RELEASE' and self.drawing:
                self.drawing = False
                self._finalize_stroke(context)
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE' and self.drawing:
            self._sample(coord)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}


class VIEW3D_OT_BlendMark_FinishEditingOperator(Operator):
    bl_idname = "view3d.blendmark_finish_editing"
    bl_label = "Finish Editing"
    bl_options = {'REGISTER'}
    bl_description = "Stop the running BlendMark viewport tool"

    def execute(self, context):
        request_stop()
        self.report({'INFO'}, "Finished editing landmarks")
        return {'FINISHED'}


class VIEW3D_OT_BlendMark_GenerateSemilandmarksOperator(Operator):
    bl_idname = "view3d.blendmark_generate_semilandmarks"
    bl_label = "Semilandmarks From Edge Path"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = (
        "Resample the edge path currently selected in Edit Mode on the active "
        "mesh into equally-spaced semilandmarks, stored on the active landmark set"
    )

    num_points: IntProperty(name="Semilandmarks", default=10, min=2, max=500)

    def invoke(self, context, event):
        self.num_points = context.scene.blendmark_curve_points
        return self.execute(context)

    def execute(self, context):
        mesh_obj = context.edit_object
        if mesh_obj is None or mesh_obj.type != 'MESH':
            self.report({'ERROR'}, "Enter Edit Mode on the mesh and select a connected edge path")
            return {'CANCELLED'}

        landmark_set = None
        for obj in bpy.data.objects:
            if is_landmark_set(obj) and obj.blendmark_target == mesh_obj:
                landmark_set = obj
                break
        if landmark_set is None:
            self.report({'ERROR'}, f"No landmark set targets '{mesh_obj.name}'. Create one with 'New Landmark Set' first")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(mesh_obj.data)
        ordered_verts = order_selected_edge_path(bm)
        if ordered_verts is None:
            self.report({'ERROR'}, "Selection must be a single connected edge path (no branches)")
            return {'CANCELLED'}

        world_path = [mesh_obj.matrix_world @ v.co for v in ordered_verts]
        try:
            resampled = resample_polyline(world_path, self.num_points)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        curve_id = next_curve_id(landmark_set)
        for i, co in enumerate(resampled, start=1):
            point = landmark_set.blendmark_points.add()
            point.point_name = f"C.{curve_id}.{i:02d}"
            point.co = co
            point.kind = 'SEMI'
            point.curve_id = curve_id
            point.curve_index = i

        self.report({'INFO'}, f"Curve {curve_id}: added {self.num_points} semilandmarks to '{landmark_set.name}'")
        return {'FINISHED'}


classes = (
    VIEW3D_OT_BlendMark_EditPointsOperator,
    VIEW3D_OT_BlendMark_DrawCurveOperator,
    VIEW3D_OT_BlendMark_FinishEditingOperator,
    VIEW3D_OT_BlendMark_GenerateSemilandmarksOperator,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blendmark_use_auto_naming = bpy.props.BoolProperty(
        name="Auto Name", description="Automatically name new landmarks S.1, S.2, ...", default=True,
    )
    bpy.types.Scene.blendmark_curve_points = IntProperty(
        name="Points per Curve",
        description="How many equally-spaced semilandmarks each curve is resampled to",
        default=10, min=2, max=500,
    )


def unregister():
    del bpy.types.Scene.blendmark_curve_points
    del bpy.types.Scene.blendmark_use_auto_naming
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
