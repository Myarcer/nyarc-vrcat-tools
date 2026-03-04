# Shape Key Workspace UI Components
# Combines live preview/sync and quick shape key editing into one workspace panel

import bpy


def draw_workspace_ui(layout, context, props):
    """Draw the Shape Key Workspace UI section (replaces old Live Preview & Sync)"""
    layout.separator(factor=0.5)
    
    # Main collapsible workspace section
    workspace_box = layout.box()
    workspace_header = workspace_box.row()
    workspace_header.prop(props, "shapekey_workspace_expanded",
                         icon='TRIA_DOWN' if props.shapekey_workspace_expanded else 'TRIA_RIGHT',
                         icon_only=True, emboss=False)
    workspace_header.label(text="Shape Key Workspace", icon='TOOL_SETTINGS')
    
    if not props.shapekey_workspace_expanded:
        return
    
    # ─── Sub-section 1: Live Preview & Sync ───
    _draw_live_sync_section(workspace_box, context, props)
    
    # ─── Sub-section 2: Quick Shape Key Edit ───
    _draw_quick_edit_section(workspace_box, context, props)


def _draw_live_sync_section(parent_box, context, props):
    """Draw the Live Preview & Sync sub-section"""
    sync_box = parent_box.box()
    sync_header = sync_box.row()
    sync_header.prop(props, "shapekey_preview_mode",
                    icon='TRIA_DOWN' if props.shapekey_preview_mode else 'TRIA_RIGHT',
                    icon_only=True, emboss=False)
    sync_header.label(text="Live Preview & Sync", icon='LINKED')
    
    if not props.shapekey_preview_mode:
        return
    
    # Sync controls header
    sync_controls = sync_box.row()
    sync_controls.prop(props, "shapekey_sync_enabled", text="Enable Live Sync")
    sync_controls.operator("mesh.reset_shape_key_values", text="Reset All", icon='X')
    sync_controls.operator("mesh.clear_live_preview_modifiers", text="Clear Previews", icon='MODIFIER')
    
    # Get available shape keys from source
    source_obj = props.shapekey_source_object
    if not source_obj or not source_obj.data.shape_keys:
        sync_box.label(text="No shape keys found in source mesh", icon='INFO')
        return
    
    # Get target objects for validation (including viewport selection)
    target_objects = _get_target_objects(context, props, source_obj)
    
    if not target_objects:
        sync_box.label(text="No target meshes selected", icon='INFO')
        return
    
    # Show sync status
    _draw_sync_status(sync_box, props, target_objects)
    
    # Show helpful notes
    targets_without_keys = sum(1 for t in target_objects if not (t and t.data.shape_keys))
    
    if targets_without_keys > 0:
        info_row = sync_box.row()
        info_row.label(text="Transfer shape keys first to enable full live sync", icon='LIGHT')
    
    if not props.shapekey_sync_enabled:
        disabled_info_row = sync_box.row()
        disabled_info_row.label(text="Enable Live Sync to activate shape key sliders", icon='INFO')
    
    # Dynamic sliders for shape keys
    _draw_shape_key_sliders(sync_box, context, props, source_obj)


