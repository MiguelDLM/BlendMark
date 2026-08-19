#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared helpers for the BlendMark add-on: naming, target picking and the
polyline resampling used to build semilandmark curves.
"""

import bpy
from mathutils import Vector
from mathutils.geometry import intersect_line_plane
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d

RAY_LENGTH = 1.0e6


# ---------------------------------------------------------------------------
# Landmark set discovery / creation
# ---------------------------------------------------------------------------

def ensure_landmarks_collection():
    collection = bpy.data.collections.get("Landmarks")
    if not collection:
        collection = bpy.data.collections.new("Landmarks")
        bpy.context.scene.collection.children.link(collection)
    return collection


def is_landmark_set(obj):
    return bool(obj) and obj.get("blendmark_is_set", False)


def is_valid_target(obj):
    """Objects that can be digitized: meshes, and empties displaying an image."""
    if obj is None:
        return False
    if obj.type == 'MESH':
        return True
    return obj.type == 'EMPTY' and obj.empty_display_type == 'IMAGE'


def get_active_landmark_set(context):
    """Return the active object if it is a BlendMark landmark set, else None."""
    obj = context.active_object
    return obj if is_landmark_set(obj) else None


def create_landmark_set(context, name, target_object=None):
    collection = ensure_landmarks_collection()

    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'PLAIN_AXES'
    empty.empty_display_size = 0.001  # the axes themselves are not meaningful, keep them tiny
    empty["blendmark_is_set"] = True
    empty.blendmark_target = target_object
    collection.objects.link(empty)
    return empty


# ---------------------------------------------------------------------------
# Point naming
# ---------------------------------------------------------------------------

def _existing_landmark_indices(landmark_set):
    indices = []
    for p in landmark_set.blendmark_points:
        if p.kind == 'LANDMARK' and p.point_name.startswith("S."):
            try:
                indices.append(int(p.point_name.split(".")[1]))
            except (ValueError, IndexError):
                pass
    return indices


def next_landmark_name(landmark_set):
    indices = _existing_landmark_indices(landmark_set)
    return f"S.{(max(indices) + 1) if indices else 1}"


def next_curve_id(landmark_set):
    ids = [p.curve_id for p in landmark_set.blendmark_points if p.kind == 'SEMI']
    return (max(ids) + 1) if ids else 1


# ---------------------------------------------------------------------------
# Picking a point ON the target object
# ---------------------------------------------------------------------------

def _image_empty_bounds(target):
    """
    Local-space (x0, x1, y0, y1) rectangle covered by an image empty, or None
    if the empty has no image to measure.
    """
    image = target.data
    if image is None or not image.size[0] or not image.size[1]:
        return None

    width, height = image.size[0], image.size[1]
    largest = max(width, height)
    size_x = target.empty_display_size * width / largest
    size_y = target.empty_display_size * height / largest

    offset_x, offset_y = target.empty_image_offset
    x0 = offset_x * size_x
    y0 = offset_y * size_y
    return x0, x0 + size_x, y0, y0 + size_y


def pick_target_point(target, region, rv3d, coord):
    """
    Ray-cast the mouse position against `target` only and return the world-space
    hit as a Vector, or None when the ray misses it.

    Meshes are ray-cast against their evaluated geometry; image empties are
    intersected with their own plane and clipped to the image rectangle. Nothing
    else in the scene can capture the ray, so landmarks can only ever land on
    the object being digitized.
    """
    if not is_valid_target(target):
        return None

    origin = region_2d_to_origin_3d(region, rv3d, coord)
    direction = region_2d_to_vector_3d(region, rv3d, coord)
    if origin is None or direction is None:
        return None

    matrix_inv = target.matrix_world.inverted()

    if target.type == 'MESH':
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = target.evaluated_get(depsgraph)
        local_origin = matrix_inv @ origin
        local_direction = (matrix_inv.to_3x3() @ direction).normalized()

        success, location, _normal, _index = evaluated.ray_cast(local_origin, local_direction)
        if not success:
            return None
        return target.matrix_world @ location

    # Image empty: intersect the ray with the empty's local XY plane.
    plane_co = target.matrix_world.translation
    plane_no = target.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    hit = intersect_line_plane(origin, origin + direction * RAY_LENGTH, plane_co, plane_no)
    if hit is None:
        return None

    bounds = _image_empty_bounds(target)
    if bounds is not None:
        local_hit = matrix_inv @ hit
        x0, x1, y0, y1 = bounds
        if not (x0 <= local_hit.x <= x1 and y0 <= local_hit.y <= y1):
            return None

    return hit


# ---------------------------------------------------------------------------
# Edge-path ordering and resampling (semilandmark curves)
# ---------------------------------------------------------------------------

def order_selected_edge_path(bm):
    """
    Given a bmesh with a set of selected edges forming a single open path
    (or a closed loop), return an ordered list of bmesh vertices from one
    end of the path to the other. Returns None if the selection does not
    form a single unbranched path.
    """
    selected_edges = [e for e in bm.edges if e.select]
    if not selected_edges:
        return None

    adjacency = {}
    for e in selected_edges:
        v1, v2 = e.verts
        adjacency.setdefault(v1, []).append(v2)
        adjacency.setdefault(v2, []).append(v1)

    # A valid simple path/loop has every vertex with degree 1 (endpoints) or 2 (middle).
    if any(len(neighbors) > 2 for neighbors in adjacency.values()):
        return None

    endpoints = [v for v, neighbors in adjacency.items() if len(neighbors) == 1]

    if len(endpoints) not in (0, 2):
        return None

    start = endpoints[0] if endpoints else next(iter(adjacency))
    is_loop = not endpoints

    ordered = [start]
    previous = None
    current = start
    while True:
        neighbors = [n for n in adjacency[current] if n is not previous]
        if not neighbors:
            break
        nxt = neighbors[0]
        if is_loop and nxt is start:
            break
        ordered.append(nxt)
        previous, current = current, nxt

    expected_len = len(adjacency)
    if len(ordered) != expected_len:
        return None

    return ordered


def resample_polyline(points, n):
    """Resample a polyline (list of Vector) into n equally arc-length-spaced points."""
    if n < 2:
        raise ValueError("Need at least 2 semilandmarks")
    if len(points) < 2:
        raise ValueError("Path needs at least 2 vertices")

    segment_lengths = [(points[i + 1] - points[i]).length for i in range(len(points) - 1)]
    total_length = sum(segment_lengths)
    if total_length <= 0.0:
        raise ValueError("Selected path has zero length")

    step = total_length / (n - 1)
    result = [points[0].copy()]

    seg_index = 0
    seg_start_dist = 0.0
    for i in range(1, n - 1):
        target_dist = step * i
        while seg_index < len(segment_lengths) and seg_start_dist + segment_lengths[seg_index] < target_dist:
            seg_start_dist += segment_lengths[seg_index]
            seg_index += 1
        seg_len = segment_lengths[seg_index]
        t = 0.0 if seg_len == 0 else (target_dist - seg_start_dist) / seg_len
        result.append(points[seg_index].lerp(points[seg_index + 1], t))

    result.append(points[-1].copy())
    return result
