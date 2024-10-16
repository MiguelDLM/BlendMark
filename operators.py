import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper

class VIEW3D_OT_BlendMark_BrowseFolderOperator(Operator, ImportHelper):
    bl_idname = "view3d.browse_folder"
    bl_label = "Browse Folder"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select the folder where files will be stored. If there is any text in the 'Browse Folder' window, delete the text."

    def execute(self, context):
        context.scene.selected_folder = self.filepath
        return {'FINISHED'}   
    


class VIEW3D_OT_BlendMark_ImportDataOperator(Operator, ImportHelper):
    bl_idname = "view3d.import_data"
    bl_label = "Import Data"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import data to the scene."
    
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')
    
    def execute(self, context):
        # Notify the user that the import process has started
        self.report({'INFO'}, "Importing data...")
        
        # Reorient the viewport to look from the top (Z axis)
        bpy.ops.view3d.view_axis(type='TOP')
        
        # Iterate over selected files and load each as a reference image or mesh
        for file_elem in self.files:
            filepath = self.directory + file_elem.name
            file_extension = file_elem.name.split('.')[-1].lower()
            
            if file_extension in {'jpg', 'jpeg', 'png', 'bmp', 'tiff'}:
                # Import as reference image
                bpy.ops.object.load_reference_image(filepath=filepath)
                
                # Rename the imported image object to the filename without extension
                imported_object = context.view_layer.objects.active
                if imported_object and imported_object.type == 'EMPTY' and imported_object.empty_display_type == 'IMAGE':
                    imported_object.name = file_elem.name.rsplit('.', 1)[0]
            elif file_extension in {'obj', 'stl', 'ply'}:
                # Import as mesh
                if file_extension == 'obj':
                    bpy.ops.import_scene.obj(filepath=filepath)
                elif file_extension == 'stl':
                    bpy.ops.import_mesh.stl(filepath=filepath)
                elif file_extension == 'ply':
                    bpy.ops.import_mesh.ply(filepath=filepath)
                
                # Rename the imported mesh object to the filename without extension
                imported_object = context.view_layer.objects.active
                if imported_object and imported_object.type == 'MESH':
                    imported_object.name = file_elem.name.rsplit('.', 1)[0]
        
        # Notify the user that the import process has finished
        self.report({'INFO'}, "Data import completed.")
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# Register classes
def register():
    bpy.utils.register_class(VIEW3D_OT_BlendMark_ImportDataOperator)

def unregister():
    bpy.utils.unregister_class(VIEW3D_OT_BlendMark_ImportDataOperator)

if __name__ == "__main__":
    register()
    
class VIEW3D_OT_BlendMark_NewLandmarksFileOperator(Operator):
    bl_idname = "view3d.newlandmarksfile"
    bl_label = "Start Landmarking"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Start landmarking the active object."
    
    def execute(self, context):
        # Get the active object
        active_object = context.active_object
        
        # Check if the active object is an image object
        if active_object and active_object.type == 'EMPTY' and active_object.empty_display_type == 'IMAGE':
            # Check if the "Landmarks" collection exists
            landmarks_collection = bpy.data.collections.get("Landmarks")
            if not landmarks_collection:
                # Create the "Landmarks" collection if it doesn't exist
                landmarks_collection = bpy.data.collections.new("Landmarks")
                bpy.context.scene.collection.children.link(landmarks_collection)
            
            # Remove the extension from the active object's name
            name_without_extension, _ = os.path.splitext(active_object.name)
            
            # Create a new mesh and object
            mesh = bpy.data.meshes.new(name_without_extension)
            empty_object = bpy.data.objects.new(name_without_extension, mesh)
            
            # Link the object to the "Landmarks" collection
            landmarks_collection.objects.link(empty_object)
            
            # Optionally, set the location of the empty object to match the active object
            empty_object.location = active_object.location

            # Change to edit mode
            bpy.context.view_layer.objects.active = empty_object
            bpy.ops.object.mode_set(mode='EDIT')

            # Activate the 3D cursor tool
            bpy.ops.wm.tool_set_by_id(name="builtin.cursor")
        
        return {'FINISHED'}
    