def _draw_quick_edit_section(parent_box, context, props):
    """Draw the Quick Shape Key Edit sub-section"""
    edit_box = parent_box.box()
    edit_header = edit_box.row()
    edit_header.prop(props, "shapekey_quick_edit_expanded",
                    icon='TRIA_DOWN' if props.shapekey_quick_edit_expanded else 'TRIA_RIGHT',
                    icon_only=True, emboss=False)
    edit_header.label(text="Quick Shape Key Edit", icon='EDITMODE_HLT')
    
    if not props.shapekey_quick_edit_expanded:
        return
    
    # Check if we're currently in edit/sculpt mode on a mesh
    in_edit_mode = context.mode in ('EDIT_MESH', 'SCULPT')
    
    if in_edit_mode:
        # Show exit button prominently when in edit/sculpt mode
        exit_row = edit_box.row()
        exit_row.scale_y = 1.3
        exit_row.alert = True
        exit_row.operator("mesh.exit_shapekey_edit", text="Exit Edit Mode", icon='LOOP_BACK')
        edit_box.separator(factor=0.3)
    
    # Target mesh selector
    edit_box.label(text="Target Mesh:", icon='OUTLINER_OB_MESH')
    
    # Populate from target objects if available
    target_objects = _get_all_target_objects(context, props)
    
    if target_objects and not props.shapekey_edit_target_mesh:
        # Show hint about available targets
        hint_row = edit_box.row()
        hint_row.scale_y = 0.8
        hint_row.label(text=f"{len(target_objects)} target mesh(es) available", icon='INFO')
    
    # Mesh picker dropdown
    edit_box.prop(props, "shapekey_edit_target_mesh", text="")
    
    # Quick-select buttons from target meshes (compact row)
    if target_objects:
        quick_label = edit_box.row()
        quick_label.scale_y = 0.8
        quick_label.label(text="Quick Select Target:")
        
        # Show target mesh buttons in rows of 3
        for i in range(0, len(target_objects), 3):
            row = edit_box.row(align=True)
            row.scale_y = 0.85
            for j in range(3):
                idx = i + j
                if idx < len(target_objects):
                    target = target_objects[idx]
                    is_selected = (props.shapekey_edit_target_mesh == target)
                    op = row.operator(
                        "mesh.set_quick_edit_target",
                        text=target.name,
                        depress=is_selected,
                        icon='CHECKMARK' if is_selected else 'NONE'
                    )
                    op.target_name = target.name
                else:
                    row.label(text="")  # Empty spacer
    
    target_mesh = props.shapekey_edit_target_mesh
    if not target_mesh:
        edit_box.label(text="Select a mesh to edit shape keys on", icon='INFO')
        return
    
    # Shape key selector on the target mesh
    if not target_mesh.data.shape_keys or not target_mesh.data.shape_keys.key_blocks:
        edit_box.label(text=f"'{target_mesh.name}' has no shape keys", icon='ERROR')
        return
    
    edit_box.separator(factor=0.3)
    edit_box.label(text="Shape Key:", icon='SHAPEKEY_DATA')
    
    # Use the mesh's built-in shape key selector
    edit_box.template_list(
        "MESH_UL_shape_keys", "",
        target_mesh.data.shape_keys, "key_blocks",
        target_mesh, "active_shape_key_index",
        rows=3, maxrows=5
    )
    
    # Show active shape key info
    active_idx = target_mesh.active_shape_key_index
    if active_idx < len(target_mesh.data.shape_keys.key_blocks):
        active_key = target_mesh.data.shape_keys.key_blocks[active_idx]
        if active_key.name == "Basis":
            edit_box.label(text="Select a shape key other than Basis", icon='INFO')
            return
        
        # Value slider for the active shape key
        val_row = edit_box.row()
        val_row.prop(active_key, "value", text=f"{active_key.name} Value", slider=True)
    
    edit_box.separator(factor=0.3)
    
    # Edit mode type
    mode_row = edit_box.row(align=True)
    mode_row.label(text="Mode:", icon='OBJECT_DATAMODE')
    mode_row.prop(props, "shapekey_edit_mode_type", expand=True)
    
    # Symmetry options
    sym_row = edit_box.row(align=True)
    sym_row.label(text="Auto Symmetry:", icon='MOD_MIRROR')
    sym_row.prop(props, "shapekey_edit_symmetry_x", toggle=True)
    sym_row.prop(props, "shapekey_edit_symmetry_y", toggle=True)
    sym_row.prop(props, "shapekey_edit_symmetry_z", toggle=True)
    
    edit_box.separator(factor=0.3)
    
    # Enter edit mode button
    enter_row = edit_box.row()
    enter_row.scale_y = 1.5
    
    active_idx = target_mesh.active_shape_key_index
    active_key_name = target_mesh.data.shape_keys.key_blocks[active_idx].name if active_idx < len(target_mesh.data.shape_keys.key_blocks) else "?"
    mode_label = "Edit" if props.shapekey_edit_mode_type == 'EDIT' else "Sculpt"
    
    enter_row.operator(
        "mesh.enter_shapekey_edit",
        text=f"{mode_label}: {active_key_name}",
        icon='EDITMODE_HLT' if props.shapekey_edit_mode_type == 'EDIT' else 'SCULPTMODE_HLT'
    )


