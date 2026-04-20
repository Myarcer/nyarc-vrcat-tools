# Clean Export UI Panel

import bpy

from ..utils.name_cleaner import strip_numeric_suffix


def _get_mesh_children_recursive(armature_obj):
    meshes = []
    def recurse(parent):
        for obj in bpy.context.scene.objects:
            if obj.parent == parent and obj.type == 'MESH':
                meshes.append(obj)
                recurse(obj)
    recurse(armature_obj)
    return meshes


def draw_ui(layout, context):
    """Draw the Clean Export UI content (called from modules.py)."""
    props = getattr(context.scene, 'nyarc_tools_props', None)
    if not props:
        layout.label(text="Nyarc Tools properties not found!", icon='ERROR')
        return

    # Info header
    info_box = layout.box()
    info_col = info_box.column(align=True)
    info_col.scale_y = 0.85
    info_col.label(text="Opens a fresh Blender window with", icon='INFO')
    info_col.label(text="clean names. Required because object")
    info_col.label(text="names are global per .blend file.")

    layout.separator(factor=0.5)

    # Armature picker
    layout.label(text="Armature to Export:")
    layout.prop(props, "clean_export_armature", text="")

    armature = getattr(props, 'clean_export_armature', None)

    if armature:
        meshes = _get_mesh_children_recursive(armature)
        all_objs = [armature] + meshes

        preview_box = layout.box()
        preview_box.label(text="Objects to copy:", icon='OUTLINER_OB_ARMATURE')
        col = preview_box.column(align=True)

        has_any_suffix = False
        for obj in all_objs:
            clean = strip_numeric_suffix(obj.name)
            row = col.row(align=True)
            if clean != obj.name:
                has_any_suffix = True
                row.label(text=obj.name, icon='DOT')
                row.label(text=f"-> {clean}")
            else:
                row.label(text=obj.name, icon='DOT')

        if not has_any_suffix:
            preview_box.label(text="No suffixes found - names already clean.", icon='CHECKMARK')

        layout.separator(factor=0.5)

        # Main action button
        row = layout.row()
        row.scale_y = 1.8
        row.operator(
            "export.create_clean_scene",
            text="Open Clean Export in New Blender",
            icon='WINDOW'
        )

        layout.separator(factor=0.3)
        layout.label(text="From the new window: export FBX/CATS as usual.", icon='EXPORT')

    else:
        layout.separator(factor=0.5)
        layout.label(text="Select an armature above to preview.", icon='INFO')
# Clean Export UI Panel

import bpy
from bpy.types import Panel

from ..utils.name_cleaner import strip_numeric_suffix


def _get_mesh_children_recursive(armature_obj):
    """Recursively find all mesh children."""
    meshes = []
    def recurse(parent):
        for obj in bpy.context.scene.objects:
            if obj.parent == parent and obj.type == 'MESH':
                meshes.append(obj)
                recurse(obj)
    recurse(armature_obj)
    return meshes


def draw_ui(layout, context):
    """Draw the Clean Export UI content (called from modules.py)."""
    props = getattr(context.scene, 'nyarc_tools_props', None)
    if not props:
        layout.label(text="Nyarc Tools properties not found!", icon='ERROR')
        return

    # Armature picker
    layout.label(text="Armature to Export:")
    layout.prop(props, "clean_export_armature", text="")

    armature = getattr(props, 'clean_export_armature', None)

    if armature:
        # Preview: what will be copied and renamed
        meshes = _get_mesh_children_recursive(armature)
        all_objs = [armature] + meshes

        preview_box = layout.box()
        preview_box.label(text="Objects to copy:", icon='OUTLINER_OB_ARMATURE')
        col = preview_box.column(align=True)

        has_any_suffix = False
        for obj in all_objs:
            clean = strip_numeric_suffix(obj.name)
            row = col.row(align=True)
            if clean != obj.name:
                has_any_suffix = True
                row.label(text=obj.name, icon='DOT')
                row.label(text=f"→ {clean}")
            else:
                row.label(text=obj.name, icon='DOT')

        if not has_any_suffix:
            info_row = preview_box.row()
            info_row.label(text="No suffixes found — names already clean.", icon='INFO')

        layout.separator(factor=0.5)

        # Main action button
        row = layout.row()
        row.scale_y = 1.8
        row.operator(
            "export.create_clean_scene",
            text="Create Clean Export Scene",
            icon='SCENE_DATA'
        )

        layout.separator(factor=0.3)
        layout.label(text="New scene name will be:", icon='INFO')
        layout.label(text=f"  {strip_numeric_suffix(armature.name)}_Export")

    else:
        layout.separator(factor=0.5)
        layout.label(text="Select an armature above to preview.", icon='INFO')

    # Return button (always visible if there are multiple scenes)
    if len(bpy.data.scenes) > 1:
        layout.separator(factor=0.5)
        row = layout.row()
        row.operator("export.return_to_original_scene", text="Return to Original Scene", icon='LOOP_BACK')
