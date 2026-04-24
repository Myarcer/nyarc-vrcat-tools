# Preset Merge Module
# Combines multiple existing JSON presets into a single new preset.
#
# MATH NOTE: Presets store ABSOLUTE pose-bone transforms (location, rotation,
# scale). The loader directly assigns these values without composition.
# Therefore manually loading preset A then preset B is equivalent, per bone,
# to: bones unique to A keep A's values, bones in B (whether or not in A) take
# B's values. The merge below is exactly that ordered last-write-wins dict
# merge, so a merged preset reproduces sequential application bit-for-bit on
# the standard pose path.
#
# Precision/diff_export presets are intentionally REJECTED. Their precision
# corrections are computed against the rest pose at export time, and sequential
# application mutates the rest pose between applies (via apply-as-rest). A
# single merged file cannot replicate that pipeline, so merging would silently
# diverge from manual sequential application.

import bpy
import copy
import os
from bpy.types import Operator, PropertyGroup
from bpy.props import StringProperty, IntProperty, EnumProperty, CollectionProperty

from .manager import (
    get_available_presets,
    load_preset_from_file,
    save_preset_to_file,
    get_presets_directory,
)


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


def _available_presets_enum(self, context):
    """EnumProperty items callback for the add-preset dropdown."""
    items = []
    for name in get_available_presets():
        items.append((name, name, ""))
    if not items:
        items.append(("", "(no presets)", ""))
    return items


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class ARMATURE_OT_preset_merge_add(Operator):
    """Add a preset to the merge list (later entries overwrite earlier ones per bone)"""
    bl_idname = "armature.preset_merge_add"
    bl_label = "Add Preset to Merge"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    preset_name: EnumProperty(
        name="Preset",
        description="Preset to add to the merge list",
        items=_available_presets_enum,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Pick a preset to append:")
        layout.prop(self, "preset_name", text="")
        layout.label(text="Order = apply order. Later entries win per bone.", icon='INFO')

    def execute(self, context):
        coll, _, _ = _get_merge_state(context)
        if coll is None:
            self.report({'ERROR'}, "Merge list not registered")
            return {'CANCELLED'}
        if not self.preset_name:
            self.report({'WARNING'}, "No preset selected")
            return {'CANCELLED'}
        item = coll.add()
        item.name = self.preset_name
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
        layout.label(text="Later entries overwrite earlier ones per bone.", icon='INFO')

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

        # Ordered last-write-wins merge of bone dicts.
        merged_bones = {}
        per_source_counts = []
        for name, data in loaded:
            bones = data.get("bones") or {}
            per_source_counts.append((name, len(bones)))
            for bone_name, bone_data in bones.items():
                merged_bones[bone_name] = copy.deepcopy(bone_data)

        # Determine flattened flag: only safe if ALL sources are flattened.
        all_flattened = all(d.get("flattened", False) for _, d in loaded)

        merged_preset = {
            "name": out_name,
            "source_armature": "merged:" + " + ".join(ordered_names),
            "bone_count": len(merged_bones),
            "bones": merged_bones,
            "flattened": all_flattened,
            "merged_from": ordered_names,
            "description": (
                "Merged preset. Equivalent to applying source presets in listed "
                "order: later entries overwrite earlier ones per bone."
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
        icon_only=True, emboss=False,
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
    info.label(text="Mathematically equivalent to applying source presets in order.", icon='INFO')
    info.label(text="Per bone: later entry wins. Bones unique to earlier entries are kept.")
    info.label(text="Diff/precision presets cannot be merged (rest-pose state-dependent).", icon='ERROR')


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
