bl_info = {
    "name": "BlendMark",
    "blender": (2, 80, 0),
    "category": "Mesh",
    "author": "E. Miguel Diaz de Leon-Munoz",
    "description": "An Add-on for generating and managing landmarks in Blender",
    "version": (1, 0, 0),
    "location": "View3D > Tools",
    "tracker_url": "https://github.com/MiguelDLM",
    "support": "COMMUNITY",
}

import bpy
from .panel import VIEW3D_PT_BlendMark_Panel_PT
import subprocess
import sys



from .operators import (
    VIEW3D_OT_BlendMark_BrowseFolderOperator,
    VIEW3D_OT_BlendMark_ImportDataOperator,
    VIEW3D_OT_BlendMark_NewLandmarksFileOperator,
    VIEW3D_OT_BlendMark_NewLandmarkOperator,
    VIEW3D_OT_BlendMark_ExportLandmarksOperator,
    VIEW3D_OT_BlendMark_ShowLandmarksOperator,
    VIEW3D_OT_BlendMark_StartLandmarkingOperator,
    VIEW3D_OT_BlendMark_Add3DLandmarkOperator,
    VIEW3D_OT_BlendMark_Generate3DLandmarksOperator
)    

from .panel import (
    VIEW3D_PT_BlendMark_Panel_PT,
)
#register and unregister
def register():
    bpy.utils.register_class(VIEW3D_PT_BlendMark_Panel_PT)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_BrowseFolderOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_ImportDataOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_NewLandmarksFileOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_NewLandmarkOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_ExportLandmarksOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_ShowLandmarksOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_StartLandmarkingOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_Add3DLandmarkOperator)
    bpy.utils.register_class(VIEW3D_OT_BlendMark_Generate3DLandmarksOperator)



    bpy.types.Scene.selected_folder = bpy.props.StringProperty(
        name="Selected Folder",
        description="Selected folder to store the files",
        default="",
    )

    bpy.types.Scene.new_landmark = bpy.props.StringProperty(
        name="New Landmark",
        description="Name of the new landmark",
        default="",
    )   

    bpy.types.Scene.sphere_size = bpy.props.FloatProperty(
        name="Sphere Size",
        description="Size of the spheres",
        default=0.1,
    )

    bpy.types.Scene.landmarking_mode = bpy.props.EnumProperty(
        name="Landmarking Mode",
        description="Select the landmarking mode",
        items=[
            ('2D', "2D", "2D Landmarking Mode"),
            ('3D', "3D", "3D Landmarking Mode")
        ],
        default='2D'
    )

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_BlendMark_Panel_PT)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_BrowseFolderOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_ImportDataOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_NewLandmarksFileOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_NewLandmarkOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_ExportLandmarksOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_ShowLandmarksOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_StartLandmarkingOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_Add3DLandmarkOperator)
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_Generate3DLandmarksOperator)

    del bpy.types.Scene.selected_folder
    del bpy.types.Scene.new_landmark
    del bpy.types.Scene.sphere_size

    