class VIEW3D_OT_BlendMark_NewLandmarkOperator(Operator):
    bl_idname = "view3d.add_landmark"
    bl_label = "Add Landmark"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Add a new landmark to the active object."
    
    def execute(self, context):
        # Get the active object
        active_object = context.active_object
        
        # Check if the active object is a mesh object
        if active_object and active_object.type == 'MESH':
            # Get the 3D cursor location
            cursor_location = context.scene.cursor.location
            
            # Switch to edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Deselect all vertices
            bpy.ops.mesh.select_all(action='DESELECT')
            
            # Switch to object mode to add the vertex
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Get the mesh data
            mesh = active_object.data
            
            # Create a new vertex at the cursor location
            mesh.vertices.add(1)
            mesh.vertices[-1].co = cursor_location
            
            # Get the name of the new landmark group
            landmark_name = context.scene.new_landmark
            
            # Create the vertex group if it doesn't exist
            if landmark_name not in active_object.vertex_groups:
                active_object.vertex_groups.new(name=landmark_name)
            
            # Get the vertex group
            vertex_group = active_object.vertex_groups[landmark_name]
            
            # Assign the new vertex to the vertex group
            vertex_group.add([len(mesh.vertices) - 1], 1.0, 'ADD')
            
            # Update the mesh
            mesh.update()
            
            # Switch back to edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            
            self.report({'INFO'}, f"New landmark '{landmark_name}' added at cursor location")
            
            # Check if the geometry node modifier already exists
            node = active_object.modifiers.get("Landmarks")
            
            if not node:
                # Create a new geometry node
                node = active_object.modifiers.new(name="Landmarks", type='NODES')
                
                # Create a new geometry node group
                node_group = bpy.data.node_groups.new(name="Landmarks", type='GeometryNodeTree')
                node.node_group = node_group
                
                # Create input and output nodes
                input_node = node_group.nodes.new('NodeGroupInput')
                output_node = node_group.nodes.new('NodeGroupOutput')
                node_group.inputs.new('NodeSocketGeometry', 'Geometry')
                node_group.outputs.new('NodeSocketGeometry', 'Geometry')
                
                # Create a "Mesh to Points" node
                mesh_to_points = node_group.nodes.new('GeometryNodeMeshToPoints')
                
                # Create an "Instances on Points" node
                instances_on_points = node_group.nodes.new('GeometryNodeInstanceOnPoints')
                
                # Create an "Ico Sphere" node
                ico_sphere = node_group.nodes.new('GeometryNodeMeshIcoSphere')
                ico_sphere.inputs['Radius'].default_value = context.scene.sphere_size
                ico_sphere.inputs['Subdivisions'].default_value = 3
                
                # Connect the nodes
                node_group.links.new(input_node.outputs['Geometry'], mesh_to_points.inputs['Mesh'])
                node_group.links.new(mesh_to_points.outputs['Points'], instances_on_points.inputs['Points'])
                node_group.links.new(ico_sphere.outputs['Mesh'], instances_on_points.inputs['Instance'])
                node_group.links.new(instances_on_points.outputs['Instances'], output_node.inputs['Geometry'])
                
                self.report({'INFO'}, "Landmarks geometry node added to the active object")
        else:
            self.report({'ERROR'}, "Active object must be a mesh object")

        return {'FINISHED'}
    
    
class VIEW3D_OT_BlendMark_ShowLandmarksOperator(Operator):
    bl_idname = "view3d.show_landmarks"
    bl_label = "Show Landmarks"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Show the landmarks on the active object."
    
    def execute(self, context):
        # Get the active object
        active_object = context.active_object
        
        # Check if the active object is a mesh object
        if active_object and active_object.type == 'MESH':
            # Check if the geometry node modifier exists
            node = active_object.modifiers.get("Landmarks")
            
            if node:
                # Toggle visibility
                node.show_viewport = not node.show_viewport
                node.show_in_editmode = not node.show_in_editmode
                self.report({'INFO'}, "Toggled visibility of landmarks on the active object")
            else:
                self.report({'ERROR'}, "No landmarks geometry node found on the active object")
        else:
            self.report({'ERROR'}, "Active object must be a mesh object")

        return {'FINISHED'}
    

