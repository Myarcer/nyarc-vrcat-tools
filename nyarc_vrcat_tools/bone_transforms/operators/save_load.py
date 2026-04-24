# Save/Load Operators Bridge
# Imports save/load operators from bone_transform_saver module to avoid duplication

from ...core.registry import try_import_module

# Import save/load operators from the main saver module
saver_module, SAVER_AVAILABLE = try_import_module('nyarc_vrcat_tools.bone_transform_saver', 'bone_transform_saver')

# Import diff export operator from io module  
diff_export_module, DIFF_EXPORT_AVAILABLE = try_import_module('nyarc_vrcat_tools.bone_transforms.io.diff_export', 'bone_transforms.io.diff_export')

SAVE_LOAD_CLASSES = []

# bl_idnames the legacy bone_transform_saver module is the canonical owner of.
# Auto-discovered by walking module classes and matching bl_idname — prevents
# "forgot to add a class to the bridge" bugs (e.g. armature.compatibility_warning
# was missing, which broke MayoEdit1-3 preset loading).
#
# NOTE: pose_mode / inherit_scale / apply_rest / diff_export operators are
# intentionally EXCLUDED — modular versions of those live elsewhere in
# bone_transforms/operators/ and are registered there. The saver still defines
# legacy duplicates, but registering them here would collide on bl_idname.
_SAVER_OWNED_BL_IDNAMES = {
    "armature.save_bone_transforms",
    "armature.load_bone_transforms",
    "armature.load_bone_transforms_confirmed",
    "armature.compatibility_warning",
    "armature.delete_bone_transforms",
    "armature.list_presets",
}

if SAVER_AVAILABLE:
    import inspect as _inspect
    from bpy.types import Operator as _Operator

    discovered = []
    seen_idnames = set()
    for _name, _obj in _inspect.getmembers(saver_module, _inspect.isclass):
        if not isinstance(_obj, type) or not issubclass(_obj, _Operator):
            continue
        # Only classes actually defined in the saver module (skip re-exports)
        if getattr(_obj, "__module__", "") != saver_module.__name__:
            continue
        bl_idname = getattr(_obj, "bl_idname", None)
        if bl_idname not in _SAVER_OWNED_BL_IDNAMES:
            continue
        if bl_idname in seen_idnames:
            continue
        seen_idnames.add(bl_idname)
        discovered.append(_obj)

    SAVE_LOAD_CLASSES.extend(discovered)
    missing = _SAVER_OWNED_BL_IDNAMES - seen_idnames
    print(f"[DEBUG] save_load.py - auto-discovered {len(discovered)} operators from bone_transform_saver: {sorted(seen_idnames)}")
    if missing:
        print(f"[WARN] save_load.py - expected saver operators NOT found: {sorted(missing)}")
else:
    print("[DEBUG] save_load.py - bone_transform_saver not available")

# Add diff export operator
if DIFF_EXPORT_AVAILABLE and hasattr(diff_export_module, 'ARMATURE_OT_export_armature_diff'):
    SAVE_LOAD_CLASSES.append(diff_export_module.ARMATURE_OT_export_armature_diff)
    print(f"[DEBUG] save_load.py - added export_armature_diff operator")

print(f"[DEBUG] save_load.py - total classes: {len(SAVE_LOAD_CLASSES)}")