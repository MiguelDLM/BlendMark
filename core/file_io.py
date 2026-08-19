#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Folder/reference-file handling and CSV export for BlendMark.
"""

import os

import bpy
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .utils import get_active_landmark_set


class VIEW3D_OT_BlendMark_BrowseFolderOperator(Operator, ImportHelper):
    bl_idname = "view3d.blendmark_browse_folder"
    bl_label = "Browse Folder"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select the folder where exported files will be stored"

    def execute(self, context):
        context.scene.selected_folder = self.filepath
        self.report({'INFO'}, f"Selected folder: {self.filepath}")
        return {'FINISHED'}


class VIEW3D_OT_BlendMark_ImportDataOperator(Operator, ImportHelper):
    bl_idname = "view3d.blendmark_import_data"
    bl_label = "Import Data"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import reference images or 3D models to the scene"

    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        bpy.ops.view3d.view_axis(type='TOP')

        files_imported = 0
        last_imported = None
        for file_elem in self.files:
            filepath = self.directory + file_elem.name
            file_extension = file_elem.name.split('.')[-1].lower()

            if file_extension in {'jpg', 'jpeg', 'png', 'bmp', 'tiff'}:
                bpy.ops.object.empty_image_add(
                    filepath=filepath, relative_path=True, align='VIEW',
                    location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), background=False,
                )
                imported_object = context.view_layer.objects.active
                if imported_object and imported_object.type == 'EMPTY' and imported_object.empty_display_type == 'IMAGE':
                    imported_object.name = file_elem.name.rsplit('.', 1)[0]
                    last_imported = imported_object
                    files_imported += 1

            elif file_extension in {'obj', 'stl', 'ply'}:
                if file_extension == 'obj':
                    bpy.ops.wm.obj_import(filepath=filepath)
                elif file_extension == 'stl':
                    bpy.ops.wm.stl_import(filepath=filepath)
                elif file_extension == 'ply':
                    bpy.ops.wm.ply_import(filepath=filepath)

                imported_object = context.view_layer.objects.active
                if imported_object and imported_object.type == 'MESH':
                    imported_object.name = file_elem.name.rsplit('.', 1)[0]
                    last_imported = imported_object
                    files_imported += 1

        # Pre-fill the target so the user can go straight to digitizing.
        if last_imported is not None and context.scene.blendmark_target_object is None:
            context.scene.blendmark_target_object = last_imported

        self.report({'INFO'}, f"Imported {files_imported} file(s)")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class VIEW3D_OT_BlendMark_ExportCSVOperator(Operator):
    bl_idname = "view3d.blendmark_export_csv"
    bl_label = "Export CSV"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export the active landmark set's points to a CSV file (name, X, Y, Z)"

    def execute(self, context):
        selected_folder = context.scene.selected_folder
        if not selected_folder:
            self.report({'ERROR'}, "Please select a folder to export the landmarks")
            return {'CANCELLED'}

        landmark_set = get_active_landmark_set(context)
        if landmark_set is None:
            self.report({'ERROR'}, "Active object is not a BlendMark landmark set")
            return {'CANCELLED'}

        if len(landmark_set.blendmark_points) == 0:
            self.report({'WARNING'}, "Landmark set is empty, nothing to export")
            return {'CANCELLED'}

        csv_filename = os.path.join(selected_folder, f"{landmark_set.name}.csv")
        with open(csv_filename, 'w') as f:
            f.write("Landmark, X, Y, Z\n")
            for p in landmark_set.blendmark_points:
                f.write(f"{p.point_name}, {p.co.x}, {p.co.y}, {p.co.z}\n")

        self.report({'INFO'}, f"Landmarks exported to: {csv_filename}")
        return {'FINISHED'}


classes = (
    VIEW3D_OT_BlendMark_BrowseFolderOperator,
    VIEW3D_OT_BlendMark_ImportDataOperator,
    VIEW3D_OT_BlendMark_ExportCSVOperator,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
