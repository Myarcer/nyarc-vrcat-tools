# Name cleaning utilities for Clean Export module
# Strips .001, .016 style numeric suffixes added by Blender for duplicate objects

import re


def strip_numeric_suffix(name: str) -> str:
    """
    Strip Blender's auto-added numeric suffix from an object/mesh/bone name.
    e.g. 'Body.001' -> 'Body', 'Armature.016' -> 'Armature'
    Only strips a trailing dot followed by digits, e.g. '.001' or '.016'.
    """
    return re.sub(r'\.\d+$', '', name)


def clean_names_mapping(objects) -> dict:
    """
    Build a mapping of {original_name: clean_name} for a list of Blender objects.
    Handles collisions: if two objects would map to the same clean name,
    the first one gets the clean name and subsequent ones keep their original name.

    Args:
        objects: iterable of bpy.types.Object

    Returns:
        dict mapping original_name -> clean_name (may equal original_name if no suffix)
    """
    mapping = {}
    used_names = set()

    for obj in objects:
        original = obj.name
        desired = strip_numeric_suffix(original)

        if desired not in used_names:
            mapping[original] = desired
            used_names.add(desired)
        else:
            # Collision: keep original name to avoid duplication
            mapping[original] = original
            used_names.add(original)

    return mapping
