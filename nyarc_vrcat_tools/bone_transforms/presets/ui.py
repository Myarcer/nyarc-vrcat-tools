# Preset UI Module
# Handles the collapsible presets section UI

import bpy
import json
import os
from .manager import get_available_presets
from ..operators.loader import preset_has_precision_data
from .merge import draw_merge_ui

def has_precision_capable_presets(visible_presets):
    """Check if any of the visible presets have precision data"""
    presets_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), 'addons', 'nyarc_tools_presets')
    
    for preset_name in visible_presets:
        preset_file = os.path.join(presets_dir, f"{preset_name}.json")
        try:
            if os.path.exists(preset_file):
                with open(preset_file, 'r') as f:
                    preset_data = json.load(f)
                    if preset_has_precision_data(preset_data):
                        return True
        except:
            continue
    return False

def preset_has_precision_data_by_name(preset_name):
    """Check if a specific preset has precision data"""
    presets_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), 'addons', 'nyarc_tools_presets')
    preset_file = os.path.join(presets_dir, f"{preset_name}.json")
    
    try:
        if os.path.exists(preset_file):
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
                return preset_has_precision_data(preset_data) and preset_data.get('diff_export', False)
    except:
        pass
    return False

def _sync_preset_list(props):
    """Sync the bone_preset_list collection with presets on disk (no-op if already in sync)"""
    presets_on_disk = get_available_presets()
    current_names = [item.name for item in props.bone_preset_list]
    if current_names != presets_on_disk:
        props.bone_preset_list.clear()
        for name in presets_on_disk:
            item = props.bone_preset_list.add()
            item.name = name
        if props.bone_preset_active_index >= len(presets_on_disk):
            props.bone_preset_active_index = max(0, len(presets_on_disk) - 1)

def draw_presets_ui(layout, context, props):
    """Draw the Transform Presets UI as a collapsible section"""
    try:
        preset_box = layout.box()

        # Header with toggle
        preset_header = preset_box.row()
        preset_header.prop(props, "bone_presets_show_ui",
                          icon="TRIA_DOWN" if props.bone_presets_show_ui else "TRIA_RIGHT",
                          icon_only=True, emboss=False)
        preset_header.label(text="Transform Presets", icon='PRESET')

        if not props.bone_presets_show_ui:
            return

        # Preset name input + Save button
        preset_box.label(text="Preset Name:")
        preset_box.prop(props, "bone_preset_name", text="")
        save_row = preset_box.row()
        save_row.scale_y = 1.2
        save_row.operator("armature.save_bone_transforms", text="Save Preset", icon='EXPORT')

        preset_box.separator()

        # Sync list from disk (only updates when actual changes detected)
        _sync_preset_list(props)

        # List header with count and refresh button
        list_header = preset_box.row()
        list_header.label(text=f"Available Presets ({len(props.bone_preset_list)} total):")
        list_header.operator("armature.refresh_preset_list", text="", icon='FILE_REFRESH')

        if props.bone_preset_list:
            # Scrollable UIList
            preset_box.template_list(
                "PRESET_UL_list", "",
                props, "bone_preset_list",
                props, "bone_preset_active_index",
                rows=8,
                maxrows=12,
                type='DEFAULT'
            )

            # Action buttons for the selected preset
            active_idx = props.bone_preset_active_index
            if 0 <= active_idx < len(props.bone_preset_list):
                selected_preset = props.bone_preset_list[active_idx].name

                action_row = preset_box.row(align=True)
                action_row.scale_y = 1.2

                button_text = "Load"
                button_icon = 'IMPORT'
                if (props.apply_precision_correction and
                        preset_has_precision_data_by_name(selected_preset)):
                    button_text = "Apply Pose"
                    button_icon = 'ARMATURE_DATA'

                load_op = action_row.operator("armature.load_bone_transforms",
                                              text=button_text, icon=button_icon)
                load_op.preset_name = selected_preset

                delete_op = action_row.operator("armature.delete_bone_transforms",
                                                text="Delete", icon='X')
                delete_op.preset_name = selected_preset

                # Precision correction options (only if selected preset has precision data)
                if has_precision_capable_presets([selected_preset]):
                    preset_box.separator()
                    precision_box = preset_box.box()
                    precision_box.label(text="Precision Options:", icon='MODIFIER_DATA')
                    precision_row = precision_box.row()
                    precision_row.prop(props, "apply_precision_correction",
                                      text="Apply Precision Correction")
                    info_row = precision_box.row()
                    info_row.scale_y = 0.8
                    if props.apply_precision_correction:
                        info_row.label(text="ENABLED - Only use with SAME base armature as diff export!", icon='ERROR')
                        warning_row = precision_box.row()
                        warning_row.scale_y = 0.7
                        warning_row.label(text="WIP: Precision correction is broken - do not use!", icon='ERROR')
                    else:
                        info_row.label(text="Precision correction disabled - may have small offsets", icon='INFO')
                        warning_row = precision_box.row()
                        warning_row.scale_y = 0.7
                        warning_row.label(text="WIP: Precision correction is broken - feature under development", icon='ERROR')
        else:
            preset_box.label(text="No presets found - save one first!", icon='INFO')

        # Preset folder management
        preset_box.separator()
        folder_row = preset_box.row()
        folder_row.scale_y = 0.9
        folder_row.operator("wm.open_presets_folder", text="Open Presets Folder", icon='FILE_FOLDER')

        # Merge Presets sub-section
        preset_box.separator()
        try:
            draw_merge_ui(preset_box, context, props)
        except Exception as merge_err:
            err_box = preset_box.box()
            err_box.label(text="Merge Presets UI error", icon='ERROR')
            err_box.label(text=str(merge_err))
            print(f"[ERROR] Merge UI: {merge_err}")

        # Tips
        info_box = preset_box.box()
        info_box.scale_y = 0.8
        info_box.label(text="Tips:", icon='INFO')
        info_box.label(text="- Enter pose mode first, then save presets")
        info_box.label(text="- Name presets with model name for easy identification")
        info_box.label(text="- Presets work best on similar bone structures")

    except Exception as e:
        error_box = layout.box()
        error_box.label(text="Transform Presets (Error)", icon='ERROR')
        error_box.label(text=f"UI Error: {str(e)}", icon='INFO')
        print(f"Presets UI Error: {e}")