class VIEW3D_OT_BlendMark_ExportLandmarksOperator(Operator):
    bl_idname = "view3d.export_landmarks"
    bl_label = "Export Landmarks"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Export the landmarks to a file."
    
    def execute(self, context):

        # Get the selected folder
        selected_folder = context.scene.selected_folder

        # Check if the selected folder is valid
        if not selected_folder:
            self.report({'ERROR'}, "Please select a folder to export the landmarks")
            return {'CANCELLED'}
        
        # Get the Landmarks collection
        landmarks_collection = bpy.data.collections.get("Landmarks")

        # Check if the Landmarks collection exists
        if not landmarks_collection:
            self.report({'ERROR'}, "No landmarks found to export")
            return {'CANCELLED'}
        
        # Create the CSV file for each object in the Landmarks collection and export the landmarks coordinates
        for obj in landmarks_collection.objects:
            if obj.type == 'MESH':
                # Create the CSV file
                csv_filename = os.path.join(selected_folder, f"{obj.name}.csv")
                with open(csv_filename, 'w') as f:
                    # Write the header
                    f.write("Landmark, X, Y, Z\n")
                    
                    # Iterate over the vertex groups
                    for vertex_group in obj.vertex_groups:
                        # Get the vertices in the vertex group
                        vertices = [v for v in obj.data.vertices if vertex_group.index in [vg.group for vg in v.groups]]
                        
                        # Write the vertex group name and coordinates to the file
                        for vertex in vertices:
                            f.write(f"{vertex_group.name}, {vertex.co.x}, {vertex.co.y}, {vertex.co.z}\n")
                
                self.report({'INFO'}, f"Landmarks exported to: {csv_filename}")

        return {'FINISHED'}
    
class VIEW3D_OT_BlendMark_StartLandmarkingOperator(Operator):
    bl_idname = "view3d.start_landmarking"
    bl_label = "Start Landmarking"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Start landmarking the active object."
    
    def execute(self, context):
        # Get the active object
        active_object = context.active_object
        
        # Check if the active object is a mesh object
        if active_object and active_object.type == 'MESH':
            # Change to edit mode
            bpy.context.view_layer.objects.active = active_object
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Activate the select vertex tool
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")

            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Active object must be a mesh object")
            return {'CANCELLED'}
        
