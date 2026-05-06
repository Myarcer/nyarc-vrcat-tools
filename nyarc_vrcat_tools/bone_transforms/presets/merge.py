# Preset Merge Module
# Combines multiple existing JSON presets into a single new preset that emulates
# the sequential workflow: load preset i -> Apply As Rest -> load preset i+1 -> ...
#
# MATH NOTE: Each preset stores ABSOLUTE pose-bone local TRS in the bone's
# CURRENT rest frame at the time of application. Apply-As-Rest does two things:
#   1) Bakes the pose into the bone's rest. For root bones the head moves by
#      the local 'location' (rotated by the current rest orientation); for child
#      bones the head also moves with the parent's baked transform.
#   2) IMPORTANT: Bone scale is absorbed into the bone's edit-mode length and
#      the pose-bone's local scale is reset to (1, 1, 1). Edit-mode bones do not
#      carry an explicit scale matrix in Blender; only head/tail/roll. This means
#      the *next* preset's 'location' is interpreted in an identity-scale local
#      frame -- it is NOT pre-multiplied by previously-applied scales.
#
# Therefore naive 4x4 matrix product (M_1 @ M_2 @ ... @ M_n) is INCORRECT: it
# bakes the previous step's scale into the next step's translation. The correct
# composition for the flattened (inherit_scale=NONE) workflow is:
#
#   R_total = R_1 * R_2 * ... * R_n           (quaternion chain)
#   T_total = sum_i (R_1 * ... * R_{i-1}) @ loc_i   (no scale terms)
#   S_total = S_1 * S_2 * ... * S_n           (component-wise product)
#
# In words: rotations and scales accumulate independently; translations sum in
# the accumulated rotation frame, with NO scale pre-multiplication.
#
# Precision/diff_export presets are still REJECTED; they depend on rest-pose
# state in ways the static JSON cannot encode.

import bpy
import copy
import os
from mathutils import Matrix, Vector, Quaternion
from bpy.types import Operator, PropertyGroup
from bpy.props import StringProperty, IntProperty, EnumProperty, CollectionProperty

from .manager import (
    get_available_presets,
    load_preset_from_file,
    save_preset_to_file,
    get_presets_directory,
)


def _read_step(bone_data):
    """Pull (loc, rot, scl) out of a preset bone entry, with safe defaults."""
    loc = Vector(bone_data.get("location", (0.0, 0.0, 0.0)))
    rot = Quaternion(bone_data.get("rotation_quaternion", (1.0, 0.0, 0.0, 0.0)))
    scl = Vector(bone_data.get("scale", (1.0, 1.0, 1.0)))
    return loc, rot, scl


def _compose_apply_rest_chain(steps):
    """Compose a list of (loc, rot, scl) steps as sequential apply-as-rest.

    Returns (loc_total, rot_total, scl_total) such that applying the resulting
    TRS once and then apply-as-rest is equivalent (in flattened/inherit_scale=NONE
    context) to applying every step in order with apply-as-rest in between.

    Key correctness rule: scale does NOT carry into subsequent translations,
    because apply-as-rest absorbs scale into bone length and resets pose scale
    to identity before the next step's location is interpreted.
    """
    rot_total = Quaternion((1.0, 0.0, 0.0, 0.0))
    loc_total = Vector((0.0, 0.0, 0.0))
    scl_total = Vector((1.0, 1.0, 1.0))
    for loc_i, rot_i, scl_i in steps:
        # Translation accumulates in the frame rotated by all preceding rotations.
        # No scale pre-multiplication -- see module docstring.
        loc_total = loc_total + (rot_total @ loc_i)
        # Rotation chain.
        rot_total = rot_total @ rot_i
        # Component-wise scale product (inherit_scale=NONE -> independent axes).
        scl_total = Vector((
            scl_total.x * scl_i.x,
            scl_total.y * scl_i.y,
            scl_total.z * scl_i.z,
        ))
    return loc_total, rot_total, scl_total


def _step_to_bone_data(loc, rot, scl, template):
    """Format a composed TRS triple back into a preset bone entry.

    Preserves any non-TRS keys (e.g. inherit_scale) from the most recent
    template seen for the bone.
    """
    out = copy.deepcopy(template) if isinstance(template, dict) else {}
    out["location"] = [loc.x, loc.y, loc.z]
    # Normalize quaternion just in case of accumulated drift.
    rot_n = rot.normalized()
    out["rotation_quaternion"] = [rot_n.w, rot_n.x, rot_n.y, rot_n.z]
    out["scale"] = [scl.x, scl.y, scl.z]
    return out


# ---------------------------------------------------------------------------
# Property group for the ordered merge list
# ---------------------------------------------------------------------------

class PresetMergeItem(PropertyGroup):
    """One entry in the ordered merge list."""
    name: StringProperty(name="Preset Name")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_merge_state(context):
    """Return (collection, active_index_prop_name, scene) or (None, None, scene)."""
    scene = context.scene
    coll = getattr(scene, "nyarc_preset_merge_list", None)
    return coll, "nyarc_preset_merge_active_index", scene


def _preset_has_precision(preset_data):
    """Return True if preset uses precision correction or diff export."""
    if not isinstance(preset_data, dict):
        return False
    if preset_data.get("diff_export"):
        return True
    bones = preset_data.get("bones") or {}
    for bone_data in bones.values():
        if isinstance(bone_data, dict) and "precision_data" in bone_data:
            return True
    return False


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class ARMATURE_OT_preset_merge_add(Operator):
    """Add a preset to the merge list (presets are composed in order, emulating sequential apply-as-rest)"""
    bl_idname = "armature.preset_merge_add"
    bl_label = "Add Preset to Merge"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    # Index into nyarc_tools_props.bone_preset_list
    selected_index: IntProperty(default=0, min=0)

    def invoke(self, context, event):
        # Sync the preset list from disk (safe here — operator invoke, not draw)
        props = getattr(context.scene, 'nyarc_tools_props', None)
        if props is not None:
            presets = get_available_presets()
            props.bone_preset_list.clear()
            for name in presets:
                item = props.bone_preset_list.add()
                item.name = name
            if self.selected_index >= len(presets):
                self.selected_index = max(0, len(presets) - 1)
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        props = getattr(context.scene, 'nyarc_tools_props', None)
        if props is None or not props.bone_preset_list:
            layout.label(text="No presets found — save one first", icon='INFO')
            return
        layout.label(text="Pick a preset to append:")
        layout.template_list(
            "PRESET_UL_list", "merge_picker",
            props, "bone_preset_list",
            self, "selected_index",
            rows=6, maxrows=10,
            type='DEFAULT',
        )
        layout.label(text="Order = sequential apply-as-rest order.", icon='INFO')

    def execute(self, context):
        coll, _, _ = _get_merge_state(context)
        if coll is None:
            self.report({'ERROR'}, "Merge list not registered")
            return {'CANCELLED'}

        props = getattr(context.scene, 'nyarc_tools_props', None)
        if props is None or not props.bone_preset_list:
            self.report({'WARNING'}, "No presets available")
            return {'CANCELLED'}
        if self.selected_index < 0 or self.selected_index >= len(props.bone_preset_list):
            self.report({'WARNING'}, "No preset selected")
            return {'CANCELLED'}

        preset_name = props.bone_preset_list[self.selected_index].name
        item = coll.add()
        item.name = preset_name

        # Re-open dialog so user can immediately add another preset
        bpy.ops.armature.preset_merge_add('INVOKE_DEFAULT')
        return {'FINISHED'}


class ARMATURE_OT_preset_merge_remove(Operator):
    """Remove the entry at the given index from the merge list"""
    bl_idname = "armature.preset_merge_remove"
    bl_label = "Remove from Merge"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    index: IntProperty(default=-1)

    def execute(self, context):
        coll, active_attr, scene = _get_merge_state(context)
        if coll is None or self.index < 0 or self.index >= len(coll):
            return {'CANCELLED'}
        coll.remove(self.index)
        # Clamp active index
        cur = getattr(scene, active_attr, 0)
        if cur >= len(coll):
            setattr(scene, active_attr, max(0, len(coll) - 1))
        return {'FINISHED'}


class ARMATURE_OT_preset_merge_move(Operator):
    """Reorder an entry in the merge list"""
    bl_idname = "armature.preset_merge_move"
    bl_label = "Move Merge Entry"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    index: IntProperty(default=-1)
    direction: EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")],
        default='UP',
    )

    def execute(self, context):
        coll, _, _ = _get_merge_state(context)
        if coll is None or self.index < 0 or self.index >= len(coll):
            return {'CANCELLED'}
        target = self.index - 1 if self.direction == 'UP' else self.index + 1
        if target < 0 or target >= len(coll):
            return {'CANCELLED'}
        coll.move(self.index, target)
        return {'FINISHED'}


class ARMATURE_OT_preset_merge_clear(Operator):
    """Clear the merge list"""
    bl_idname = "armature.preset_merge_clear"
    bl_label = "Clear Merge List"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        coll, _, _ = _get_merge_state(context)
        if coll is None:
            return {'CANCELLED'}
        coll.clear()
        return {'FINISHED'}


