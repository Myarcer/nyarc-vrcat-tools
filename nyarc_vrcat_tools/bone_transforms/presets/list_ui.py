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
            row.label(text=item.name, icon=preset_icon)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='PRESET')


def get_classes():
    return [PRESET_UL_list]
