# Clean Export Scene Operator
# Writes selected armature + child meshes to a fresh temp .blend file,
# strips .001/.016-style numeric suffixes from all names,
# then opens that file in a new Blender process.

import bpy
import os
import sys
import re
import tempfile
import subprocess
from bpy.types import Operator

from ..utils.name_cleaner import strip_numeric_suffix


def _get_mesh_children_recursive(armature_obj, scene):
    """Recursively find all mesh children of armature_obj in given scene."""
    meshes = []
    def recurse(parent):
        for obj in scene.objects:
            if obj.parent == parent and obj.type == 'MESH':
                meshes.append(obj)
                recurse(obj)
    recurse(armature_obj)
    return meshes


# Bootstrap script written into the temp file's directory and passed to the
# new Blender process via --python. It runs once after the file loads and
# renames every datablock to strip trailing .NNN suffixes.
BOOTSTRAP_SCRIPT = r'''
import bpy
import re

pattern = re.compile(r"\.\d+$")

def strip_collection(collection):
    desired = {}
    for item in collection:
        new_name = pattern.sub("", item.name)
        if new_name != item.name:
            desired[item] = new_name
    for item, new_name in desired.items():
        if new_name not in collection:
            item.name = new_name

for coll in (
    bpy.data.meshes,
    bpy.data.armatures,
    bpy.data.materials,
    bpy.data.shape_keys,
    bpy.data.actions,
    bpy.data.objects,
    bpy.data.collections,
    bpy.data.scenes,
):
    try:
        strip_collection(coll)
    except Exception as e:
        print(f"[Nyarc Clean Export] Skipped {coll}: {e}")

# Strip vertex group names on every mesh object
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        for vg in obj.vertex_groups:
            new_name = pattern.sub("", vg.name)
            if new_name != vg.name and new_name not in obj.vertex_groups:
                vg.name = new_name

# Strip bone names on every armature
for arm in bpy.data.armatures:
    for bone in arm.bones:
        new_name = pattern.sub("", bone.name)
        if new_name != bone.name and new_name not in arm.bones:
            bone.name = new_name

print("[Nyarc Clean Export] Bootstrap rename complete.")
'''


class EXPORT_OT_create_clean_scene(Operator):
    """
    Write selected armature + all child meshes to a new .blend file,
    strip numeric suffixes (.001, .016, etc.) from every name,
    and open it in a separate Blender window.
    """
    bl_idname = "export.create_clean_scene"
    bl_label = "Open Clean Export in New Blender"
    bl_description = (
        "Save selected armature + child meshes to a new .blend file with "
        ".001/.016-style suffixes stripped, then launch in a new Blender window"
    )
    bl_options = {'REGISTER'}

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

        if source_armature is None or source_armature.type != 'ARMATURE':
            self.report({'ERROR'}, "No armature selected.")
            return {'CANCELLED'}

        # --- Collect datablocks to write ---
        meshes = _get_mesh_children_recursive(source_armature, context.scene)
        all_objects = [source_armature] + meshes

        datablocks = set()
        for obj in all_objects:
            datablocks.add(obj)
            if obj.data is not None:
                datablocks.add(obj.data)
            for slot in getattr(obj, 'material_slots', []):
                if slot.material is not None:
                    datablocks.add(slot.material)
            if obj.type == 'MESH' and obj.data and obj.data.shape_keys is not None:
                datablocks.add(obj.data.shape_keys)

        # --- Build temp directory + filename ---
        clean_arm_name = strip_numeric_suffix(source_armature.name)
        safe_name = re.sub(r'[^A-Za-z0-9_\-]', '_', clean_arm_name) or "Armature"

        temp_dir = tempfile.mkdtemp(prefix="nyarc_clean_export_")
        temp_blend = os.path.join(temp_dir, f"{safe_name}_Export.blend")
        bootstrap_path = os.path.join(temp_dir, "rename_bootstrap.py")

        # --- Write bootstrap script ---
        try:
            with open(bootstrap_path, 'w', encoding='utf-8') as f:
                f.write(BOOTSTRAP_SCRIPT)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write bootstrap script: {e}")
            return {'CANCELLED'}

        # --- Write selected datablocks to new .blend ---
        try:
            bpy.data.libraries.write(
                temp_blend,
                datablocks,
                fake_user=True,
                path_remap='ABSOLUTE',
            )
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write .blend file: {e}")
            return {'CANCELLED'}

        # --- Launch new Blender process ---
        blender_exe = bpy.app.binary_path
        if not blender_exe or not os.path.exists(blender_exe):
            self.report(
                {'ERROR'},
                f"Could not locate Blender executable. File saved at: {temp_blend}"
            )
            return {'CANCELLED'}

        try:
            popen_kwargs = {}
            if sys.platform.startswith('win'):
                # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                popen_kwargs['creationflags'] = 0x00000008 | 0x00000200
                popen_kwargs['close_fds'] = True
            else:
                popen_kwargs['start_new_session'] = True

            subprocess.Popen(
                [blender_exe, temp_blend, "--python", bootstrap_path],
                **popen_kwargs,
            )
        except Exception as e:
            self.report(
                {'ERROR'},
                f"Failed to launch new Blender ({e}). File saved at: {temp_blend}"
            )
            return {'CANCELLED'}

        suffix_count = sum(
            1 for obj in all_objects if strip_numeric_suffix(obj.name) != obj.name
        )
        self.report(
            {'INFO'},
            f"Launched new Blender with clean export ({len(all_objects)} objects, "
            f"{suffix_count} suffixes will be stripped). File: {temp_blend}"
        )
        return {'FINISHED'}


# List of classes to register
classes = (
    EXPORT_OT_create_clean_scene,
)
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
