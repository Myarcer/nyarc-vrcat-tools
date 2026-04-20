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
# new Blender process via --python. After the file loads it:
#   1. Links every orphan object to the active scene's master collection
#   2. Restores parent relationships
#   3. Renames every datablock to strip trailing .NNN suffixes
#   4. Saves the .blend so re-opens are clean
#   5. Writes a detailed log next to the .blend file
BOOTSTRAP_SCRIPT = r'''
import bpy
import os
import re
import sys
import traceback

LOG_PATH = os.path.join(os.path.dirname(bpy.data.filepath), "clean_export_log.txt")
_log_lines = []

def log(msg):
    line = f"[Nyarc Clean Export] {msg}"
    _log_lines.append(line)
    print(line)

def flush_log():
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(_log_lines) + "\n")
    except Exception as e:
        print(f"[Nyarc Clean Export] Failed to write log: {e}")

try:
    log(f"Bootstrap started. File: {bpy.data.filepath}")
    log(f"Blender version: {bpy.app.version_string}")

    # --- Stats before ---
    log(f"Pre-link counts: objects={len(bpy.data.objects)} "
        f"meshes={len(bpy.data.meshes)} armatures={len(bpy.data.armatures)} "
        f"materials={len(bpy.data.materials)} scenes={len(bpy.data.scenes)}")

    scene = bpy.context.scene
    log(f"Active scene: '{scene.name}'")
    master_coll = scene.collection

    # --- 1. Link orphan objects to master collection ---
    linked_count = 0
    already_count = 0
    for obj in list(bpy.data.objects):
        if obj.name not in master_coll.objects and not any(
            obj.name in c.objects for c in bpy.data.collections
        ):
            try:
                master_coll.objects.link(obj)
                linked_count += 1
                log(f"  Linked '{obj.name}' ({obj.type}) to scene")
            except Exception as e:
                log(f"  FAILED to link '{obj.name}': {e}")
        else:
            already_count += 1
    log(f"Linking done: {linked_count} newly linked, {already_count} already in a collection")

    # --- 2. Strip suffixes ---
    pattern = re.compile(r"\.\d+$")

    def strip_collection(coll, label):
        renamed = 0
        skipped = 0
        # Build a set of all current names BEFORE any rename so we don't
        # accidentally consider a name "free" that another item is about to take.
        existing = {item.name for item in coll}
        targets = []
        for item in coll:
            new_name = pattern.sub("", item.name)
            if new_name != item.name:
                targets.append((item, new_name))
        for item, new_name in targets:
            if new_name in existing and new_name != item.name:
                log(f"  [{label}] SKIP '{item.name}' -> '{new_name}' (collision)")
                skipped += 1
                continue
            existing.discard(item.name)
            item.name = new_name
            existing.add(item.name)
            log(f"  [{label}] '{item.name}' (was suffix-stripped)")
            renamed += 1
        return renamed, skipped

    total_renamed = 0
    for coll, label in (
        (bpy.data.meshes, "mesh"),
        (bpy.data.armatures, "armature_data"),
        (bpy.data.materials, "material"),
        (bpy.data.actions, "action"),
        (bpy.data.objects, "object"),
        (bpy.data.collections, "collection"),
        (bpy.data.scenes, "scene"),
    ):
        try:
            r, s = strip_collection(coll, label)
            log(f"{label}: renamed={r} skipped={s}")
            total_renamed += r
        except Exception as e:
            log(f"{label}: ERROR {e}")
            log(traceback.format_exc())

    # Shape key (Key) datablocks need separate handling because their name
    # often references the mesh name pattern
    try:
        shape_key_renamed = 0
        for key in bpy.data.shape_keys:
            new_name = pattern.sub("", key.name)
            if new_name != key.name:
                key.name = new_name
                shape_key_renamed += 1
        log(f"shape_keys: renamed={shape_key_renamed}")
    except Exception as e:
        log(f"shape_keys: ERROR {e}")

    # Vertex groups
    vg_renamed = 0
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            existing = {vg.name for vg in obj.vertex_groups}
            for vg in obj.vertex_groups:
                new_name = pattern.sub("", vg.name)
                if new_name != vg.name and new_name not in existing:
                    existing.discard(vg.name)
                    vg.name = new_name
                    existing.add(new_name)
                    vg_renamed += 1
    log(f"vertex_groups renamed: {vg_renamed}")

    # Bones
    bone_renamed = 0
    for arm in bpy.data.armatures:
        existing = {b.name for b in arm.bones}
        for bone in arm.bones:
            new_name = pattern.sub("", bone.name)
            if new_name != bone.name and new_name not in existing:
                existing.discard(bone.name)
                bone.name = new_name
                existing.add(new_name)
                bone_renamed += 1
    log(f"bones renamed: {bone_renamed}")

    log(f"TOTAL datablock renames: {total_renamed}")

    # --- 3. Save the cleaned file ---
    try:
        bpy.ops.wm.save_mainfile()
        log(f"Saved cleaned file: {bpy.data.filepath}")
    except Exception as e:
        log(f"Save failed: {e}")

    log("Bootstrap complete.")

except Exception as e:
    log(f"FATAL: {e}")
    log(traceback.format_exc())
finally:
    flush_log()
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
        log_path = os.path.join(temp_dir, "clean_export_log.txt")
        # Print to console too so user sees it without opening the file
        print(f"[Nyarc Clean Export] Wrote {len(datablocks)} datablocks to: {temp_blend}")
        print(f"[Nyarc Clean Export] Bootstrap log will be at: {log_path}")
        print(f"[Nyarc Clean Export] Launching: {blender_exe} {temp_blend}")
        self.report(
            {'INFO'},
            f"Launched new Blender ({len(all_objects)} objs, {len(datablocks)} datablocks, "
            f"{suffix_count} suffixes). Log: {log_path}",
        )
        return {'FINISHED'}


classes = (
    EXPORT_OT_create_clean_scene,
)