class VIEW3D_OT_BlendMark_Generate3DLandmarksOperator(Operator):
    bl_idname = "view3d.generate_3dlandmarks"
    bl_label = "Generate 3D Landmarks"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Generate 3D landmarks on the active object."

    def execute(self, context):
        # Check if the landmarks collection exists, if not, create it
        landmarks_collection = bpy.data.collections.get("Landmarks")
        if not landmarks_collection:
            landmarks_collection = bpy.data.collections.new("Landmarks")
            bpy.context.scene.collection.children.link(landmarks_collection)
        
        # Get the active object
        active_object = context.active_object

        # Check if the active object is a mesh object
        if active_object and active_object.type == 'MESH':
            # Create a new mesh and object
            mesh = bpy.data.meshes.new(f"{active_object.name}_Landmarks")
            landmarks_object = bpy.data.objects.new(f"{active_object.name}_Landmarks", mesh)
            
            # Link the object to the "Landmarks" collection
            landmarks_collection.objects.link(landmarks_object)
            
            # Extract the vertices from the vertex groups of the active object
            all_vertices = []
            vertex_group_map = {}
            for vertex_group in active_object.vertex_groups:
                # Get the vertices in the vertex group
                vertices = [v for v in active_object.data.vertices if vertex_group.index in [vg.group for vg in v.groups]]
                all_vertices.extend(vertices)
                
                # Create a new vertex group in the new mesh object
                new_vertex_group = landmarks_object.vertex_groups.new(name=vertex_group.name)
                vertex_group_map[vertex_group.name] = (new_vertex_group, vertices)
            
            # Set the vertices of the new mesh object
            mesh.from_pydata([v.co for v in all_vertices], [], [])
            
            # Update the mesh
            mesh.update()
            
            # Assign the vertices to the corresponding vertex groups in the new mesh object
            for group_name, (new_vertex_group, vertices) in vertex_group_map.items():
                vertex_indices = [all_vertices.index(v) for v in vertices]
                new_vertex_group.add(vertex_indices, 1.0, 'ADD')
            
            # Optionally, set the location of the landmarks object to match the active object
            landmarks_object.location = active_object.location
            
            # Add a geometry node modifier to the new mesh object
            node = landmarks_object.modifiers.new(name="Landmarks", type='NODES')
            
            # Create a new geometry node group
            node_group = bpy.data.node_groups.new(name="Landmarks", type='GeometryNodeTree')
            node.node_group = node_group
            
            # Create input and output nodes
            input_node = node_group.nodes.new('NodeGroupInput')
            output_node = node_group.nodes.new('NodeGroupOutput')
            node_group.inputs.new('NodeSocketGeometry', 'Geometry')
            node_group.outputs.new('NodeSocketGeometry', 'Geometry')
            
            # Create a "Mesh to Points" node
            mesh_to_points = node_group.nodes.new('GeometryNodeMeshToPoints')
            
            # Create an "Instances on Points" node
            instances_on_points = node_group.nodes.new('GeometryNodeInstanceOnPoints')
            
            # Create an "Ico Sphere" node
            ico_sphere = node_group.nodes.new('GeometryNodeMeshIcoSphere')
            ico_sphere.inputs['Radius'].default_value = context.scene.sphere_size
            ico_sphere.inputs['Subdivisions'].default_value = 3
            
            # Connect the nodes
            node_group.links.new(input_node.outputs['Geometry'], mesh_to_points.inputs['Mesh'])
            node_group.links.new(mesh_to_points.outputs['Points'], instances_on_points.inputs['Points'])
            node_group.links.new(ico_sphere.outputs['Mesh'], instances_on_points.inputs['Instance'])
            node_group.links.new(instances_on_points.outputs['Instances'], output_node.inputs['Geometry'])
            
            self.report({'INFO'}, f"3D landmarks generated on the active object '{active_object.name}'")
        else:
            self.report({'ERROR'}, "Active object must be a mesh object")
            return {'CANCELLED'}
        
        return {'FINISHED'}
        
class VIEW3D_OT_BlendMark_Add3DLandmarkOperator(Operator):
    bl_idname = "view3d.add_3dlandmark"
    bl_label = "Add 3D Landmark"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Add a 3D landmark to the active object."

    def execute(self, context):
        # Get the active object
        active_object = context.active_object
        
        # Check if the active object is a mesh object
        if active_object and active_object.type == 'MESH':
            # Get the name of the new landmark group
            landmark_name = context.scene.new_landmark
            
            # Check if the vertex group already exists
            if landmark_name in active_object.vertex_groups:
                self.report({'ERROR'}, f"Landmark '{landmark_name}' already exists, please choose a different name or delete the existing landmark")
                return {'CANCELLED'}
            
            # Switch to edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Get the selected vertices
            selected_vertices = [v.index for v in active_object.data.vertices if v.select]
            
            # Check if exactly one vertex is selected
            if len(selected_vertices) != 1:
                self.report({'ERROR'}, "Please select exactly one vertex")
                return {'CANCELLED'}
            
            # Switch back to object mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Create the vertex group
            vertex_group = active_object.vertex_groups.new(name=landmark_name)
            
            # Assign the selected vertex to the vertex group
            vertex_group.add(selected_vertices, 1.0, 'ADD')

            # Return to edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            
            self.report({'INFO'}, f"New 3D landmark '{landmark_name}' added to the selected vertex")
        else:
            self.report({'ERROR'}, "Active object must be a mesh object")

        return {'FINISHED'}