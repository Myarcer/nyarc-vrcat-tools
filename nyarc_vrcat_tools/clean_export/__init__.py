# Clean Export Module
# Creates a new clean scene from a selected armature, stripping .001/.016 suffixes

import bpy

from . import operators, ui, utils
from .operators.clean_scene import classes as operator_classes


MODULE_INFO = {
    'name': 'clean_export',
    'version': '1.0.0',
    'dependencies': ['core'],
    'operators': [
        'EXPORT_OT_create_clean_scene',
        'EXPORT_OT_return_to_original_scene',
    ],
    'ui_panels': [],
    'property_groups': [],
}


def register_module():
    """Register all clean_export module components."""
    print("Registering clean_export module...")
    for cls in operator_classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"[ERROR] clean_export: failed to register {cls.__name__}: {e}")
    print("[OK] Clean Export module registered")


def unregister_module():
    """Unregister all clean_export module components."""
    for cls in reversed(operator_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"[WARN] clean_export: failed to unregister {cls.__name__}: {e}")


def draw_ui(layout, context):
    """Expose draw_ui for modules.py."""
    from .ui.panels import draw_ui as _draw
    _draw(layout, context)
