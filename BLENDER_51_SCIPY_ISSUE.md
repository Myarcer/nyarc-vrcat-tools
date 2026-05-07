# Blender 5.1 — scipy DLL Loading Issue

## Status: UNSOLVED — ctypes SetDefaultDllDirectories fix UNTESTED but most promising (see below)

## Summary

scipy installs correctly but **cannot import its compiled extensions (.pyd)** when running inside Blender 5.1's process. The exact same Python executable, same scipy install, same paths — works perfectly outside Blender, fails inside.

## Root Cause

Blender 5.1's process restricts DLL search in a way that prevents scipy's `.pyd` files from finding the bundled openblas DLL (`libscipy_openblas-*.dll` in `scipy.libs/`).

### Proof: Same Python, Different Results

```
# OUTSIDE Blender (standalone Python) — WORKS
> "C:\Program Files (x86)\Steam\steamapps\common\Blender\5.1\python\bin\python.exe" -c "
  import site, sysconfig
  site.addsitedir('<deps>/Python313/site-packages')
  import scipy  # OK: 1.17.1
  import robust_laplacian  # OK
"

# INSIDE Blender — FAILS
# scipy.__init__.py raises:
# "The scipy install you are using seems to be broken,
#  (extension modules cannot be imported)"
```

### What scipy Does Internally

scipy 1.17.1 ships with a `_delvewheel_patch` in `scipy/__init__.py`:
```python
def _delvewheel_patch_1_12_0():
    import os
    libs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'scipy.libs'))
    if os.path.isdir(libs_dir):
        os.add_dll_directory(libs_dir)
```

This computes the correct path to `scipy.libs/` and calls `os.add_dll_directory()`. It works in standalone Python but NOT inside Blender's process.

### Why It Fails Inside Blender

Blender likely calls Windows `SetDefaultDllDirectories()` at startup with flags that exclude `LOAD_LIBRARY_SEARCH_USER_DIRS`. This means:
- `os.add_dll_directory()` has no effect (user dirs not searched)
- `PATH` environment variable changes have no effect (safe DLL search ignores PATH)
- Only DLLs in system directories or the executable's directory are found

## Methods Attempted (ALL FAILED inside Blender 5.1)

| Method | Code | Result |
|--------|------|--------|
| `os.add_dll_directory()` | `os.add_dll_directory(scipy_libs_path)` | No effect |
| PATH prepend | `os.environ['PATH'] = libs + os.pathsep + PATH` | No effect |
| `ctypes` pre-load | `ctypes.WinDLL(full_dll_path)` | DLL loads into process, but .pyd still can't find it — this does NOT change search flags, `LOAD_LIBRARY_SEARCH_USER_DIRS` still absent |
| `site.addsitedir()` | `site.addsitedir(user_site_path)` | Adds Python path, doesn't help DLLs |
| All four combined | All of the above at once | Still fails |

> **Key insight on the ctypes attempt:** `ctypes.WinDLL(path)` and `SetDefaultDllDirectories()` are completely different operations. Loading the DLL manually does not restore the process-wide search flags. `os.add_dll_directory()` remains inert until `LOAD_LIBRARY_SEARCH_USER_DIRS` is re-enabled.

## Environment Details

- Blender 5.1 (Steam install, `C:\Program Files (x86)\Steam\...`)
- Python 3.13 (bundled with Blender)
- scipy 1.17.1 cp313-cp313-win_amd64
- robust-laplacian 1.0.0 cp313-cp313-win_amd64
- numpy 2.3.4 (bundled with Blender, works fine)
- Windows 10

## SENT Robust Weight Transfer — Same Issue

SENT (v1.1.9) uses the identical loading pattern:
```python
libs_path = os.path.join(os.path.dirname(__file__), 'deps')
scheme = sysconfig.get_preferred_scheme("user")
user_site = sysconfig.get_paths(scheme, vars={"userbase": libs_path})["purelib"]
site.addsitedir(user_site)
```

SENT is also broken on Blender 5.1:
```
File "...\robust-weight-transfer\deps\igl\__init__.py", line 8
    from .pyigl import *
ModuleNotFoundError: No module named 'igl.pyigl'
```

Their `libigl26` branch (for 5.1 compat) has the same loading code — just pins `libigl==2.6.1` instead of `2.5.1`. **They have NOT solved the DLL loading issue.** Developer acknowledged in issue #16 (Mar 19): *"added a libigl2.6 zip to the current release as temp. solution. ideally gonna have a single codebase and release."*

SENT's `InstallDependencies` operator uses `pip install --user` with `PYTHONUSERBASE` pointing to the addon `deps/` folder, then `site.addsitedir()` — same root failure as our approach on 5.1.

## What Works on 4.2 LTS

On Blender 4.2.1 LTS (Python 3.11), the simple approach works:
```python
deps_path = os.path.join(os.path.dirname(__file__), 'deps')
if os.path.exists(deps_path) and deps_path not in sys.path:
    sys.path.insert(0, deps_path)
```

