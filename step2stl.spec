# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration
"""

import sys
import os

# ==========================================
# Safe print function
# ==========================================
def _safe_print(msg):
    """Ultra-safe print"""
    try:
        print(msg)
    except:
        try:
            sys.stdout.write(str(msg) + '\n')
            sys.stdout.flush()
        except:
            pass

_safe_print("=" * 70)
_safe_print("step2stl Build Configuration")
_safe_print("=" * 70)

# ==========================================
# Environment info
# ==========================================
_safe_print("\n[Environment]")
_safe_print("Python: %s" % sys.version.split()[0])
_safe_print("Platform: %s" % sys.platform)
_safe_print("Executable: %s" % sys.executable)

conda_prefix = os.environ.get('CONDA_PREFIX', 'NOT SET')
_safe_print("CONDA_PREFIX: %s" % conda_prefix)

# ==========================================
# Import PyInstaller
# ==========================================
try:
    from PyInstaller.utils.hooks import collect_all, collect_submodules
    _safe_print("\n[OK] PyInstaller modules imported")
except Exception as e:
    _safe_print("\n[ERROR] Cannot import PyInstaller: %s" % str(e))
    raise

# ==========================================
# Helper functions
# ==========================================
def safe_filter_strings(items):
    if not items:
        return []
    return [str(item) for item in items if item and isinstance(item, str)]

def safe_filter_tuples(items):
    if not items:
        return []
    result = []
    for item in items:
        if isinstance(item, tuple) and len(item) >= 2:
            if all(isinstance(x, str) or x is None for x in item):
                result.append(item)
    return result

# ==========================================
# Initialize
# ==========================================
hiddenimports = []
datas = []
binaries = []

# ==========================================
# Collect numpy
# ==========================================
_safe_print("\n[Collecting numpy]")
try:
    numpy_result = collect_all('numpy')
    hiddenimports += safe_filter_strings(numpy_result[0])
    binaries += safe_filter_tuples(numpy_result[1])
    datas += safe_filter_tuples(numpy_result[2])
    _safe_print("  [OK]")
except Exception as e:
    _safe_print("  [WARNING] %s" % str(e))
    hiddenimports += ['numpy', 'numpy.core', 'numpy._core']

# ==========================================
# Collect jaraco
# ==========================================
_safe_print("\n[Collecting jaraco]")
try:
    jaraco_result = collect_all('jaraco')
    hiddenimports += safe_filter_strings(jaraco_result[0])
    datas += safe_filter_tuples(jaraco_result[2])
    _safe_print("  [OK]")
except Exception as e:
    _safe_print("  [WARNING] %s" % str(e))
    hiddenimports += ['jaraco', 'jaraco.text', 'jaraco.functools']

# ==========================================
# Standard library
# ==========================================
_safe_print("\n[Adding standard modules]")
hiddenimports += [
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
]
_safe_print("  [OK]")

# ==========================================
# OCC modules
# ==========================================
_safe_print("\n[Collecting OCC]")
hiddenimports += [
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
]

try:
    occ_all = collect_submodules('OCC.Core')
    hiddenimports += safe_filter_strings(occ_all)
    _safe_print("  [OK] %d modules" % len(occ_all))
except Exception as e:
    _safe_print("  [WARNING] %s" % str(e))

# ==========================================
# Trimesh
# ==========================================
_safe_print("\n[Collecting trimesh]")
try:
    trimesh_modules = collect_submodules('trimesh')
    hiddenimports += safe_filter_strings(trimesh_modules)
    _safe_print("  [OK]")
except:
    hiddenimports += ['trimesh']
    _safe_print("  [FALLBACK]")

# ==========================================
# Deduplicate
# ==========================================
hiddenimports = list(set(safe_filter_strings(hiddenimports)))
binaries = safe_filter_tuples(binaries)
datas = safe_filter_tuples(datas)

_safe_print("\n[Summary]")
_safe_print("  hiddenimports: %d" % len(hiddenimports))
_safe_print("  binaries: %d" % len(binaries))
_safe_print("  datas: %d" % len(datas))

# ==========================================
# Excludes
# ==========================================
excludes = [
    'tkinter', 'PyQt5', 'PyQt6', 'matplotlib',
    'pandas', 'scipy', 'pytest', 'IPython',
]

# ==========================================
# Analysis
# ==========================================
_safe_print("\n" + "=" * 70)
_safe_print("Creating Analysis...")
_safe_print("=" * 70 + "\n")

# NOTE: Analysis, PYZ, EXE are injected by PyInstaller at runtime
# They are not available during normal Python execution

a = Analysis(
    ['step2stl.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Remove pkg_resources hook
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]

# Filter binaries
def should_keep(name):
    if not isinstance(name, str):
        return True
    name_lower = name.lower()
    exclude_patterns = ['test', 'example', 'doc', '.pdb']
    return not any(e in name_lower for e in exclude_patterns)

a.binaries = [(n, p, t) for n, p, t in a.binaries if should_keep(n)]

_safe_print("[Final Summary]")
_safe_print("  scripts: %d" % len(a.scripts))
_safe_print("  binaries: %d" % len(a.binaries))
_safe_print("  datas: %d" % len(a.datas))

# Check TK libraries
tk_libs = [b[0] for b in a.binaries if 'TK' in b[0] or 'tk' in b[0].lower()]
if tk_libs:
    _safe_print("  TK libraries: %d [OK]" % len(tk_libs))
else:
    _safe_print("  TK libraries: 0 [WARNING]")

_safe_print("")

# ==========================================
# PYZ & EXE
# ==========================================
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='step2stl',
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

_safe_print("=" * 70)
_safe_print("Build configuration completed")
_safe_print("=" * 70)