# Quick Shape Key Edit Operators
# Enter edit/sculpt mode on a target mesh's shape key with auto-symmetry

import bpy
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator


class MESH_OT_set_quick_edit_target(Operator):
    """Set the quick edit target mesh by name (used by quick-select buttons)"""
    bl_idname = "mesh.set_quick_edit_target"
    bl_label = "Set Quick Edit Target"
    bl_description = "Set this mesh as the target for quick shape key editing"
    bl_options = {'REGISTER', 'UNDO'}
    
    target_name: StringProperty(
        name="Target Name",
        description="Name of the target object to set",
    )
    
    def execute(self, context):
        props = context.scene.nyarc_tools_props
        target_obj = bpy.data.objects.get(self.target_name)
        
        if not target_obj or target_obj.type != 'MESH':
            self.report({'ERROR'}, f"Object '{self.target_name}' not found or not a mesh")
            return {'CANCELLED'}
        
        props.shapekey_edit_target_mesh = target_obj
        return {'FINISHED'}


class MESH_OT_enter_shapekey_edit(Operator):
    """Enter edit or sculpt mode on a target mesh with a specific shape key active"""
    bl_idname = "mesh.enter_shapekey_edit"
    bl_label = "Edit Shape Key"
    bl_description = "Select the target mesh, activate the chosen shape key, enter edit/sculpt mode, and optionally enable symmetry"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, 'nyarc_tools_props', None)
        if not props:
            return False
        target = props.shapekey_edit_target_mesh
        if not target or not target.data.shape_keys:
            return False
        return True

    def execute(self, context):
        props = context.scene.nyarc_tools_props
        target_mesh = props.shapekey_edit_target_mesh
        mode_type = props.shapekey_edit_mode_type

        if not target_mesh:
            self.report({'ERROR'}, "No target mesh selected for editing")
            return {'CANCELLED'}

        if not target_mesh.data.shape_keys or not target_mesh.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"'{target_mesh.name}' has no shape keys")
            return {'CANCELLED'}

        # Find the active shape key index from the UI selection
        # The shape key is selected via the built-in prop on the mesh's shape_keys
        active_sk_index = target_mesh.active_shape_key_index

        # Ensure we're in object mode first
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect all, then select and activate the target mesh
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        context.view_layer.objects.active = target_mesh

        # Enter the desired mode
        if mode_type == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        elif mode_type == 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')

        # Enable symmetry axes as configured
        if context.object and context.object.type == 'MESH':
            mesh = context.object.data
            mesh.use_mirror_x = props.shapekey_edit_symmetry_x
            mesh.use_mirror_y = props.shapekey_edit_symmetry_y
            mesh.use_mirror_z = props.shapekey_edit_symmetry_z

        active_key_name = target_mesh.data.shape_keys.key_blocks[active_sk_index].name if active_sk_index < len(target_mesh.data.shape_keys.key_blocks) else "unknown"

        symmetry_info = []
        if props.shapekey_edit_symmetry_x:
            symmetry_info.append("X")
        if props.shapekey_edit_symmetry_y:
            symmetry_info.append("Y")
        if props.shapekey_edit_symmetry_z:
            symmetry_info.append("Z")
        sym_text = f" | Symmetry: {', '.join(symmetry_info)}" if symmetry_info else ""

        self.report({'INFO'}, f"Editing '{active_key_name}' on '{target_mesh.name}' in {mode_type} mode{sym_text}")
        return {'FINISHED'}


class MESH_OT_exit_shapekey_edit(Operator):
    """Exit edit/sculpt mode and return to object mode"""
    bl_idname = "mesh.exit_shapekey_edit"
    bl_label = "Exit Shape Key Edit"
    bl_description = "Return to object mode from shape key editing"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode in ('EDIT_MESH', 'SCULPT')

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Exited shape key edit mode")
        return {'FINISHED'}


def get_classes():
    """Get all quick edit operator classes for registration"""
    return [
        MESH_OT_set_quick_edit_target,
        MESH_OT_enter_shapekey_edit,
        MESH_OT_exit_shapekey_edit,
    ]
