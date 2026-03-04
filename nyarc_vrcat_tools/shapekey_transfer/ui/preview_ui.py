# Shape Key Workspace UI Components
# Combined live preview/sync + inline shape key editing in one compact panel

import bpy


def draw_workspace_ui(layout, context, props):
    """Draw the unified Shape Key Workspace section"""
    layout.separator(factor=0.5)
    
    workspace_box = layout.box()
    workspace_header = workspace_box.row()
    workspace_header.prop(props, "shapekey_workspace_expanded",
                         icon='TRIA_DOWN' if props.shapekey_workspace_expanded else 'TRIA_RIGHT',
                         icon_only=True, emboss=False)
    workspace_header.label(text="Shape Key Workspace", icon='TOOL_SETTINGS')
    
    if not props.shapekey_workspace_expanded:
        return
    
    source_obj = props.shapekey_source_object
    if not source_obj or not source_obj.data.shape_keys:
        workspace_box.label(text="No shape keys found in source mesh", icon='INFO')
        return
    
    # ─── Exit button when in edit/sculpt mode ───
    in_edit_mode = context.mode in ('EDIT_MESH', 'SCULPT')
    if in_edit_mode:
        exit_row = workspace_box.row()
        exit_row.scale_y = 1.3
        exit_row.alert = True
        exit_row.operator("mesh.exit_shapekey_edit", text="Exit Edit Mode", icon='LOOP_BACK')
        workspace_box.separator(factor=0.3)
    
    # ─── Quick Target Select ───
    target_objects = _get_all_target_objects(context, props)
    
    if target_objects:
        if len(target_objects) > 1:
            target_label = workspace_box.row()
            target_label.scale_y = 0.8
            target_label.label(text="Target:", icon='OUTLINER_OB_MESH')
            
            for i in range(0, len(target_objects), 3):
                row = workspace_box.row(align=True)
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
                        row.label(text="")
        else:
            # Single target - auto-set and show as label
            single_target = target_objects[0]
            if not props.shapekey_edit_target_mesh:
                props.shapekey_edit_target_mesh = single_target
            target_row = workspace_box.row()
            target_row.scale_y = 0.8
            target_row.label(text=f"Target: {single_target.name}", icon='OUTLINER_OB_MESH')
    else:
        workspace_box.label(text="No target meshes selected", icon='INFO')
        return
    
    workspace_box.separator(factor=0.3)
    
    # ─── Edit Controls: Mode select ───
    edit_row = workspace_box.row(align=True)
    edit_row.prop(props, "shapekey_edit_mode_type", expand=True)
    
    # ─── Symmetry (separate row) ───
    sym_row = workspace_box.row(align=True)
    sym_row.label(text="Sym:", icon='MOD_MIRROR')
    sym_row.prop(props, "shapekey_edit_symmetry_x", text="X", toggle=True)
    sym_row.prop(props, "shapekey_edit_symmetry_y", text="Y", toggle=True)
    sym_row.prop(props, "shapekey_edit_symmetry_z", text="Z", toggle=True)
    
    # Apply symmetry live if currently in edit/sculpt mode
    if in_edit_mode and context.object and context.object.type == 'MESH':
        mesh = context.object.data
        mesh.use_mirror_x = props.shapekey_edit_symmetry_x
        mesh.use_mirror_y = props.shapekey_edit_symmetry_y
        mesh.use_mirror_z = props.shapekey_edit_symmetry_z
    
    # ─── Sync Controls ───
    sync_row = workspace_box.row(align=True)
    sync_row.prop(props, "shapekey_sync_enabled", text="Live Sync", icon='LINKED')
    sync_row.operator("mesh.reset_shape_key_values", text="Reset", icon='X')
    sync_row.operator("mesh.clear_live_preview_modifiers", text="Clear", icon='MODIFIER')
    
    workspace_box.separator(factor=0.3)
    
    # ─── Shape Key Sliders + Edit Buttons ───
    _draw_shape_key_rows(workspace_box, context, props, source_obj, target_objects)


def _draw_shape_key_rows(parent, context, props, source_obj, target_objects):
    """Draw shape key sliders with inline edit buttons"""
    # Get the shape keys based on mode
    if props.shapekey_multi_mode:
        selected_keys = props.get_selected_shape_keys()
        if not selected_keys:
            parent.label(text="Select shape keys above to preview/edit", icon='INFO')
            return
        key_names = [k for k in selected_keys if k != "Basis"]
    else:
        # Single target mode - use the selected shape key
        if props.shapekey_shape_key and props.shapekey_shape_key != "NONE":
            key_names = [props.shapekey_shape_key]
        else:
            parent.label(text="Select a shape key above", icon='INFO')
            return
    
    if not key_names:
        parent.label(text="No shape keys selected (excluding Basis)", icon='INFO')
        return
    
    # Resolve current edit target
    edit_target = props.shapekey_edit_target_mesh
    if not edit_target and target_objects:
        edit_target = target_objects[0]
    
    mode_icon = 'EDITMODE_HLT' if props.shapekey_edit_mode_type == 'EDIT' else 'SCULPTMODE_HLT'
    
    for key_name in key_names:
        if key_name not in source_obj.data.shape_keys.key_blocks:
            continue
        
        key_block = source_obj.data.shape_keys.key_blocks[key_name]
        
        row = parent.row(align=True)
        
        # Edit button (left side, compact)
        if edit_target:
            edit_sub = row.row(align=True)
            edit_sub.scale_x = 0.35
            op = edit_sub.operator(
                "mesh.enter_shapekey_edit",
                text="",
                icon=mode_icon,
            )
            op.target_name = edit_target.name
            op.shape_key_name = key_name
        
        # Slider (takes remaining space)
        slider_sub = row.row(align=True)
        if props.shapekey_sync_enabled:
            slider_sub.prop(key_block, "value", text=key_name, slider=True)
        else:
            slider_sub.enabled = False
            slider_sub.prop(key_block, "value", text=key_name, slider=True)
    
    # Show sync status summary
    if len(target_objects) > 0:
        targets_with_keys = sum(1 for t in target_objects if t and t.data.shape_keys)
        targets_without = len(target_objects) - targets_with_keys
        if targets_without > 0:
            parent.separator(factor=0.2)
            info_row = parent.row()
            info_row.scale_y = 0.7
            info_row.label(text=f"{targets_without} target(s) need shape key transfer first", icon='LIGHT')


# ─── Helper functions ───

def _get_all_target_objects(context, props):
    """Get all target objects from single/multi-target mode selection"""
    target_objects = []
    source_obj = props.shapekey_source_object
    
    if props.shapekey_multi_mode:
        # Multi-target: get from the target objects list
        target_objects.extend(props.get_target_objects_list())
    else:
        # Single-target: get from dropdown or viewport
        if props.shapekey_target_object:
            target_objects.append(props.shapekey_target_object)
        elif context.selected_objects:
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj != source_obj:
                    target_objects.append(obj)
                    break
    
    return list(dict.fromkeys(target_objects))  # Dedupe preserving order


# Keep backward compatibility
def draw_live_preview_ui(layout, context, props):
    """Backward-compatible wrapper - redirects to workspace UI"""
    draw_workspace_ui(layout, context, props)


def get_classes():
    """Get all preview UI classes for registration (none for preview_ui)"""
    return []