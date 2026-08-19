#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import/export of the .pts landmark format:

    Version 1.0
    <point count>
    S.1 <x> <y> <z>
    ...
    C.<curve>.<index> <x> <y> <z>
    ...

"S.N" rows are ordinary landmarks, "C.<curve>.<index>" rows are semilandmarks
sampled along curve <curve>, in order. Both kinds are stored as plain points
on a BlendMark landmark set (see core/landmark_data.py) and drawn as a
viewport overlay only -- no mesh geometry is created.
"""

import os

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .utils import create_landmark_set, get_active_landmark_set, is_landmark_set


class PtsParseError(Exception):
    pass


def parse_pts(filepath):
    """Parse a .pts file into a list of dicts: name, x, y, z, kind, curve_id, curve_index."""
    with open(filepath, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        raise PtsParseError("File is empty")
    if not lines[0].lower().startswith("version"):
        raise PtsParseError(f"Expected a 'Version ...' header, found: '{lines[0]}'")

    # lines[1] is the declared point count; trust the actual rows instead.
    rows = lines[2:]

    points = []
    for line_no, line in enumerate(rows, start=3):
        parts = line.split()
        if len(parts) != 4:
            raise PtsParseError(f"Line {line_no}: expected '<name> <x> <y> <z>', got: '{line}'")
        name, x, y, z = parts
        try:
            x, y, z = float(x), float(y), float(z)
        except ValueError:
            raise PtsParseError(f"Line {line_no}: non-numeric coordinates in '{line}'")

        if name.startswith("S."):
            points.append({"name": name, "co": (x, y, z), "kind": 'LANDMARK', "curve_id": 0, "curve_index": 0})
        elif name.startswith("C."):
            name_parts = name.split(".")
            if len(name_parts) != 3:
                raise PtsParseError(f"Line {line_no}: malformed curve point name '{name}', expected 'C.<curve>.<index>'")
            try:
                curve_id, curve_index = int(name_parts[1]), int(name_parts[2])
            except ValueError:
                raise PtsParseError(f"Line {line_no}: curve/index in '{name}' must be numeric")
            points.append({
                "name": name, "co": (x, y, z), "kind": 'SEMI',
                "curve_id": curve_id, "curve_index": curve_index,
            })
        else:
            raise PtsParseError(f"Line {line_no}: point name '{name}' must start with 'S.' or 'C.'")

    return points


def write_pts(filepath, points):
    """Write points (dicts with name/co/kind, as produced by landmark_set_to_dicts) to a .pts file."""
    landmarks = sorted(
        (p for p in points if p["kind"] == 'LANDMARK'),
        key=lambda p: _landmark_sort_key(p["name"]),
    )
    semis = sorted(
        (p for p in points if p["kind"] == 'SEMI'),
        key=lambda p: (p["curve_id"], p["curve_index"]),
    )
    ordered = landmarks + semis

    with open(filepath, 'w') as f:
        f.write("Version 1.0\n")
        f.write(f"{len(ordered)}\n")
        for p in ordered:
            x, y, z = p["co"]
            f.write(f"{p['name']} {x:.6e} {y:.6e} {z:.6e}\n")


def _landmark_sort_key(name):
    try:
        return int(name.split(".")[1])
    except (ValueError, IndexError):
        return name


def landmark_set_to_dicts(landmark_set):
    result = []
    for p in landmark_set.blendmark_points:
        result.append({
            "name": p.point_name, "co": tuple(p.co), "kind": p.kind,
            "curve_id": p.curve_id, "curve_index": p.curve_index,
        })
    return result


class VIEW3D_OT_BlendMark_ImportPTSOperator(Operator, ImportHelper):
    bl_idname = "view3d.blendmark_import_pts"
    bl_label = "Import .pts"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import landmarks/semilandmarks from a .pts file as a viewport overlay (no mesh is created)"

    filename_ext = ".pts"
    filter_glob: StringProperty(default="*.pts", options={'HIDDEN'})

    def execute(self, context):
        try:
            parsed = parse_pts(self.filepath)
        except (PtsParseError, OSError) as exc:
            self.report({'ERROR'}, f"Could not import '{self.filepath}': {exc}")
            return {'CANCELLED'}

        target = context.scene.blendmark_target_object
        name = os.path.splitext(os.path.basename(self.filepath))[0]
        landmark_set = create_landmark_set(context, name, target_object=target)

        for p in parsed:
            point = landmark_set.blendmark_points.add()
            point.point_name = p["name"]
            point.co = p["co"]
            point.kind = p["kind"]
            point.curve_id = p["curve_id"]
            point.curve_index = p["curve_index"]

        context.view_layer.objects.active = landmark_set
        for obj in context.selected_objects:
            obj.select_set(False)
        landmark_set.select_set(True)

        n_landmarks = sum(1 for p in parsed if p["kind"] == 'LANDMARK')
        n_semi = len(parsed) - n_landmarks
        self.report({'INFO'}, f"Imported {n_landmarks} landmarks and {n_semi} semilandmarks into '{name}'")
        return {'FINISHED'}


class VIEW3D_OT_BlendMark_ExportPTSOperator(Operator, ExportHelper):
    bl_idname = "view3d.blendmark_export_pts"
    bl_label = "Export .pts"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export the active landmark set's landmarks/semilandmarks to a .pts file"

    filename_ext = ".pts"
    filter_glob: StringProperty(default="*.pts", options={'HIDDEN'})

    def invoke(self, context, event):
        landmark_set = get_active_landmark_set(context)
        if landmark_set is None:
            self.report({'ERROR'}, "Active object is not a BlendMark landmark set")
            return {'CANCELLED'}
        self.filepath = f"{landmark_set.name}.pts"
        return super().invoke(context, event)

    def execute(self, context):
        landmark_set = get_active_landmark_set(context)
        if landmark_set is None:
            self.report({'ERROR'}, "Active object is not a BlendMark landmark set")
            return {'CANCELLED'}
        if len(landmark_set.blendmark_points) == 0:
            self.report({'WARNING'}, "Landmark set is empty, nothing to export")
            return {'CANCELLED'}

        write_pts(self.filepath, landmark_set_to_dicts(landmark_set))
        self.report({'INFO'}, f"Exported {len(landmark_set.blendmark_points)} points to '{self.filepath}'")
        return {'FINISHED'}


class VIEW3D_OT_BlendMark_ExportAllPTSOperator(Operator):
    bl_idname = "view3d.blendmark_export_all_pts"
    bl_label = "Export All Landmark Sets (.pts)"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export every landmark set in the scene to <selected folder>/<set name>.pts"

    def execute(self, context):
        folder = context.scene.selected_folder
        if not folder:
            self.report({'ERROR'}, "Please select a folder to export the landmarks")
            return {'CANCELLED'}

        out_dir = folder if os.path.isdir(folder) else os.path.dirname(folder)
        exported = 0
        for obj in bpy.data.objects:
            if not is_landmark_set(obj) or len(obj.blendmark_points) == 0:
                continue
            filepath = os.path.join(out_dir, f"{obj.name}.pts")
            write_pts(filepath, landmark_set_to_dicts(obj))
            exported += 1

        if exported == 0:
            self.report({'WARNING'}, "No non-empty landmark sets found to export")
        else:
            self.report({'INFO'}, f"Exported {exported} landmark set(s) to '{out_dir}'")
        return {'FINISHED'}


classes = (
    VIEW3D_OT_BlendMark_ImportPTSOperator,
    VIEW3D_OT_BlendMark_ExportPTSOperator,
    VIEW3D_OT_BlendMark_ExportAllPTSOperator,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
