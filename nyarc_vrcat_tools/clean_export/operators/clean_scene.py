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
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty

from ..utils.name_cleaner import strip_numeric_suffix


def _get_mesh_children_recursive(armature_obj, scene):
    """Find all mesh objects belonging to armature_obj in the scene.

    Includes:
    - meshes parented to the armature (or to any of its child meshes)
    - meshes that reference the armature via an Armature modifier but are
      not directly parented (common when built outside of 'Parent with
      Armature Deform' workflow)
    """
    meshes = []
    seen = set()

    def recurse_children(parent):
        for obj in scene.objects:
            if obj.parent == parent and obj.type == 'MESH' and obj not in seen:
                seen.add(obj)
                meshes.append(obj)
                recurse_children(obj)

    recurse_children(armature_obj)

    # Also pick up meshes linked via Armature modifier (no parent relationship)
    for obj in scene.objects:
        if obj.type != 'MESH' or obj in seen:
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature_obj:
                seen.add(obj)
                meshes.append(obj)
                break

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

        temp_dir = os.path.join(tempfile.gettempdir(), "nyarc_clean_export")
        os.makedirs(temp_dir, exist_ok=True)
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


class EXPORT_OT_export_clean_fbx(Operator, ExportHelper):
    """Export selected armature + meshes as FBX with .001 suffixes stripped in-place, then restored."""

    bl_idname = "export.nyarc_clean_fbx"
    bl_label = "Export Clean FBX"
    bl_description = (
        "Export armature + child meshes as FBX with .001/.016-style suffixes stripped. "
        "Names are renamed temporarily and restored after export — no scene copy needed."
    )
    bl_options = {'REGISTER'}

    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={'HIDDEN'})

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

        # bone_renames: [(bone, old_name), ...] — bones are per-armature, no global blockers needed.
        # Blender automatically propagates bone renames to matching vertex groups.
        bone_renames = []

        # datablock_renames: [(item, old_name, blocker_item_or_None, blocker_old_or_None), ...]
        # For global datablocks (objects, meshes, armatures, materials) where a clean-name
        # blocker might exist that needs a temporary rename to make room.
        datablock_renames = []
        processed_ids = set()

        # vis_overrides: [(obj, hide_viewport, hide_select, was_hidden_vl), ...]
        # Saved so we can restore after export even if export raises an exception.
        vis_overrides = []

        def try_rename_datablock(item, global_coll):
            if id(item) in processed_ids:
                return
            processed_ids.add(id(item))
            clean = strip_numeric_suffix(item.name)
            if clean == item.name:
                return
            blocker_item = global_coll.get(clean)
            blocker_old = None
            if blocker_item is not None and blocker_item is not item:
                tmp = f"__nyarc_tmp_{len(datablock_renames):04d}__"
                old_b = blocker_item.name
                blocker_item.name = tmp
                if blocker_item.name != tmp:
                    return  # can't move blocker, give up
                blocker_old = old_b
            old = item.name
            item.name = clean
            if item.name == clean:
                datablock_renames.append((item, old, blocker_item if blocker_old else None, blocker_old))
            else:
                # Blender re-suffixed it; undo blocker move
                item.name = old
                if blocker_item and blocker_old:
                    blocker_item.name = blocker_old

        try:
            # 1. Rename bones (Blender auto-renames matching vertex groups)
            arm_data = source_armature.data
            bone_names_in_arm = {b.name for b in arm_data.bones}
            for bone in list(arm_data.bones):
                clean = strip_numeric_suffix(bone.name)
                if clean == bone.name or clean in bone_names_in_arm:
                    continue
                old = bone.name
                bone.name = clean
                if bone.name == clean:
                    bone_renames.append((bone, old))
                    bone_names_in_arm.discard(old)
                    bone_names_in_arm.add(clean)

            # 2. Armature data block
            try_rename_datablock(arm_data, bpy.data.armatures)

            # 3. Mesh data + materials (deduplicated via processed_ids)
            for obj in meshes:
                if obj.data:
                    try_rename_datablock(obj.data, bpy.data.meshes)
                for slot in getattr(obj, 'material_slots', []):
                    if slot.material:
                        try_rename_datablock(slot.material, bpy.data.materials)

            # 4. Object names last (most visible in FBX node names)
            for obj in all_objects:
                try_rename_datablock(obj, bpy.data.objects)

            # 5. Select only export objects.
            # Temporarily clear hide_viewport / hide_select / per-vl hide so that
            # select_set(True) doesn't silently no-op for objects the user hid or
            # made non-selectable in the outliner.
            prev_active = context.view_layer.objects.active
            prev_selected = [(o, o.select_get()) for o in context.scene.objects]

            for obj in all_objects:
                old_vp = obj.hide_viewport
                old_sel = obj.hide_select
                try:
                    old_vl = obj.hide_get()
                except Exception:
                    old_vl = False
                obj.hide_viewport = False
                obj.hide_select = False
                if old_vl:
                    try:
                        obj.hide_set(False)
                    except Exception:
                        pass
                vis_overrides.append((obj, old_vp, old_sel, old_vl))

            bpy.ops.object.select_all(action='DESELECT')
            for obj in all_objects:
                try:
                    obj.select_set(True)
                except RuntimeError:
                    pass  # object excluded from view layer — skip gracefully
            context.view_layer.objects.active = source_armature

            # 6. Export FBX — settings match CATS exactly for VRChat/Unity compatibility.
            # Key differences from naive defaults:
            #   mesh_smooth_type='OFF'  → Unity computes normals itself; 'FACE'/'EDGE'
            #                             breaks blendshape normals in Unity.
            #   axis_forward='-Z' / axis_up='Y'  → Unity coordinate space.
            #   armature_nodetype='NULL'          → cleaner rig import in Unity.
            #   use_tspace=False                  → tangent-space normals off (CATS default).
            #   bake_anim_use_nla_strips/all_actions=False  → avoids animation explosion.
            bpy.ops.export_scene.fbx(
                filepath=self.filepath,
                use_selection=True,
                axis_forward='-Z',
                axis_up='Y',
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_NONE',
                object_types={'ARMATURE', 'MESH', 'EMPTY'},
                use_mesh_modifiers=True,
                mesh_smooth_type='OFF',
                use_mesh_edges=False,
                use_tspace=False,
                use_custom_props=True,
                add_leaf_bones=False,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=False,
                armature_nodetype='NULL',
                bake_anim=True,
                bake_anim_use_all_bones=True,
                bake_anim_use_nla_strips=False,
                bake_anim_use_all_actions=False,
                bake_anim_force_startend_keying=True,
                bake_anim_step=1.0,
                bake_anim_simplify_factor=1.0,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
            )

            # Restore selection
            for o, sel in prev_selected:
                try:
                    o.select_set(sel)
                except Exception:
                    pass
            try:
                context.view_layer.objects.active = prev_active
            except Exception:
                pass

            renamed_count = len(bone_renames) + len(
                [r for r in datablock_renames if not (r[1] or "").startswith("__nyarc_tmp_")]
            )
            self.report(
                {'INFO'},
                f"Clean FBX exported ({renamed_count} name(s) stripped). {self.filepath}",
            )
            return {'FINISHED'}

        finally:
            # Restore visibility/selectability overrides
            for obj, old_vp, old_sel, old_vl in vis_overrides:
                try:
                    obj.hide_viewport = old_vp
                    obj.hide_select = old_sel
                    if old_vl:
                        obj.hide_set(True)
                except Exception:
                    pass

            # Restore datablock renames in reverse: free clean name first, then restore blocker
            for item, old, blocker_item, blocker_old in reversed(datablock_renames):
                try:
                    item.name = old
                except Exception:
                    pass
                if blocker_item and blocker_old:
                    try:
                        blocker_item.name = blocker_old
                    except Exception:
                        pass
            # Restore bone renames in reverse (auto-reverts vertex groups)
            for bone, old in reversed(bone_renames):
                try:
                    bone.name = old
                except Exception:
                    pass


classes = (
    EXPORT_OT_create_clean_scene,
    EXPORT_OT_export_clean_fbx,
)
