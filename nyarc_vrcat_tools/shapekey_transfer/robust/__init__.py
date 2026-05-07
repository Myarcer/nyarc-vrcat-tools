# Robust Shape Key Transfer Module
# Harmonic inpainting-based transfer for smooth boundaries and islands
#
# Based on: "Robust Skin Weights Transfer via Weight Inpainting"
# SIGGRAPH ASIA 2023 - Abdrashitov, Raichstat, Monsen, Hill
#
# Adapted for shape key transfer (3D displacement vectors instead of scalar weights)

import sys
import os
import importlib

# Add local deps folder to Python path for bundled dependencies
deps_path = os.path.join(os.path.dirname(__file__), 'deps')
if os.path.exists(deps_path) and deps_path not in sys.path:
    sys.path.insert(0, deps_path)

# Check for required dependencies
DEPENDENCIES = ["scipy", "robust_laplacian"]
missing_deps = []

# Check robust_laplacian version BEFORE importing — v1.1.0 segfaults Blender
_rl_dist_info = os.path.join(deps_path, 'robust_laplacian-1.1.0.dist-info')
if os.path.exists(_rl_dist_info):
    print("[NYARC] WARNING: robust_laplacian 1.1.0 detected (crashes Blender). "
          "Delete the deps/ folder and reinstall via the addon button.")
    missing_deps.append("robust_laplacian")
else:
    for module_name in DEPENDENCIES:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing_deps.append(module_name)

# Only import functionality if dependencies are available
if not missing_deps:
    from .core import transfer_shape_key_robust
    from .correspondence import find_geometric_correspondence
    from .inpainting import inpaint_displacements
    from .debug import create_match_quality_debug

    __all__ = [
        'transfer_shape_key_robust',
        'find_geometric_correspondence',
        'inpaint_displacements',
        'create_match_quality_debug',
    ]

    DEPENDENCIES_AVAILABLE = True
else:
    # Dependencies missing - will show installer UI
    DEPENDENCIES_AVAILABLE = False
    __all__ = []

def get_missing_dependencies():
    """Return list of missing dependency names for UI display"""
    return missing_deps.copy()

def deps_installed_on_disk():
    """Check if deps folder exists with expected packages (installed but not yet loaded)"""
    if not os.path.exists(deps_path):
        return False
    # Check for scipy and robust_laplacian directories
    has_scipy = os.path.isdir(os.path.join(deps_path, 'scipy'))
    has_rl = (os.path.isdir(os.path.join(deps_path, 'robust_laplacian')) or
              os.path.isfile(os.path.join(deps_path, 'robust_laplacian_bindings.pyd')))
    return has_scipy and has_rl
