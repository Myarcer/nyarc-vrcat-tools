"""
Geometric Correspondence (Stage 1)
Find closest surface points and validate matches using distance and normal thresholds.
Uses barycentric interpolation on source triangles for smooth displacement transfer.
"""

import numpy as np


def find_geometric_correspondence(
    source_verts, source_faces, source_normals, source_displacements,
    target_verts, target_normals,
    distance_threshold, normal_threshold
):
    """
    Find and validate geometric correspondence between source and target.

    Projects target vertices onto the source mesh surface and interpolates
    displacements using barycentric coordinates for smooth results.

    Returns:
        matched_indices: (K,) indices of matched target vertices
        matched_displacements: (K, 3) displacement vectors at matched vertices
        distances: (K,) distances for matched vertices
    """
    try:
        from mathutils.bvhtree import BVHTree
        import mathutils

        N = len(target_verts)

        # Build BVH tree from source mesh triangles for surface queries
        print("Building BVH tree for source surface...")
        verts_list = source_verts.tolist()
        faces_list = source_faces.tolist()
        bvh = BVHTree.FromPolygons(verts_list, faces_list, all_triangles=True)

        # Project each target vertex onto source surface
        print("Projecting target vertices onto source surface...")

        proj_distances = np.full(N, np.inf)
        proj_displacements = np.zeros((N, 3))
        proj_normals = np.zeros((N, 3))

        for i in range(N):
            location, normal, face_idx, dist = bvh.find_nearest(
                mathutils.Vector(target_verts[i].tolist())
            )

            if location is None or face_idx is None:
                continue

            proj_distances[i] = dist

            # Get triangle vertex indices
            face = source_faces[face_idx]
            i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])

            # Compute barycentric coordinates at the closest surface point
            closest_pt = np.array(location)
            bary = _compute_barycentric(
                closest_pt,
                source_verts[i0], source_verts[i1], source_verts[i2]
            )

            # Interpolate displacement using barycentric coordinates
            proj_displacements[i] = (
                bary[0] * source_displacements[i0] +
                bary[1] * source_displacements[i1] +
                bary[2] * source_displacements[i2]
            )

            # Interpolate vertex normal for validation
            interp_normal = (
                bary[0] * source_normals[i0] +
                bary[1] * source_normals[i1] +
                bary[2] * source_normals[i2]
            )
            norm_len = np.linalg.norm(interp_normal)
            if norm_len > 0:
                interp_normal = interp_normal / norm_len
            proj_normals[i] = interp_normal

        # Validate matches using distance and normal criteria
        print("Validating matches...")
        valid_mask = _validate_matches(
            target_normals, proj_normals,
            proj_distances,
            distance_threshold, normal_threshold
        )

        matched_indices = np.where(valid_mask)[0]
        matched_displacements = proj_displacements[valid_mask]
        matched_distances = proj_distances[valid_mask]

        return matched_indices, matched_displacements, matched_distances

    except Exception as e:
        print(f"ERROR: Correspondence failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def _compute_barycentric(point, v0, v1, v2):
    """
    Compute barycentric coordinates of a point with respect to a triangle.
    The point should be on or very near the triangle surface.

    Returns (w, u, v) where point ~= w*v0 + u*v1 + v*v2.
    """
    edge0 = v1 - v0
    edge1 = v2 - v0
    v0_to_p = point - v0

    d00 = np.dot(edge0, edge0)
    d01 = np.dot(edge0, edge1)
    d11 = np.dot(edge1, edge1)
    d20 = np.dot(v0_to_p, edge0)
    d21 = np.dot(v0_to_p, edge1)

    denom = d00 * d11 - d01 * d01

    if abs(denom) < 1e-12:
        # Degenerate triangle
        return np.array([1.0, 0.0, 0.0])

    inv_denom = 1.0 / denom
    u = (d11 * d20 - d01 * d21) * inv_denom
    v = (d00 * d21 - d01 * d20) * inv_denom
    w = 1.0 - u - v

    # Clamp to valid range (numerical precision)
    w = max(0.0, min(1.0, w))
    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))

    # Renormalize
    total = w + u + v
    if total > 0:
        w /= total
        u /= total
        v /= total

    return np.array([w, u, v])


def _validate_matches(
    target_normals, source_normals,
    distances,
    distance_threshold, normal_threshold
):
    """
    Validate matches using distance and normal alignment criteria.

    Returns:
        valid_mask: (N,) boolean array, True = valid match
    """
    # Filter out vertices that had no BVH hit
    has_match = np.isfinite(distances)

    # Distance check
    distance_valid = distances < distance_threshold

    # Normal alignment check (bidirectional for flipped normals)
    cos_angles = np.sum(target_normals * source_normals, axis=1)
    normal_valid = np.abs(cos_angles) > normal_threshold

    # Combined validation
    valid_mask = has_match & distance_valid & normal_valid

    return valid_mask
