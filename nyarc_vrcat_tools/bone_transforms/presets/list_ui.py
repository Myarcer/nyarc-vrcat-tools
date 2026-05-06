# Preset List UI Components
# Scrollable UIList for bone transform presets

import bpy
from bpy.types import UIList


class PRESET_UL_list(UIList):
    """Scrollable UIList for bone transform presets"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            preset_icon = 'MOD_DISPLACE' if item.name.endswith('_diff') else 'PRESET'
            # Name as operator button — clicking opens rename dialog
            op = row.operator("armature.rename_preset", text=item.name,
                              icon=preset_icon, emboss=False)
            op.old_name = item.name
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='PRESET')


def get_classes():
    return [PRESET_UL_list]
