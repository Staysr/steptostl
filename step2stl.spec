# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration (Fixed for Windows/Conda)
"""

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ==========================================
# Safe print function
# ==========================================
def _safe_print(msg):
    try:
        print(msg)
    except:
        pass

_safe_print("=" * 70)
_safe_print("step2stl Build Configuration (Refined)")
_safe_print("=" * 70)

# ==========================================
# Helper: Detect Conda
# ==========================================
conda_prefix = os.environ.get('CONDA_PREFIX')
if not conda_prefix:
    # Try to guess from executable path
    try:
        if 'conda' in sys.executable.lower():
            conda_prefix = os.path.dirname(os.path.dirname(sys.executable))
    except:
        pass

_safe_print("CONDA_PREFIX: %s" % conda_prefix)
_safe_print("Platform: %s" % sys.platform)

# ==========================================
# Initialize
# ==========================================
hiddenimports = []
datas = []
binaries = []
pathex = []

# ==========================================
# Windows Conda DLL Fix (Crucial for Numpy/OCC)
# ==========================================
if sys.platform == 'win32' and conda_prefix:
    _safe_print("\n[Windows Conda Fix]")
    # 1. Add Library/bin to pathex so PyInstaller can find DLLs during analysis
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin')
    if os.path.exists(lib_bin):
        _safe_print("  Adding to pathex: %s" % lib_bin)
        pathex.append(lib_bin)
        
        # 2. Manually collect critical DLLs that hooks often miss
        # Numpy often needs MKL or OpenBLAS, OCC needs TBB/FreeImage
        dll_patterns = [
            'mkl_*.dll', 'libopenblas*.dll', 'libiomp5md.dll', # Numpy/BLAS
            'tbb*.dll', 'freeimage*.dll', 'freetype*.dll',     # OCC Deps
            'zlib*.dll', 'lzma*.dll'                           # Compression
        ]
        
        count = 0
        for pattern in dll_patterns:
            for dll in glob.glob(os.path.join(lib_bin, pattern)):
                # (source, destination_folder)
                binaries.append((dll, '.'))
                count += 1
        _safe_print("  Manually added %d critical DLLs from Library/bin" % count)

# ==========================================
# Collect Packages
# ==========================================

# 1. Numpy
_safe_print("\n[Collecting numpy]")
try:
    # collect_all finds the package, but sometimes misses external DLLs handled above
    np_hidden, np_bin, np_data = collect_all('numpy')
    hiddenimports += np_hidden
    binaries += np_bin
    datas += np_data
except Exception as e:
    _safe_print("  Warning: %s" % e)
    hiddenimports += ['numpy', 'numpy.core', 'numpy._core']

# 2. Jaraco (Dependency hell often lives here)
_safe_print("\n[Collecting jaraco]")
try:
    j_hidden, j_bin, j_data = collect_all('jaraco')
    hiddenimports += j_hidden
    datas += j_data
except:
    hiddenimports += ['jaraco.text', 'jaraco.functools', 'jaraco.context']

# 3. Trimesh
_safe_print("\n[Collecting trimesh]")
try:
    tm_hidden = collect_submodules('trimesh')
    hiddenimports += tm_hidden
except:
    hiddenimports += ['trimesh']

# 4. Standard Library & Misc
hiddenimports += [
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
    'shutil', 'tempfile', 'copy', 'zipfile'
]

# 5. OCC (Core logic handled by hook-OCC.py, but adding safety here)
hiddenimports += [
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
]

# ==========================================
# Analysis
# ==========================================
block_cipher = None

a = Analysis(
    ['step2stl.py'],
    pathex=pathex,  # Important: Includes Conda Library/bin
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./hooks'], # Points to your hook-OCC.py
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Clean up duplicates
a.binaries = list(set(a.binaries))
a.hiddenimports = list(set(a.hiddenimports))

# Remove pkg_resources hook if present (often causes issues)
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]

# Filter out trash binaries
def is_garbage(name):
    name = name.lower()
    return 'test' in name or 'example' in name

a.binaries = [x for x in a.binaries if not is_garbage(x[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='step2stl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # Disable UPX to prevent DLL corruption
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)