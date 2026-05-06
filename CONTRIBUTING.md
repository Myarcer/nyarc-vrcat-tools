# Contributing to NYARC VRCat Tools

Thank you for your interest in contributing! This document outlines how to contribute to the NYARC VRCat Tools project.

## Quick Start

1. **Fork** this repository
2. **Clone** your fork locally
3. **Create** a feature branch: `git checkout -b feature/my-feature`
4. **Make** your changes and test thoroughly
5. **Commit** with descriptive messages: `git commit -m "feat: add my feature"`
6. **Push** to your branch: `git push origin feature/my-feature`
7. **Open** a Pull Request

## Development Guidelines

### Code Style
- Follow **PEP 8** for Python code formatting
- Use **4 spaces** for indentation (no tabs)
- Keep line length under **120 characters**
- Use **descriptive variable names**
- Add **docstrings** for all public functions and classes

### Commit Message Format
We use [Conventional Commits](https://www.conventionalcommits.org/) for automated changelog generation:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic changes)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(bone-transforms): add fuzzy bone name matching
fix(shape-keys): resolve transfer validation error
docs: update installation guide
refactor(presets): improve preset loading performance
```

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

## Architecture Overview

### Project Structure
```
nyarc_vrcat_tools/
├── __init__.py                 # Main addon registration & main panel
├── modules.py                  # Module coordinator and registry
├── bone_transform_saver.py     # Legacy bone transform entry point
├── core/                       # Shared utilities and registry
│   ├── registry.py            # Module registration system
│   └── data_structures.py     # Shared data structures
├── bone_transforms/            # Modular bone transform system
│   ├── operators/             # Bone transformation operations
│   ├── presets/               # Advanced preset management
│   ├── precision/             # Precision correction engine
│   ├── pose_history/          # Pose history and rollback
│   ├── compatibility/         # VRChat compatibility checking
│   ├── diff_export/           # Armature difference export
│   ├── ui/                    # User interface panels
│   ├── utils/                 # Utility functions
│   └── io/                    # Import/export functionality
├── shapekey_transfer/         # Shape key transfer system
│   ├── operators/             # Transfer operations
│   ├── robust/                # Robust harmonic transfer
│   ├── sync/                  # Live synchronization
│   ├── ui/                    # User interface components
│   └── utils/                 # Helper utilities
├── clean_export/              # Clean FBX export module
│   ├── operators/             # Export operations
│   ├── ui/                    # UI panels
│   └── utils/                 # Export helpers
├── mirror_flip/               # Mirror flip utilities
│   ├── operators/             # Flip operations
│   ├── ui/                    # UI panels
│   └── utils/                 # Detection and validation
└── details_companion_tools.py # Details & Companion Tools panel
```

### Key Principles
- **Modular Design**: Each feature is self-contained
- **Graceful Fallbacks**: Missing modules don't break the addon
- **Dynamic Registration**: Components are loaded automatically
- **Clean Separation**: UI, logic, and data are clearly separated

## Testing

### Manual Testing
1. Install the addon in Blender 4.2+
2. Test all features with various avatar types
3. Verify VRChat compatibility
4. Check error handling with invalid inputs

### Test Scenarios
- **Basic Operations**: All core features work as expected
- **Edge Cases**: Invalid inputs handled gracefully
- **Performance**: Large avatars processed efficiently
- **Compatibility**: Works across Blender versions

## Documentation

### Code Documentation
- Add **docstrings** to all public functions
- Include **parameter descriptions** and **return values**
- Document **exceptions** that may be raised
- Explain **complex algorithms** with comments

### User Documentation
- Update relevant documentation files
- Add **screenshots** for UI changes
- Update **changelog** entries
- Provide **usage examples**

## Bug Reports

### Before Reporting
1. Check existing issues for duplicates
2. Test with the latest version
3. Verify the bug in a clean Blender installation

### Bug Report Template
```markdown
**Blender Version:** 4.x.x
**Addon Version:** x.x.x
**Operating System:** Windows/macOS/Linux

**Description:**
Clear description of the issue

**Steps to Reproduce:**
1. Step one
2. Step two
3. Step three

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Additional Context:**
Screenshots, logs, etc.
```

## Feature Requests

### Feature Request Template
```markdown
**Feature Description:**
Clear description of the proposed feature

**Use Case:**
Why is this feature needed?

**Proposed Solution:**
How should it work?

**Alternatives Considered:**
Other approaches considered

**Additional Context:**
Mockups, examples, etc.
```

## Pull Request Process

### Before Submitting
1. **Test thoroughly** with various avatar types
2. **Update documentation** if needed
3. **Follow coding standards** and conventions
4. **Write descriptive commit messages**

### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Manual testing completed
- [ ] Edge cases considered
- [ ] Performance impact assessed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Changelog updated
```

### Review Process
1. **Automated checks** must pass
2. **Code review** by maintainers
3. **Testing** on different systems
4. **Merge** after approval

## Areas for Contribution

### High Priority
- **Performance optimization** for large avatars
- **New VRChat features** support
- **Cross-platform testing** and fixes
- **User interface** improvements

### Documentation
- **Tutorial videos** and guides
- **API documentation** for developers
- **Translation** to other languages
- **Example projects** and workflows

### Features
- **New export formats** support
- **Advanced animation** tools
- **Material management** system
- **Asset optimization** utilities

## Community

### Communication
- **GitHub Discussions** for general questions
- **GitHub Issues** for bug reports and feature requests
- **Discord** for real-time chat (VRChat Community)

### Code of Conduct
- Be **respectful** and inclusive
- Provide **constructive feedback**
- Help **newcomers** get started
- Focus on **collaboration** over competition

## License

By contributing, you agree that your contributions will be licensed under the same **GNU General Public License v3.0** that covers the project.

---

**Thank you for contributing to NYARC VRCat Tools!** 🎉