# ─── Helper functions ───

def _get_target_objects(context, props, source_obj):
    """Get target objects for sync (includes viewport selection fallback)"""
    target_objects = []
    if props.shapekey_target_object:
        target_objects.append(props.shapekey_target_object)
    else:
        # Fallback: Check for viewport-selected mesh
        if context.selected_objects:
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj != source_obj:
                    target_objects.append(obj)
                    break

    target_objects.extend(props.get_target_objects_list())
    target_objects = list(set(target_objects))
    return target_objects


def _get_all_target_objects(context, props):
    """Get all available target objects from both single and multi-target mode"""
    target_objects = []
    source_obj = props.shapekey_source_object
    
    if props.shapekey_target_object:
        target_objects.append(props.shapekey_target_object)
    
    target_objects.extend(props.get_target_objects_list())
    
    # Also check viewport selection
    if context.selected_objects:
        for obj in context.selected_objects:
            if (obj.type == 'MESH' and obj != source_obj and 
                obj not in target_objects):
                target_objects.append(obj)
    
    return list(dict.fromkeys(target_objects))  # Dedupe preserving order


def _draw_sync_status(sync_box, props, target_objects):
    """Draw sync status information"""
    status_row = sync_box.row()
    
    targets_with_keys = sum(1 for t in target_objects if t and t.data.shape_keys)
    targets_without_keys = len(target_objects) - targets_with_keys
    
    if targets_without_keys > 0:
        status_row.label(
            text=f"Sync: Source + {targets_with_keys} transferred | {targets_without_keys} need transfer first",
            icon='INFO'
        )
    else:
        status_row.label(
            text=f"Syncing: Source + {len(target_objects)} target(s)",
            icon='LINKED'
        )


def _draw_shape_key_sliders(sync_box, context, props, source_obj):
    """Draw shape key preview sliders"""
    if props.shapekey_multi_mode:
        # Multi-target mode: show sliders for selected shape keys
        selected_keys = props.get_selected_shape_keys()
        
        sync_box.label(text=f"Selected keys: {len(selected_keys)}", icon='INFO')
        
        if not selected_keys:
            sync_box.label(text="Select shape keys to preview", icon='INFO')
            return
        
        for key_name in selected_keys:
            if key_name != "Basis" and key_name in source_obj.data.shape_keys.key_blocks:
                key_block = source_obj.data.shape_keys.key_blocks[key_name]
                _draw_slider_row(sync_box, props, key_name, key_block)
    else:
        # Single target mode: show slider for selected shape key
        sync_box.label(text=f"Single mode - Selected: {props.shapekey_shape_key}", icon='INFO')
        
        if props.shapekey_shape_key and props.shapekey_shape_key != "NONE":
            key_name = props.shapekey_shape_key
            if key_name in source_obj.data.shape_keys.key_blocks:
                key_block = source_obj.data.shape_keys.key_blocks[key_name]
                _draw_slider_row(sync_box, props, key_name, key_block)
        else:
            sync_box.label(text="Select a shape key to preview", icon='INFO')


def _draw_slider_row(parent, props, key_name, key_block):
    """Draw a single shape key slider row with sync status"""
    row = parent.row()
    row.label(text=key_name)
    slider_row = row.row()
    slider_row.scale_x = 2.0
    
    if props.shapekey_sync_enabled:
        slider_row.prop(key_block, "value", text="", slider=True)
        row.label(text="", icon='LINKED')
    else:
        slider_row.enabled = False
        slider_row.prop(key_block, "value", text="", slider=True)
        row.label(text="", icon='UNLINKED')


# Keep backward compatibility
def draw_live_preview_ui(layout, context, props):
    """Backward-compatible wrapper - redirects to new workspace UI"""
    draw_workspace_ui(layout, context, props)


def get_classes():
    """Get all preview UI classes for registration (none for preview_ui)"""
    return []