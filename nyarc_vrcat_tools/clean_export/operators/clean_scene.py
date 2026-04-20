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

for obj in bpy.data.objects:
    if obj.type == "MESH":
        for vg in obj.vertex_groups:
            new_name = pattern.sub("", vg.name)
            if new_name != vg.name and new_name not in obj.vertex_groups:
                vg.name = new_name

for arm in bpy.data.armatures:
    for bone in arm.bones:
        new_name = pattern.sub("", bone.name)
        if new_name != bone.name and new_name not in arm.bones:
            bone.name = new_name

print("[Nyarc Clean Export] Bootstrap rename complete.")
'''


class EXPORT_OT_create_clean_scene(Operator):
    """Write selected armature + meshes to a new .blend, strip suffixes, open in new Blender."""

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

        clean_arm_name = strip_numeric_suffix(source_armature.name)
        safe_name = re.sub(r'[^A-Za-z0-9_\-]', '_', clean_arm_name) or "Armature"

        temp_dir = tempfile.mkdtemp(prefix="nyarc_clean_export_")
        temp_blend = os.path.join(temp_dir, f"{safe_name}_Export.blend")
        bootstrap_path = os.path.join(temp_dir, "rename_bootstrap.py")

        try:
            with open(bootstrap_path, 'w', encoding='utf-8') as f:
                f.write(BOOTSTRAP_SCRIPT)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write bootstrap script: {e}")
            return {'CANCELLED'}

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

        blender_exe = bpy.app.binary_path
        if not blender_exe or not os.path.exists(blender_exe):
            self.report(
                {'ERROR'},
                f"Could not locate Blender executable. File saved at: {temp_blend}",
            )
            return {'CANCELLED'}

        try:
            popen_kwargs = {}
            if sys.platform.startswith('win'):
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
                f"Failed to launch new Blender ({e}). File saved at: {temp_blend}",
            )
            return {'CANCELLED'}

        suffix_count = sum(
            1 for obj in all_objects if strip_numeric_suffix(obj.name) != obj.name
        )
        self.report(
            {'INFO'},
            f"Launched new Blender with clean export ({len(all_objects)} objects, "
            f"{suffix_count} suffixes will be stripped). File: {temp_blend}",
        )
        return {'FINISHED'}


classes = (
    EXPORT_OT_create_clean_scene,
)
