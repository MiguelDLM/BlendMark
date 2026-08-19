#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main BlendMark UI panel.
"""

import bpy

from .overlay import is_tool_active
from .utils import is_landmark_set, is_valid_target


class BLENDMARK_UL_points(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_id = 'MESH_ICOSPHERE' if item.kind == 'LANDMARK' else 'CURVE_BEZCURVE'
        row = layout.row(align=True)
        row.label(text=item.point_name, icon=icon_id)
        row.label(text=f"{item.co.x:.2f}, {item.co.y:.2f}, {item.co.z:.2f}")


class VIEW3D_PT_BlendMark_Panel_PT(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_BlendMark_Panel_PT"
    bl_label = "BlendMark"
    bl_category = "BlendMark"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'HEADER_LAYOUT_EXPAND'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        landmark_set = context.active_object if is_landmark_set(context.active_object) else None
        tool_active = is_tool_active()

        box = layout.box()
        box.label(text="Storage location", icon='FILE_FOLDER')
        row = box.row()
        row.operator("view3d.blendmark_browse_folder", text="Browse Folder", icon='FILE_FOLDER')
        row.prop(scene, "selected_folder", text="")

        layout.separator()
        box = layout.box()
        box.label(text="Import reference data", icon='IMAGE_DATA')
        box.operator("view3d.blendmark_import_data", text="Import Image / Mesh", icon='IMPORT')

        layout.separator()
        box = layout.box()
        box.label(text="Target object", icon='EYEDROPPER')
        box.prop(scene, "blendmark_target_object", text="")
        target_object = scene.blendmark_target_object
        if target_object is None:
            box.label(text="Pick the object to digitize", icon='INFO')
        elif not is_valid_target(target_object):
            box.label(text="Must be a mesh or image empty", icon='ERROR')
        else:
            box.label(text="Landmarks land on this object only", icon='CHECKMARK')

        layout.separator()
        box = layout.box()
        box.label(text="Landmark set", icon='EMPTY_AXIS')

        if landmark_set is None:
            box.operator("view3d.blendmark_new_landmark_set", text="New Landmark Set", icon='ADD')
        else:
            col = box.column(align=True)
            col.label(text=f"Active set: {landmark_set.name}", icon='EMPTY_AXIS')
            n_landmarks = sum(1 for p in landmark_set.blendmark_points if p.kind == 'LANDMARK')
            n_semi = len(landmark_set.blendmark_points) - n_landmarks
            col.label(text=f"{n_landmarks} landmarks, {n_semi} semilandmarks")

            col = box.column(align=True)
            col.label(text="Placing landmarks on:")
            col.prop(landmark_set, "blendmark_target", text="")

            row = box.row(align=True)
            row.prop(scene, "blendmark_use_auto_naming", text="Auto Name")
            sub = row.row(align=True)
            sub.enabled = not scene.blendmark_use_auto_naming
            sub.prop(scene, "new_landmark", text="")

            if tool_active:
                col = box.column(align=True)
                col.alert = True
                col.scale_y = 1.5
                col.operator("view3d.blendmark_finish_editing", text="Finish Editing", icon='CHECKMARK')
                box.label(text="Esc / Enter / right-click also finish", icon='INFO')
            else:
                row = box.row()
                row.enabled = landmark_set.blendmark_target is not None
                row.scale_y = 1.4
                row.operator("view3d.blendmark_edit_points", text="Edit Landmarks", icon='GREASEPENCIL')
                if landmark_set.blendmark_target is None:
                    box.label(text="Set the target object above first", icon='ERROR')

            box.template_list(
                "BLENDMARK_UL_points", "", landmark_set, "blendmark_points",
                landmark_set, "blendmark_active_index", rows=4,
            )
            row = box.row(align=True)
            row.operator("view3d.blendmark_delete_point", text="Delete Point", icon='X')
            row.operator("view3d.blendmark_delete_curve", text="Delete Curve", icon='TRASH')

            box.operator("view3d.blendmark_new_landmark_set", text="New Landmark Set", icon='ADD')

        layout.separator()
        box = layout.box()
        box.label(text="Semilandmark curves", icon='CURVE_DATA')
        box.prop(scene, "blendmark_curve_points", text="Points per Curve")

        col = box.column(align=True)
        col.enabled = landmark_set is not None and landmark_set.blendmark_target is not None and not tool_active
        col.scale_y = 1.4
        col.operator("view3d.blendmark_draw_curve", text="Draw Curve on Surface", icon='GREASEPENCIL')

        col = box.column(align=True)
        col.enabled = not tool_active
        col.label(text="or, from an edge path in Edit Mode:")
        col.operator("view3d.blendmark_generate_semilandmarks", text="From Selected Edge Path", icon='IPO_EASE_IN_OUT')

        layout.separator()
        box = layout.box()
        box.label(text="Viewport display", icon='RESTRICT_VIEW_OFF')
        row = box.row()
        row.prop(scene, "blendmark_point_size", text="Point Size")
        row.prop(scene, "blendmark_show_labels", text="Labels", toggle=True)
        box.operator("view3d.blendmark_toggle_overlay", text="Show/Hide Landmark Set", icon='HIDE_OFF')

        layout.separator()
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        box.operator("view3d.blendmark_export_pts", text="Export .pts", icon='EXPORT')
        box.operator("view3d.blendmark_export_all_pts", text="Export All Sets to Folder", icon='EXPORT')
        box.operator("view3d.blendmark_export_csv", text="Export CSV", icon='EXPORT')

        layout.separator()
        box = layout.box()
        box.label(text="Import", icon='IMPORT')
        box.operator("view3d.blendmark_import_pts", text="Import .pts", icon='IMPORT')


classes = (
    BLENDMARK_UL_points,
    VIEW3D_PT_BlendMark_Panel_PT,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
