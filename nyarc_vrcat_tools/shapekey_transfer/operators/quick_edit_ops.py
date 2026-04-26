# Quick Shape Key Edit Operators
# Enter edit/sculpt mode on a target mesh's shape key with auto-symmetry

import bpy
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator


def _reset_all_shapekeys(props):
    """Reset all non-Basis shapekeys to 0.0 on source and all target objects."""
    objects = []
    if props.shapekey_source_object:
        objects.append(props.shapekey_source_object)
    if props.shapekey_target_object:
        objects.append(props.shapekey_target_object)
    objects.extend(props.get_target_objects_list())
    for obj in objects:
        if obj and obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                if kb.name != "Basis":
                    kb.value = 0.0


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

    # Optional inline parameters - when provided, override props
    target_name: StringProperty(
        name="Target Name",
        description="Target mesh name (optional, overrides selected target)",
        default="",
    )
    
    shape_key_name: StringProperty(
        name="Shape Key Name",
        description="Shape key to activate (optional, overrides active index)",
        default="",
    )

    @classmethod
    def poll(cls, context):
        # Always allow - target_name/shape_key_name are passed as operator params
        # and validated in execute()
        return getattr(context.scene, 'nyarc_tools_props', None) is not None

    def execute(self, context):
        props = context.scene.nyarc_tools_props
        mode_type = props.shapekey_edit_mode_type

        # Resolve target mesh: inline param > props
        if self.target_name:
            target_mesh = bpy.data.objects.get(self.target_name)
            if not target_mesh or target_mesh.type != 'MESH':
                self.report({'ERROR'}, f"Object '{self.target_name}' not found or not a mesh")
                return {'CANCELLED'}
        else:
            target_mesh = props.shapekey_edit_target_mesh

        if not target_mesh:
            self.report({'ERROR'}, "No target mesh selected for editing")
            return {'CANCELLED'}

        if not target_mesh.data.shape_keys or not target_mesh.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"'{target_mesh.name}' has no shape keys")
            return {'CANCELLED'}

        # Resolve shape key: inline param > active index
        if self.shape_key_name:
            key_blocks = target_mesh.data.shape_keys.key_blocks
            sk_index = key_blocks.find(self.shape_key_name)
            if sk_index < 0:
                self.report({'ERROR'}, f"Shape key '{self.shape_key_name}' not found on '{target_mesh.name}'")
                return {'CANCELLED'}
            active_sk_index = sk_index
        else:
            active_sk_index = target_mesh.active_shape_key_index

        active_key = target_mesh.data.shape_keys.key_blocks[active_sk_index] if active_sk_index < len(target_mesh.data.shape_keys.key_blocks) else None
        if not active_key:
            self.report({'ERROR'}, "Invalid shape key index")
            return {'CANCELLED'}
        active_key_name = active_key.name

        # Toggle: pressing the same edit button again exits edit mode
        if (props.shapekey_edit_prev_key_name == active_key_name and
                props.shapekey_edit_prev_target_name == target_mesh.name):
            _reset_all_shapekeys(props)
            props.shapekey_edit_prev_key_name = ""
            props.shapekey_edit_prev_target_name = ""
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, f"Exited edit for '{active_key_name}'")
            return {'FINISHED'}

        # Reset ALL shapekeys to 0 on source + all targets before activating the new one
        _reset_all_shapekeys(props)

        # Track which key is now being edited
        props.shapekey_edit_prev_value = 0.0
        props.shapekey_edit_prev_key_name = active_key_name
        props.shapekey_edit_prev_target_name = target_mesh.name

        # Set active key to 1.0 on the edit target and on source (so slider reflects it)
        active_key.value = 1.0
        target_mesh.active_shape_key_index = active_sk_index
        source_obj = props.shapekey_source_object
        if source_obj and source_obj.data.shape_keys:
            source_active_key = source_obj.data.shape_keys.key_blocks.get(active_key_name)
            if source_active_key:
                source_active_key.value = 1.0

        # Ensure we're in object mode first
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect all, then select and activate the target mesh
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        context.view_layer.objects.active = target_mesh
        
        # Force view layer update so context is valid for mode_set
        context.view_layer.update()

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
        props = context.scene.nyarc_tools_props
        
        # Reset ALL shapekeys to 0 on source + all targets
        _reset_all_shapekeys(props)

        # Clear tracking
        props.shapekey_edit_prev_key_name = ""
        props.shapekey_edit_prev_target_name = ""
        
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