class ARMATURE_OT_preset_merge_execute(Operator):
    """Merge the selected presets into a new preset file. Equivalent to applying them in order."""
    bl_idname = "armature.preset_merge_execute"
    bl_label = "Create Merged Preset"
    bl_options = {'REGISTER', 'UNDO'}

    output_name: StringProperty(
        name="New Preset Name",
        description="Filename (without .json) for the merged preset",
        default="MergedPreset",
    )
    overwrite: bpy.props.BoolProperty(
        name="Overwrite if exists",
        default=False,
    )

    def invoke(self, context, event):
        coll, _, scene = _get_merge_state(context)
        if coll is None or len(coll) < 2:
            self.report({'ERROR'}, "Add at least 2 presets to the merge list first")
            return {'CANCELLED'}
        # Seed default name from scene prop if user has been typing one
        seeded = getattr(scene, "nyarc_preset_merge_output_name", "").strip()
        if seeded:
            self.output_name = seeded
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        coll, _, _ = _get_merge_state(context)
        layout.label(text=f"Merging {len(coll)} presets in this order:")
        col = layout.column(align=True)
        for i, item in enumerate(coll):
            col.label(text=f"  {i + 1}. {item.name}")
        layout.separator()
        layout.prop(self, "output_name")
        layout.prop(self, "overwrite")
        layout.label(text="Per bone: matrices compose in order (M1 · M2 · …).", icon='INFO')

    def execute(self, context):
        coll, _, _ = _get_merge_state(context)
        if coll is None or len(coll) < 2:
            self.report({'ERROR'}, "Add at least 2 presets to the merge list first")
            return {'CANCELLED'}

        out_name = (self.output_name or "").strip()
        if not out_name:
            self.report({'ERROR'}, "Output preset name is required")
            return {'CANCELLED'}
        if out_name.endswith(".json"):
            out_name = out_name[:-5]

        # Validate target file
        presets_dir = get_presets_directory()
        target_file = os.path.join(presets_dir, f"{out_name}.json")
        if os.path.exists(target_file) and not self.overwrite:
            self.report({'ERROR'}, f"'{out_name}' already exists. Tick 'Overwrite if exists' to replace.")
            return {'CANCELLED'}

        # Load and validate every source preset before writing anything.
        ordered_names = [item.name for item in coll]
        loaded = []
        for name in ordered_names:
            try:
                data = load_preset_from_file(name)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to load preset '{name}': {e}")
                return {'CANCELLED'}
            if not isinstance(data, dict) or "bones" not in data:
                self.report({'ERROR'}, f"Preset '{name}' is malformed (missing 'bones')")
                return {'CANCELLED'}
            if _preset_has_precision(data):
                self.report(
                    {'ERROR'},
                    f"Preset '{name}' uses diff_export/precision_data. "
                    "Merging precision presets is not supported because precision "
                    "corrections depend on rest-pose state between applies."
                )
                return {'CANCELLED'}
            loaded.append((name, data))

        # Sequential apply-as-rest emulation requires flattened (inherit_scale=NONE)
        # context. Reject any source that is not flattened — composing in a parent-
        # scale-inheriting context cannot be expressed as per-bone matrix products.
        non_flattened = [n for n, d in loaded if not d.get("flattened", False)]
        if non_flattened:
            self.report(
                {'ERROR'},
                "Cannot merge non-flattened presets: "
                + ", ".join(non_flattened)
                + ". Re-save them via the standard apply-as-rest workflow first."
            )
            return {'CANCELLED'}

        # Per-bone apply-as-rest composition (NOT a 4x4 matrix product).
        # Bones absent from a preset contribute the identity step for that
        # preset, which mirrors apply-as-rest leaving an untouched bone unchanged.
        bone_steps = {}        # bone_name -> list of (loc, rot, scl)
        merged_templates = {}  # last-seen aux keys (inherit_scale, etc.)
        per_source_counts = []
        for name, data in loaded:
            bones = data.get("bones") or {}
            per_source_counts.append((name, len(bones)))
            for bone_name, bone_data in bones.items():
                bone_steps.setdefault(bone_name, []).append(_read_step(bone_data))
                merged_templates[bone_name] = bone_data

        merged_bones = {}
        for bone_name, steps in bone_steps.items():
            loc, rot, scl = _compose_apply_rest_chain(steps)
            merged_bones[bone_name] = _step_to_bone_data(
                loc, rot, scl, merged_templates.get(bone_name)
            )

        merged_preset = {
            "name": out_name,
            "source_armature": "merged:" + " + ".join(ordered_names),
            "bone_count": len(merged_bones),
            "bones": merged_bones,
            "flattened": True,
            "merged_from": ordered_names,
            "description": (
                "Merged preset (sequential composition). Loading this once and "
                "applying as rest is equivalent to loading the source presets in "
                "order, applying as rest between each."
            ),
        }

        try:
            save_preset_to_file(out_name, merged_preset)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save merged preset: {e}")
            return {'CANCELLED'}

        summary = ", ".join(f"{n}({c})" for n, c in per_source_counts)
        self.report(
            {'INFO'},
            f"Saved '{out_name}.json' — {len(merged_bones)} bones merged from: {summary}"
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def draw_merge_ui(layout, context, props):
    """Draw the Merge Presets sub-section. Call from the Transform Presets panel."""
    box = layout.box()
    header = box.row()
    show_attr = "nyarc_preset_merge_show_ui"
    show = getattr(context.scene, show_attr, False)
    header.prop(
        context.scene, show_attr,
        icon="TRIA_DOWN" if show else "TRIA_RIGHT",
        icon_only=True,
    )
    header.label(text="Merge Presets", icon='AUTOMERGE_ON')

    if not show:
        return

    box.label(text="Combine multiple presets into one (apply order matters):", icon='INFO')

    coll = getattr(context.scene, "nyarc_preset_merge_list", None)
    if coll is None:
        box.label(text="Merge list not registered", icon='ERROR')
        return

    # Add / Clear row
    btn_row = box.row(align=True)
    btn_row.operator("armature.preset_merge_add", text="Add Preset", icon='ADD')
    op = btn_row.operator("armature.preset_merge_clear", text="Clear", icon='X')

    if len(coll) == 0:
        box.label(text="(empty — add presets above)", icon='INFO')
    else:
        list_box = box.box()
        list_box.label(text=f"Apply order ({len(coll)} entries):")
        for i, item in enumerate(coll):
            row = list_box.row(align=True)
            row.label(text=f"{i + 1}.", icon='PRESET')
            row.label(text=item.name)
            up = row.operator("armature.preset_merge_move", text="", icon='TRIA_UP')
            up.index = i
            up.direction = 'UP'
            dn = row.operator("armature.preset_merge_move", text="", icon='TRIA_DOWN')
            dn.index = i
            dn.direction = 'DOWN'
            rm = row.operator("armature.preset_merge_remove", text="", icon='X')
            rm.index = i

    box.separator()
    name_row = box.row(align=True)
    name_row.label(text="Output name:")
    name_row.prop(context.scene, "nyarc_preset_merge_output_name", text="")

    create_row = box.row()
    create_row.scale_y = 1.3
    create_row.enabled = len(coll) >= 2
    create_row.operator(
        "armature.preset_merge_execute",
        text="Create Merged Preset",
        icon='AUTOMERGE_ON',
    )

    info = box.box()
    info.scale_y = 0.8
    info.label(text="Emulates sequential apply-as-rest of the source presets in order.", icon='INFO')
    info.label(text="Per bone: local TRS matrices are composed (M1 · M2 · …), then re-decomposed.")
    info.label(text="Sources must be flattened. Diff/precision presets are not supported.", icon='ERROR')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

MERGE_CLASSES = (
    PresetMergeItem,
    ARMATURE_OT_preset_merge_add,
    ARMATURE_OT_preset_merge_remove,
    ARMATURE_OT_preset_merge_move,
    ARMATURE_OT_preset_merge_clear,
    ARMATURE_OT_preset_merge_execute,
)


def register_merge_props():
    """Attach the merge collection + helper props to bpy.types.Scene."""
    import bpy as _bpy
    _bpy.types.Scene.nyarc_preset_merge_list = CollectionProperty(type=PresetMergeItem)
    _bpy.types.Scene.nyarc_preset_merge_active_index = IntProperty(default=0)
    _bpy.types.Scene.nyarc_preset_merge_output_name = StringProperty(
        name="Merged Preset Name",
        description="Filename (without .json) for the merged preset",
        default="MergedPreset",
    )
    _bpy.types.Scene.nyarc_preset_merge_show_ui = bpy.props.BoolProperty(
        name="Show Merge Presets",
        default=False,
    )


def unregister_merge_props():
    import bpy as _bpy
    for attr in (
        "nyarc_preset_merge_list",
        "nyarc_preset_merge_active_index",
        "nyarc_preset_merge_output_name",
        "nyarc_preset_merge_show_ui",
    ):
        if hasattr(_bpy.types.Scene, attr):
            try:
                delattr(_bpy.types.Scene, attr)
            except Exception:
                pass
