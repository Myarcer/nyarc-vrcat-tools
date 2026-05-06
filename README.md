# NYARC VRCat Tools

Blender addon for VRChat avatar creation workflows.

I'm new to Github and dev in general. This project was developed with help of Claude Code.

[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.2+-orange.svg)](https://www.blender.org/)
[![Release](https://img.shields.io/github/v/release/Myarcer/nyarc-vrcat-tools)](https://github.com/Myarcer/nyarc-vrcat-tools/releases)

## Features

### Bone Transform Saver

Core module for pose mode editing and bone transform management:

- **Pose Mode**: CATS-style start/stop pose mode with automatic context switching
- **Bone Mapping**: Fuzzy name matching that works across different armature naming conventions
- **Preset Management**: Scrollable list with organized categories and easy sharing
- **Pose History**: Rollback system for non-destructive editing
- **VRChat Compatibility**: Validates bones against VRChat naming standards
- **Inherit Scale Controls**: Manage bone scale inheritance with visual feedback

### Shape Key Transfer

Shape key transfer system with real-time sync:

- **Robust Harmonic Transfer**: Harmonic inpainting that handles topology differences between meshes
  - Auto-detects disconnected mesh islands (buttons, patches) and prevents clipping artifacts
  - Visual debug mode with color-coded vertex match quality
  - Auto-tune to find the best distance threshold automatically
- **Surface Deform Transfer**: Uses Blender's Surface Deform modifier for accurate transfer
- **Live Sync**: Real-time shape key value sync between source and target
- **Batch Transfer**: Transfer to multiple targets at once
- **Mesh Prep**: Checks mesh compatibility and sets up Surface Deform automatically
- **Built-in Help**: Collapsible instruction panels inside the addon

### Mirror Flip

One-click mirror system for accessories and bones:

- **Accessory Flip**: Detects and duplicates .L/.R accessories
- **Bone Chain Mirror**: Analyzes and duplicates bone chains symmetrically
- **Auto-Detection**: Finds flip candidates automatically with safety checks
- **Combined**: Flip mesh and bones together in one step

### Clean FBX Export

FBX export with settings compatible with CATS and Avatar Toolkit:

- **CATS-Compatible Settings**: Matched to [CATS Blender Plugin](https://github.com/teamneoneko/Cats-Blender-Plugin) and [Avatar Toolkit](https://git.disroot.org/Neoneko/Avatar-Toolkit) export behavior (note: both are no longer actively developed)
- **Name Suffix Stripping**: Automatically removes .001/.016-style numeric suffixes from all names
- **Non-Destructive**: Names are renamed temporarily during export and restored after. No scene copy needed.
- **Unity/VRChat Ready**: `FBX_SCALE_ALL`, no animation bake, `armature_nodetype='NULL'`, and other Unity-optimal defaults

### Armature Diff Export *(Work in Progress)*

Calculates armature differences and exports them:

- **Difference Calculation**: Detects differences between armature states
- **Coordinate Space**: Converts coordinate spaces correctly for accurate results

## Installation

### Automatic (Recommended)

1. Download the latest release ZIP: [Releases](https://github.com/Myarcer/nyarc-vrcat-tools/releases)
2. In Blender: `Edit` → `Preferences` → `Add-ons` → `Install...`
3. Select the downloaded ZIP file
4. Enable "NYARC VRCat Tools" in the add-ons list

### Manual

1. Clone or download this repository
2. Copy the `nyarc_vrcat_tools` folder to your Blender addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\[VERSION]\scripts\addons\`
   - **macOS**: `~/Library/Application Support/Blender/[VERSION]/scripts/addons/`
   - **Linux**: `~/.config/blender/[VERSION]/scripts/addons/`

## Updating the Addon

When installing a new version, you need to reload the addon for changes to take effect.

**Method 1: Disable/Enable (Quick)**
1. Go to `Edit` → `Preferences` → `Add-ons`
2. Find "NYARC VRCat Tools"
3. Uncheck the checkbox to disable
4. Check it again to enable
5. New version is now active.

**Method 2: Reload Scripts**
- Press `F3` and search for "Reload Scripts"

**Method 3: Restart Blender**
- Save your work and restart Blender

> **Why is this needed?** Python caches modules, so reloading is required to pick up changes. Disabling and enabling the addon triggers its built-in hot-reload.

## Usage

### Quick Start

1. Select your avatar armature
2. Open `3D Viewport` → `N Panel` → `NYARC Tools`
3. Use **Bone Transform Saver** for precise armature modifications
4. Apply **Shape Key Transfer** for facial expression workflows
5. Export differences with **Armature Diff Export**

### Workflows

- **Avatar Setup**: Bone transforms → Shape key transfer → Mirror accessories
- **Precision Export**: Diff calculation → VRChat validation → Final export
- **Team Collaboration**: Preset sharing → Version tracking → Rollback support

## System Requirements

- **Blender**: 4.2 LTS or newer
- **Platform**: Windows, macOS, Linux
- **Memory**: 4GB RAM minimum, 8GB+ recommended for complex avatars

## Documentation

- **[Changelog](CHANGELOG.md)**: Version history
- **[Contributing Guidelines](CONTRIBUTING.md)**: How to contribute
- **[License](LICENSE)**: GPL-3.0

## Contributing

See [Contributing Guidelines](CONTRIBUTING.md) for details.

**Development Setup**
1. Fork this repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and test thoroughly
4. Commit with descriptive messages: `git commit -m "feat: add my feature"`
5. Push and open a Pull Request

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

Incorporates code from [Robust Weight Transfer](https://github.com/sentfromspacevr/robust-weight-transfer) (GPL-3.0) and takes inspiration from [RinvosBlendshapeTransfer](https://github.com/neongm/RinvosBlendshapeTransfer).

## Acknowledgments

- **VRChat Community** for feedback and feature requests
- **Blender Foundation** for the 3D creation platform
- **[CATS Blender Plugin](https://github.com/teamneoneko/Cats-Blender-Plugin)** for workflow inspiration and FBX export settings reference
- **[Avatar Toolkit](https://git.disroot.org/Neoneko/Avatar-Toolkit)** for the CATS-successor reference
- **[SENT Robust Weight Transfer](https://github.com/sentfromspacevr/robust-weight-transfer)** for the harmonic inpainting shape key transfer algorithm
- **[RinvosBlendshapeTransfer](https://github.com/neongm/RinvosBlendshapeTransfer)** for ideas on standard blendshape transfer

## Support

- **Issues**: [GitHub Issues](https://github.com/Myarcer/nyarc-vrcat-tools/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Myarcer/nyarc-vrcat-tools/discussions)

---

Made for the VRChat community.
