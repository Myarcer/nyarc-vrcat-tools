# Clean Export Scene Operator
# Creates a new scene with selected armature and its child meshes,
# stripping .001/.016-style numeric suffixes from all names.

import bpy
import re
from bpy.types import Operator
from bpy.props import BoolProperty

from ..utils.name_cleaner import strip_numeric_suffix, clean_names_mapping


def _collect_armature_objects(armature_obj):
    """
    Collect armature + all mesh children (recursive) from the current scene.
    Returns list: [armature, mesh1, mesh2, ...]
    """
    result = [armature_obj]
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.parent == armature_obj:
            result.append(obj)
    return result


def _get_mesh_children_recursive(armature_obj):
    """Recursively find all mesh children, including children of children."""
    meshes = []
    def recurse(parent):
        for obj in bpy.context.scene.objects:
            if obj.parent == parent and obj.type == 'MESH':
                meshes.append(obj)
                recurse(obj)
    recurse(armature_obj)
    return meshes


class EXPORT_OT_create_clean_scene(Operator):
    """
    Copy selected armature and all its child meshes into a new scene,
    stripping numeric suffixes (.001, .016, etc.) from all object and data names.
    """
    bl_idname = "export.create_clean_scene"
    bl_label = "Create Clean Export Scene"
    bl_description = (
        "Copy selected armature + child meshes to a new scene, "
        "removing .001/.016-style suffixes from all names"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, 'nyarc_tools_props', None)
        if props is None:
            return False
        armature = getattr(props, 'clean_export_armature', None)
        return armature is not None and armature.type == 'ARMATURE'

    def execute(self, context):
        props = context.scene.nyarc_tools_props
        source_armature = props.clean_export_armature
        original_scene = context.scene

        # --- Collect objects ---
        meshes = _get_mesh_children_recursive(source_armature)
        all_source_objects = [source_armature] + meshes

        # --- Determine clean names (handle collisions) ---
        name_map = clean_names_mapping(all_source_objects)

        # --- Create new scene ---
        clean_arm_name = strip_numeric_suffix(source_armature.name)
        new_scene_name = f"{clean_arm_name}_Export"
        bpy.ops.scene.new(type='EMPTY')
        new_scene = context.scene
        new_scene.name = new_scene_name

        # --- Copy objects into new scene ---
        copied_armature = None
        obj_map = {}  # original obj -> copied obj

        # Copy armature first
        arm_copy = source_armature.copy()
        arm_copy.data = source_armature.data.copy()
        arm_copy.name = name_map[source_armature.name]
        arm_copy.data.name = strip_numeric_suffix(source_armature.data.name)
        new_scene.collection.objects.link(arm_copy)
        copied_armature = arm_copy
        obj_map[source_armature] = arm_copy

        # Copy meshes
        for src_obj in meshes:
            obj_copy = src_obj.copy()
            obj_copy.data = src_obj.data.copy()  # full copy preserves shape keys
            obj_copy.name = name_map[src_obj.name]
            obj_copy.data.name = strip_numeric_suffix(src_obj.data.name)
            new_scene.collection.objects.link(obj_copy)
            obj_map[src_obj] = obj_copy

        # --- Restore parent relationships ---
        for src_obj, dst_obj in obj_map.items():
            if src_obj.parent and src_obj.parent in obj_map:
                dst_obj.parent = obj_map[src_obj.parent]
                dst_obj.matrix_parent_inverse = src_obj.matrix_parent_inverse.copy()

        # --- Fix armature modifiers to point to copied armature ---
        for src_obj, dst_obj in obj_map.items():
            if dst_obj.type == 'MESH':
                for mod in dst_obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object in obj_map:
                        mod.object = obj_map[mod.object]

        # --- Clean material slot names (link, not copy) ---
        # Materials are shared by reference, nothing to rename here.

        # --- Report ---
        suffix_count = sum(
            1 for orig, clean in name_map.items() if orig != clean
        )
        self.report(
            {'INFO'},
            f"Clean scene '{new_scene_name}' created: "
            f"{len(all_source_objects)} objects copied, "
            f"{suffix_count} suffix(es) stripped."
        )
        return {'FINISHED'}


class EXPORT_OT_return_to_scene(Operator):
    """Switch back to the scene stored in props (the original scene before export)."""
    bl_idname = "export.return_to_original_scene"
    bl_label = "Return to Original Scene"
    bl_description = "Switch back to the scene you were working in before creating the export scene"
    bl_options = {'REGISTER', 'UNDO'}

    scene_name: bpy.props.StringProperty(
        name="Scene Name",
        description="Name of the scene to switch back to",
        default=""
    )

    @classmethod
    def poll(cls, context):
        return len(bpy.data.scenes) > 1

    def execute(self, context):
        # Try stored name first, then fallback to any scene that is not current
        target_name = self.scene_name
        if target_name and target_name in bpy.data.scenes:
            target = bpy.data.scenes[target_name]
        else:
            # Find most recent non-current non-Export scene
            target = None
            for sc in reversed(list(bpy.data.scenes)):
                if sc != context.scene and not sc.name.endswith('_Export'):
                    target = sc
                    break
            if target is None:
                self.report({'WARNING'}, "No original scene found to return to.")
                return {'CANCELLED'}

        context.window.scene = target
        self.report({'INFO'}, f"Switched to scene '{target.name}'")
        return {'FINISHED'}


# List of classes to register
classes = (
    EXPORT_OT_create_clean_scene,
    EXPORT_OT_return_to_scene,
)
