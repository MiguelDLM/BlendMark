import bpy
class VIEW3D_PT_BlendMark_Panel_PT(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_BlendMark_Panel_PT"
    bl_label = "BlendMark"
    bl_category = "BlendMark"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'HEADER_LAYOUT_EXPAND'}

    def draw(self, context):
        layout = self.layout

        # Data Storage Location
        box = layout.box()
        box.label(text="Storage results", icon='FILE_FOLDER')

        row = box.row()
        row.operator("view3d.browse_folder", text="Browse Folder", icon='FILE_FOLDER')
        row.prop(context.scene, "selected_folder", text="")

        # Add a separator
        layout.separator()

        box = layout.box()
        box.label(text="Import data", icon='IMAGE_DATA')

        row = box.row()
        row.operator("view3d.import_data", text="Import Data", icon='IMPORT')

        # Add a separator
        layout.separator()

        # Landmarking Mode Selection
        box = layout.box()
        box.label(text="Landmarking Mode", icon='CURVE_DATA')

        row = box.row()
        row.prop(context.scene, "landmarking_mode", expand=True)

        # Display the appropriate section based on the user's selection
        if context.scene.landmarking_mode == '2D':
            self.draw_2d_landmarking(context, layout)
        elif context.scene.landmarking_mode == '3D':
            self.draw_3d_landmarking(context, layout)

        # Visual elements
        layout.separator()
        box = layout.box()
        box.label(text="Visual elements", icon='MATERIAL')

        row = box.row()
        row.prop(context.scene, "sphere_size", text="Sphere Size")
        row.operator("view3d.show_landmarks", text="Show Landmarks", icon='RESTRICT_VIEW_OFF')

        layout.separator()
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        # Export landmarks
        row = box.row()
        row.operator("view3d.export_landmarks", text="Export Landmarks", icon='EXPORT')

    def draw_2d_landmarking(self, context, layout):
        box = layout.box()
        box.label(text="2D Landmarking", icon='CURVE_DATA')

        row = box.row()
        row.operator("view3d.newlandmarksfile", text="New LandmarkFile", icon='CURVE_PATH')

        row = box.row()
        row.prop(context.scene, "new_landmark", text="New Landmark", icon='GREASEPENCIL')
        row.operator("view3d.add_landmark", text="Add Landmark", icon='PLUS')

    def draw_3d_landmarking(self, context, layout):
        box = layout.box()
        box.label(text="3D Landmarking", icon='CURVE_DATA')

        row = box.row()
        row.operator("view3d.start_landmarking", text="Start Landmarking", icon='CURVE_PATH')

        row = box.row()
        row.prop(context.scene, "new_landmark", text="New Landmark", icon='GREASEPENCIL')
        row.operator("view3d.add_3dlandmark", text="Add 3D Landmark", icon='PLUS')
        row.operator("view3d.generate_3dlandmarks", text="Generate 3D Landmarks", icon='MESH_ICOSPHERE')
