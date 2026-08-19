#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data model for BlendMark: landmarks and semilandmarks are stored as plain
points (name + world-space XYZ) in a CollectionProperty on a lightweight
"landmark set" object, instead of real mesh geometry. This is what lets the
add-on show them purely as a viewport overlay (see core/overlay.py).
"""

import bpy
from bpy.types import Operator, PropertyGroup
from bpy.props import (
    StringProperty, FloatVectorProperty, EnumProperty, IntProperty, PointerProperty,
)

from .utils import (
    create_landmark_set, get_active_landmark_set, is_landmark_set, is_valid_target,
)


class BlendMarkPoint(PropertyGroup):
    point_name: StringProperty(name="Name", default="S.1")
    co: FloatVectorProperty(name="Position", size=3, subtype='XYZ')
    kind: EnumProperty(
        name="Kind",
        items=[
            ('LANDMARK', "Landmark", "Fixed anatomical landmark"),
            ('SEMI', "Semilandmark", "Point sampled along a curve"),
        ],
        default='LANDMARK',
    )
    curve_id: IntProperty(name="Curve ID", default=0)
    curve_index: IntProperty(name="Curve Index", default=0)


class VIEW3D_OT_BlendMark_NewLandmarkSetOperator(Operator):
    bl_idname = "view3d.blendmark_new_landmark_set"
    bl_label = "New Landmark Set"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = (
        "Create a new BlendMark landmark set for the object chosen in the "
        "Target Object field. Landmarks/semilandmarks are stored on this new "
        "object and shown as an overlay, no geometry is created."
    )

    def execute(self, context):
        target = context.scene.blendmark_target_object
        if target is None:
            self.report({'ERROR'}, "Pick the object to digitize in the 'Target Object' field first")
            return {'CANCELLED'}
        if not is_valid_target(target):
            self.report({'ERROR'}, f"'{target.name}' must be a mesh or an image empty")
            return {'CANCELLED'}

        name = f"{target.name}_Landmarks"
        existing = bpy.data.objects.get(name)
        if existing and is_landmark_set(existing):
            context.view_layer.objects.active = existing
            existing.select_set(True)
            self.report({'INFO'}, f"'{name}' already exists, made it active")
            return {'FINISHED'}

        landmark_set = create_landmark_set(context, name, target_object=target)
        context.view_layer.objects.active = landmark_set
        for obj in context.selected_objects:
            obj.select_set(False)
        landmark_set.select_set(True)

        self.report({'INFO'}, f"Created landmark set '{name}' targeting '{target.name}'")
        return {'FINISHED'}


class VIEW3D_OT_BlendMark_DeletePointOperator(Operator):
    bl_idname = "view3d.blendmark_delete_point"
    bl_label = "Delete Landmark"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Delete the active landmark/semilandmark from the active landmark set"

    def execute(self, context):
        landmark_set = get_active_landmark_set(context)
        if landmark_set is None:
            self.report({'ERROR'}, "Active object is not a BlendMark landmark set")
            return {'CANCELLED'}

        index = landmark_set.blendmark_active_index
        points = landmark_set.blendmark_points
        if index < 0 or index >= len(points):
            self.report({'ERROR'}, "No point selected")
            return {'CANCELLED'}

        name = points[index].point_name
        points.remove(index)
        landmark_set.blendmark_active_index = min(index, len(points) - 1)
        self.report({'INFO'}, f"Deleted '{name}'")
        return {'FINISHED'}


class VIEW3D_OT_BlendMark_DeleteCurveOperator(Operator):
    bl_idname = "view3d.blendmark_delete_curve"
    bl_label = "Delete Semilandmark Curve"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Delete every semilandmark belonging to the curve of the active point"

    def execute(self, context):
        landmark_set = get_active_landmark_set(context)
        if landmark_set is None:
            self.report({'ERROR'}, "Active object is not a BlendMark landmark set")
            return {'CANCELLED'}

        points = landmark_set.blendmark_points
        index = landmark_set.blendmark_active_index
        if index < 0 or index >= len(points) or points[index].kind != 'SEMI':
            self.report({'ERROR'}, "Select a semilandmark belonging to the curve first")
            return {'CANCELLED'}

        curve_id = points[index].curve_id
        to_remove = [i for i, p in enumerate(points) if p.kind == 'SEMI' and p.curve_id == curve_id]
        for i in reversed(to_remove):
            points.remove(i)

        landmark_set.blendmark_active_index = min(landmark_set.blendmark_active_index, len(points) - 1)
        self.report({'INFO'}, f"Deleted curve {curve_id} ({len(to_remove)} points)")
        return {'FINISHED'}


classes = (
    BlendMarkPoint,
    VIEW3D_OT_BlendMark_NewLandmarkSetOperator,
    VIEW3D_OT_BlendMark_DeletePointOperator,
    VIEW3D_OT_BlendMark_DeleteCurveOperator,
)


def _target_poll(self, obj):
    return is_valid_target(obj)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.blendmark_points = bpy.props.CollectionProperty(type=BlendMarkPoint)
    bpy.types.Object.blendmark_active_index = IntProperty(name="Active Point Index", default=0)
    bpy.types.Object.blendmark_target = PointerProperty(
        name="Target Object",
        description="Mesh or reference image these landmarks are placed on",
        type=bpy.types.Object,
        poll=_target_poll,
    )
    bpy.types.Scene.blendmark_target_object = PointerProperty(
        name="Target Object",
        description="Object to digitize: landmarks can only be placed on this object's surface",
        type=bpy.types.Object,
        poll=_target_poll,
    )


def unregister():
    del bpy.types.Scene.blendmark_target_object
    del bpy.types.Object.blendmark_target
    del bpy.types.Object.blendmark_active_index
    del bpy.types.Object.blendmark_points

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
