"""
Mesh Data Extraction and Application
Handles Blender-specific mesh operations
"""

import bpy
import numpy as np


def extract_shape_key_displacements(obj, shape_key_name):
    """
    Extract displacement vectors from shape key, in WORLD space.

    Shape-key coords are stored in the object's LOCAL space. Correspondence and
    inpainting operate in WORLD space (see get_mesh_data_world_space), so the
    displacement deltas must be rotated/scaled by the object's world matrix.
    Otherwise an object whose world transform differs from identity (e.g. a
    garment parented to an armature scaled 0.01) produces shape keys that are
    off by that scale -- collapsing to a near-zero "NONE" result on the target.

    Returns:
        displacements: (N, 3) array of WORLD-space delta vectors
        basis_coords: (N, 3) array of LOCAL-space basis shape coordinates
    """
    mesh = obj.data

    if not mesh.shape_keys:
        print(f"ERROR: Object {obj.name} has no shape keys")
        return None, None

    if shape_key_name not in mesh.shape_keys.key_blocks:
        print(f"ERROR: Shape key '{shape_key_name}' not found")
        return None, None

    # Get basis and target shape
    basis = mesh.shape_keys.key_blocks[0]  # Basis shape
    shape_key = mesh.shape_keys.key_blocks[shape_key_name]

    # Extract coordinates (local space)
    basis_verts = np.array([v.co for v in basis.data])
    shape_verts = np.array([v.co for v in shape_key.data])

    # Compute local displacements, then rotate/scale into world space.
    # Use the 3x3 part of matrix_world (no translation for direction vectors).
    local_displacements = shape_verts - basis_verts
    world_3x3 = np.array(obj.matrix_world.to_3x3())
    displacements = local_displacements @ world_3x3.T

    return displacements, basis_verts


def get_mesh_data_world_space(obj, apply_modifiers=True):
    """
    Extract mesh geometry in world space.

    Args:
        obj: Blender object
        apply_modifiers: If True, evaluate the object with all modifiers applied.
                         If False, use the base mesh data directly (no subdivision etc.).
                         Use False for source objects in robust transfer so that
                         face vertex indices match the shape-key displacement array.

    Returns:
        vertices: (N, 3) vertex coordinates
        faces: (F, 3) triangle indices
        normals: (N, 3) vertex normals
    """
    if apply_modifiers:
        # Get evaluated mesh (with modifiers applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
    else:
        # Use base mesh data — no modifiers, vertex indices match shape-key arrays
        mesh = obj.data.copy()

    try:
        # Ensure triangulation
        mesh.calc_loop_triangles()

        # Extract vertices in world space
        world_matrix = obj.matrix_world
        vertices = np.array([world_matrix @ v.co for v in mesh.vertices])

        # Extract triangulated faces
        triangles = np.array([
            [v for v in tri.vertices]
            for tri in mesh.loop_triangles
        ])

        # Calculate vertex normals in world space
        # Handle Blender 4.1+ API change (calc_normals_split removed)
        normals = np.zeros((len(mesh.vertices), 3))
        
        if bpy.app.version >= (4, 1, 0):
            # Blender 4.1+: Use corner_normals (automatically updated)
            corner_normals = mesh.corner_normals
            
            # Average corner normals for each vertex
            for tri in mesh.loop_triangles:
                for loop_idx in tri.loops:
                    vert_idx = mesh.loops[loop_idx].vertex_index
                    loop_normal = corner_normals[loop_idx].vector
                    world_normal = world_matrix.to_3x3() @ loop_normal
                    normals[vert_idx] += world_normal
        else:
            # Blender 3.x - 4.0: Use calc_normals_split
            mesh.calc_normals_split()
            
            # Average loop normals for each vertex
            for tri in mesh.loop_triangles:
                for loop_idx in tri.loops:
                    vert_idx = mesh.loops[loop_idx].vertex_index
                    loop_normal = mesh.loops[loop_idx].normal
                    world_normal = world_matrix.to_3x3() @ loop_normal
                    normals[vert_idx] += world_normal

        # Normalize
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normals = normals / norms

        return vertices, triangles, normals

    finally:
        # Clean up mesh data
        if apply_modifiers:
            obj_eval.to_mesh_clear()
        else:
            bpy.data.meshes.remove(mesh)


def apply_shape_key_to_mesh(obj, shape_key_name, displacements):
    """
    Create or update shape key on target mesh with computed displacements.

    Args:
        obj: Blender object
        shape_key_name: Name for new/updated shape key
        displacements: (N, 3) WORLD-space displacement vectors
    """
    mesh = obj.data

    # Ensure basis shape key exists
    if not mesh.shape_keys:
        obj.shape_key_add(name="Basis", from_mix=False)

    # Create or get shape key
    if shape_key_name in mesh.shape_keys.key_blocks:
        shape_key = mesh.shape_keys.key_blocks[shape_key_name]
    else:
        shape_key = obj.shape_key_add(name=shape_key_name, from_mix=False)

    # Displacements arrive in WORLD space; shape-key coords live in LOCAL space.
    # Convert world -> local with the inverse of the 3x3 world matrix so the
    # delta magnitude is correct regardless of the object's world transform.
    # (Without this, a target with non-identity world scale gets near-zero
    #  "NONE" shape keys -- e.g. a garment under an armature scaled 0.01.)
    world_3x3_inv = np.array(obj.matrix_world.to_3x3().inverted())
    local_displacements = displacements @ world_3x3_inv.T

    basis_verts = np.array([v.co for v in mesh.vertices])
    new_verts = basis_verts + local_displacements

    for i, coord in enumerate(new_verts):
        shape_key.data[i].co = coord

    print(f"Applied shape key '{shape_key_name}' to {obj.name}")
