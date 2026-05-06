# Details and Companion Tools Module - Standalone
# Information about all tools and integration with other VRChat workflow tools

import bpy
from bpy.types import Operator

class INFO_OT_open_documentation(Operator):
    """Open VRCat Avatar Tools documentation"""
    bl_idname = "info.open_documentation"
    bl_label = "Open Documentation"
    bl_description = "Open VRCat Avatar Tools documentation in web browser"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        import webbrowser
        # Open Nyarc VRCat Tools documentation/README
        webbrowser.open("https://github.com/Myarcer/nyarc-vrcat-tools#readme")
        self.report({'INFO'}, "Documentation opened in web browser")
        return {'FINISHED'}


class INFO_OT_open_support(Operator):
    """Open support and community links"""
    bl_idname = "info.open_support"
    bl_label = "Get Support"
    bl_description = "Open support channels and community resources"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        import webbrowser
        # Open GitHub issues page for support
        webbrowser.open("https://github.com/Myarcer/nyarc-vrcat-tools/issues")
        self.report({'INFO'}, "Support page opened in web browser")
        return {'FINISHED'}


class INFO_OT_open_nyarc_github(Operator):
    """Open Nyarc VRCat Tools GitHub repository"""
    bl_idname = "info.open_nyarc_github"
    bl_label = "GitHub Repository"
    bl_description = "Open the Nyarc VRCat Tools GitHub repository"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        import webbrowser
        webbrowser.open("https://github.com/Myarcer/nyarc-vrcat-tools")
        self.report({'INFO'}, "GitHub repository opened in web browser")
        return {'FINISHED'}


def draw_details_ui(layout, context, props):
    """Draw the Details/Information section about all modules and companion tools"""
    try:
        details_box = layout.box()

        # Header with toggle
        details_header = details_box.row()
        details_header.prop(
            props, "bone_details_show_ui",
            icon='TRIA_DOWN' if getattr(props, "bone_details_show_ui", False) else 'TRIA_RIGHT',
            icon_only=True
        )
        details_header.label(text="Details & Companion Tools", icon='INFO')

        if not getattr(props, "bone_details_show_ui", False):
            return

        # --- Available Modules (collapsible) ---
        modules_box = details_box.box()
        modules_header = modules_box.row()
        modules_header.prop(
            props, "details_modules_show",
            icon='TRIA_DOWN' if getattr(props, "details_modules_show", False) else 'TRIA_RIGHT',
            icon_only=True
        )
        modules_header.label(text="Available Modules", icon='OUTLINER_OB_GROUP_INSTANCE')

        if getattr(props, "details_modules_show", False):
            col = modules_box.column(align=True)
            col.scale_y = 0.85
            col.label(text="Shape Key Transfer", icon='SHAPEKEY_DATA')
            col.label(text="  Transfer shape keys across mesh topologies (Surface Deform)")
            col.separator(factor=0.3)
            col.label(text="Pose Mode Bone Editor", icon='POSE_HLT')
            col.label(text="  Save/load presets, diff export, pose history")
            col.separator(factor=0.3)
            col.label(text="Mirror Flip Tools", icon='MOD_MIRROR')
            col.label(text="  Flip bones/meshes, smart chain detection")
            col.separator(factor=0.3)
            col.label(text="Clean Export", icon='EXPORT')
            col.label(text="  One-click clean FBX/GLB export for VRChat upload")

        # --- Companion Tools (collapsible) ---
        companion_box = details_box.box()
        companion_header = companion_box.row()
        companion_header.prop(
            props, "details_companion_show",
            icon='TRIA_DOWN' if getattr(props, "details_companion_show", False) else 'TRIA_RIGHT',
            icon_only=True
        )
        companion_header.label(text="Recommended Companion Tools", icon='TOOL_SETTINGS')

        if getattr(props, "details_companion_show", False):
            col = companion_box.column(align=True)
            col.scale_y = 0.85

            # CATS - abandoned
            col.label(text="CATS Blender Plugin", icon='ARMATURE_DATA')
            warn = companion_box.box()
            warn.alert = True
            warn.label(text="Original no longer developed — consider using a community fork", icon='INFO')
            col2 = companion_box.column(align=True)
            col2.scale_y = 0.8
            col2.label(text="  Armature fix, bone merge, optimization")
            col2.label(text="  github.com/teamneoneko/Cats-Blender-Plugin")

            companion_box.separator(factor=0.5)

            # Avatar Toolkit - abandoned
            col3 = companion_box.column(align=True)
            col3.scale_y = 0.85
            col3.label(text="Avatar Toolkit", icon='ARMATURE_DATA')
            warn2 = companion_box.box()
            warn2.alert = True
            warn2.label(text="Original no longer developed — consider using a community fork", icon='INFO')
            col4 = companion_box.column(align=True)
            col4.scale_y = 0.8
            col4.label(text="  git.disroot.org/Neoneko/Avatar-Toolkit")

            companion_box.separator(factor=0.5)

            col5 = companion_box.column(align=True)
            col5.scale_y = 0.85
            col5.label(text="VRM Import/Export Tools", icon='IMPORT')
            col5.label(text="  VRM format support for all shape key / bone workflows")

        # --- Integration Workflow (collapsible) ---
        workflow_box = details_box.box()
        workflow_header = workflow_box.row()
        workflow_header.prop(
            props, "details_workflow_show",
            icon='TRIA_DOWN' if getattr(props, "details_workflow_show", False) else 'TRIA_RIGHT',
            icon_only=True
        )
        workflow_header.label(text="Integration Workflow", icon='LINKED')

        if getattr(props, "details_workflow_show", False):
            col = workflow_box.column(align=True)
            col.scale_y = 0.85
            col.label(text="1. Import + fix avatar with CATS fork or Avatar Toolkit fork")
            col.label(text="2. Shape Key Transfer for expressions/visemes")
            col.label(text="3. Pose Mode Bone Editor for transform presets")
            col.label(text="4. Clean Export for final VRChat upload")

        # Quick actions always visible when section is open
        details_box.separator(factor=0.5)
        actions_row = details_box.row()
        actions_row.scale_y = 1.1
        actions_row.operator("info.open_documentation", text="Docs", icon='HELP')
        actions_row.operator("info.open_support", text="Support", icon='COMMUNITY')
        actions_row.operator("info.open_nyarc_github", text="GitHub", icon='URL')

        # Credits (compact)
        cred_col = details_box.column(align=True)
        cred_col.scale_y = 0.75
        cred_col.label(text="Nyarc (maintainer)  |  Claude Code (AI assist)")
        cred_col.label(text="Thanks: FluffyHellWan, Aistify, Rappy")

    except Exception as e:
        error_box = layout.box()
        error_box.label(text="Details & Companion Tools (Error)", icon='ERROR')
        error_box.label(text=f"UI Error: {str(e)}", icon='INFO')
        print(f"Details UI Error: {e}")


# Operator classes for registration
classes = (
    INFO_OT_open_documentation,
    INFO_OT_open_support,
    INFO_OT_open_nyarc_github,
)


def register():
    """Register the operators"""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister the operators"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass