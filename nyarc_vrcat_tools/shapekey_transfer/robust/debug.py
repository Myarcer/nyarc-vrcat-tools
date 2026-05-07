"""
Debug Visualization
Create vertex colors showing match quality for parameter tuning

Dual-compat: works on Blender 4.2 LTS (vertex_colors) and 5.0+ (color_attributes)
"""

import bpy
import numpy as np


def _has_color_attributes(mesh):
    """Check if mesh uses the new color_attributes API (Blender 4.3+)"""
    return hasattr(mesh, 'color_attributes')


def _get_vcol_layer(mesh, name):
    """Get a vertex color layer by name, using whichever API is available"""
    if _has_color_attributes(mesh):
        return mesh.color_attributes.get(name)
    return mesh.vertex_colors.get(name)


def _new_vcol_layer(mesh, name):
    """Create a new vertex color layer, using whichever API is available"""
    if _has_color_attributes(mesh):
        return mesh.color_attributes.new(name=name, type='BYTE_COLOR', domain='CORNER')
    return mesh.vertex_colors.new(name=name)


def _remove_vcol_layer(mesh, layer):
    """Remove a vertex color layer, using whichever API is available"""
    if _has_color_attributes(mesh):
        mesh.color_attributes.remove(layer)
    else:
        mesh.vertex_colors.remove(layer)


def _set_active_vcol(mesh, layer):
    """Set the active vertex color layer for viewport display"""
    if _has_color_attributes(mesh):
        mesh.color_attributes.active_color = layer
    else:
        mesh.vertex_colors.active = layer


def _has_any_vcol(mesh):
    """Check if mesh has any vertex color layers"""
    if _has_color_attributes(mesh):
        return len(mesh.color_attributes) > 0
    return len(mesh.vertex_colors) > 0


def create_match_quality_debug(target_obj, matched_indices, distances, distance_threshold):
    """
    Create vertex color layer showing match quality.

    Colors:
    - Blue: Perfect matches (distance < 0.001)
    - Green: Good matches (distance < 0.005)
    - Yellow: Acceptable matches (distance < threshold)
    - Red: Unmatched vertices (will be inpainted)
    """
    mesh = target_obj.data

    # Create or get vertex color layer
    vcol_name = "RobustTransfer_MatchQuality"
    vcol_layer = _get_vcol_layer(mesh, vcol_name)
    if vcol_layer is None:
        vcol_layer = _new_vcol_layer(mesh, vcol_name)

    # Build color map
    N = len(mesh.vertices)
    color_map = np.zeros((N, 4))

    # Build lookup dictionary for matched vertices
    matched_lookup = {}
    for idx, vert_idx in enumerate(matched_indices):
        matched_lookup[vert_idx] = distances[idx]

    for i in range(N):
        if i in matched_lookup:
            dist = matched_lookup[i]

            if dist < 0.001:
                # Perfect match: Blue
                color_map[i] = [0.0, 0.5, 1.0, 1.0]
            elif dist < 0.005:
                # Good match: Green
                color_map[i] = [0.0, 1.0, 0.0, 1.0]
            else:
                # Acceptable match: Yellow
                color_map[i] = [1.0, 1.0, 0.0, 1.0]
        else:
            # Unmatched (will be inpainted): Red
            color_map[i] = [1.0, 0.0, 0.0, 1.0]

    # Apply to vertex color layer
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            loop = mesh.loops[loop_idx]
            vert_idx = loop.vertex_index
            vcol_layer.data[loop_idx].color = color_map[vert_idx]

    # Set as active for viewing
    _set_active_vcol(mesh, vcol_layer)

    # Switch viewport shading to show vertex colors properly
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Store original shading type for potential restoration
                    # Switch to solid shading with vertex color display
                    if space.shading.type == 'WIREFRAME':
                        space.shading.type = 'SOLID'
                    space.shading.color_type = 'VERTEX'

                    # Ensure overlays don't hide vertex colors
                    space.overlay.show_wireframes = False

    print(f"Created debug visualization: {vcol_name}")
    print("  Blue = perfect, Green = good, Yellow = acceptable, Red = inpainted")
    print("  Switched to SOLID shading with vertex colors visible")


def clear_match_quality_debug(target_obj):
    """
    Remove match quality debug visualization from target object.

    Called when user disables "Show Match Quality Debug" checkbox.
    """
    mesh = target_obj.data

    vcol_name = "RobustTransfer_MatchQuality"

    # Remove vertex color layer if it exists
    vcol_layer = _get_vcol_layer(mesh, vcol_name)
    if vcol_layer is not None:
        _remove_vcol_layer(mesh, vcol_layer)
        print(f"Removed debug visualization: {vcol_name}")

        # Switch viewport back to material shading if no other vertex colors exist
        if not _has_any_vcol(mesh):
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            if space.shading.color_type == 'VERTEX':
                                space.shading.color_type = 'MATERIAL'