With installer: `pip install --target deps_dir --no-deps scipy robust-laplacian`

Blender 4.2's process does not restrict DLL search the same way, so scipy's own `_delvewheel_patch` works.

## Blender 5.0 — WORKING

- Blender 5.0.1, Python 3.11 (same as 4.2 LTS)
- **Simple `--target` + `sys.path.insert` approach works** (same as 4.2)
- `robust-laplacian==1.0.0` imports and works correctly
- `robust-laplacian==1.1.0` **crashes Blender** (segfault in `PyInit_robust_laplacian_bindings`, `MSVCP140.dll` access violation at null) — MUST pin to 1.0.0
- scipy 1.17.1 cp311 wheel imports fine — no DLL search restriction in 5.0's process
- **5.0 does NOT have the `SetDefaultDllDirectories` restriction that 5.1 has**

## Potential Solutions (Not Yet Tried)

### 🔥 Most Promising — Re-enable user DLL dirs via SetDefaultDllDirectories

Blender calls `SetDefaultDllDirectories()` without `LOAD_LIBRARY_SEARCH_USER_DIRS` (flag `0x0400`), which makes `os.add_dll_directory()` a no-op. Fix: call it from Python before importing scipy to add the flag back:

```python
import ctypes
import os
import sys

if sys.platform == 'win32':
    LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000
    LOAD_LIBRARY_SEARCH_USER_DIRS    = 0x00000400
    ctypes.windll.kernel32.SetDefaultDllDirectories(
        LOAD_LIBRARY_SEARCH_DEFAULT_DIRS | LOAD_LIBRARY_SEARCH_USER_DIRS
    )
    # Now os.add_dll_directory() will actually work
    scipy_libs = os.path.join(deps_path, 'scipy.libs')
    if os.path.isdir(scipy_libs):
        os.add_dll_directory(scipy_libs)

import scipy  # should work now
```

**Why this is different from what we tried:** Previous `ctypes.WinDLL(full_dll_path)` attempt loaded the specific DLL manually but left the process-wide search flags unchanged — `os.add_dll_directory()` still had no effect. `SetDefaultDllDirectories(0x1400)` modifies the Windows DLL search policy itself.

**Caveat:** Must run *before* first scipy import. If Blender re-calls `SetDefaultDllDirectories` after addon registration, it won't help — but Blender only does this at startup.

---

1. **Install scipy to Blender's own site-packages** — DLLs next to Blender's own libraries would be in the trusted search path. Requires admin/write access to `C:\Program Files\...\Blender\python\Lib\site-packages\`.

2. **Copy openblas DLL to Blender's DLLs directory** — `C:\...\Blender\5.1\python\DLLs\` is always in the search path.

3. **Copy openblas DLL next to scipy's .pyd files** — e.g., into `scipy/_lib/` alongside `_ccallback_c.pyd`. The `LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR` flag searches the .pyd's own directory.

4. **Use Blender's extension manifest with bundled wheels** — the "official" Blender 5.0+ approach. Bundle `.whl` files in `./wheels/`, list them in `blender_manifest.toml`. Blender extracts them into an isolated `site-packages` and handles DLL paths itself — bypasses the whole issue. Requires ~30MB of scipy/libigl/robust-laplacian wheels per platform (win_amd64, manylinux, macos arm64/x64). Needs manifest + `bl_info` migration.

5. **Wait for Blender fix** — if Blender's DLL search restriction is unintentional, it may be fixed in a future release.

## Version Constraints

- `robust-laplacian` MUST be pinned to `==1.0.0` — **CONFIRMED: v1.1.0 crashes Blender**
  - SENT v1.1.9 release notes (Mar 27): *"Fix Blender crash (constrained robust_laplacian to 1.0.0)"*
  - Timeline: v1.1.0 released Mar 24, SENT pinned 3 days later
  - Root cause: v1.1.0 is "rebuilt with latest dependencies" (newer pybind11/Eigen). ABI incompatibility with other compiled extensions (scipy, libigl) causes segfault on import inside Blender's process
  - This is NOT a DLL search issue — it crashes even if import succeeds
- `scipy` 1.17.1 is the latest with cp313 wheels
- `numpy` is bundled with Blender — do NOT install a second copy (use `--no-deps` or constraints)

## Other Blender 5.1 API Changes (Already Fixed)

- `vertex_colors` API → `color_attributes` (4.3+) — dual-compat helpers in `debug.py`
- `SEQUENCE_COLOR_*` icons → `STRIP_COLOR_*` (4.4+) — version check in `list_ui.py` and `main_panel.py`
- `bl_info` dict still works (manifest not yet mandatory)
- `bgl` module removed (not used by us)
- `super().__init__()` required in 4.4 for bpy subclasses (doesn't affect us)
