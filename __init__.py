bl_info = {
    "name": "BlendMark",
    "blender": (4, 2, 0),
    "category": "Mesh",
    "author": "E. Miguel Diaz de Leon-Munoz",
    "description": "An Add-on for generating and managing landmarks in Blender",
    "version": (2, 0, 0),
    "location": "View3D > Tools",
    "tracker_url": "https://github.com/MiguelDLM/BlendMark/issues",
    "support": "COMMUNITY",
}

import bpy

from . import core


def register():
    core.register()

    bpy.types.Scene.selected_folder = bpy.props.StringProperty(
        name="Selected Folder",
        description="Selected folder to store exported files",
        default="",
        subtype='DIR_PATH',
    )

    bpy.types.Scene.new_landmark = bpy.props.StringProperty(
        name="New Landmark",
        description="Name used for the next landmark when auto naming is off",
        default="",
    )


def unregister():
    del bpy.types.Scene.new_landmark
    del bpy.types.Scene.selected_folder

    core.unregister()


if __name__ == "__main__":
    register()
