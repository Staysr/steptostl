# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration (Sanitized)
"""

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ==========================================
# 1. Helper Functions (Fixes TypeError)
# ==========================================
def _safe_print(msg):
    try:
        print(msg)
    except:
        pass

def sanitize_imports(raw_list):
    """
    过滤 hiddenimports，确保里面全是字符串。
    解决 TypeError: expected string or bytes-like object
    """
    clean = []
    if not raw_list:
        return clean
    for item in raw_list:
        if item and isinstance(item, str):
            clean.append(item)
    return list(set(clean))  # 去重

def sanitize_tuples(raw_list):
    """过滤 binaries 和 datas，确保是 (str, str) 格式"""
    clean = []
    if not raw_list:
        return clean
    for item in raw_list:
        if isinstance(item, tuple) and len(item) == 2:
            # 确保元组里的元素也是字符串
            if isinstance(item[0], str) and isinstance(item[1], str):
                clean.append(item)
    return list(set(clean))

_safe_print("=" * 70)
_safe_print("step2stl Build Config (Sanitized Mode)")
_safe_print("=" * 70)

# ==========================================
# 2. Environment & Conda Detection
# ==========================================
conda_prefix = os.environ.get('CONDA_PREFIX')
if not conda_prefix:
    try:
        if 'conda' in sys.executable.lower():
            conda_prefix = os.path.dirname(os.path.dirname(sys.executable))
    except:
        pass

_safe_print("CONDA_PREFIX: %s" % conda_prefix)
_safe_print("Platform: %s" % sys.platform)

# ==========================================
# 3. Initialization
# ==========================================
hiddenimports = []
datas = []
binaries = []
pathex = []

# ==========================================
# 4. Windows Conda DLL Fix
# ==========================================
if sys.platform == 'win32' and conda_prefix:
    _safe_print("\n[Windows Conda Fix]")
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin')
    if os.path.exists(lib_bin):
        _safe_print("  Adding to pathex: %s" % lib_bin)
        pathex.append(lib_bin)
        
        # Manually collect critical DLLs
        dll_patterns = [
            'mkl_*.dll', 'libopenblas*.dll', 'libiomp5md.dll',
            'tbb*.dll', 'freeimage*.dll', 'freetype*.dll',
            'zlib*.dll', 'lzma*.dll'
        ]
        
        for pattern in dll_patterns:
            for dll in glob.glob(os.path.join(lib_bin, pattern)):
                binaries.append((dll, '.'))

# ==========================================
# 5. Collect Dependencies
# ==========================================

# --- Numpy ---
_safe_print("\n[Collecting numpy]")
try:
    np_hidden, np_bin, np_data = collect_all('numpy')
    if np_hidden: hiddenimports.extend(np_hidden)
    if np_bin: binaries.extend(np_bin)
    if np_data: datas.extend(np_data)
except Exception as e:
    _safe_print("  Warning: %s" % e)
    hiddenimports.extend(['numpy', 'numpy.core', 'numpy._core'])

# --- Jaraco ---
_safe_print("\n[Collecting jaraco]")
try:
    j_hidden, j_bin, j_data = collect_all('jaraco')
    if j_hidden: hiddenimports.extend(j_hidden)
    if j_data: datas.extend(j_data)
except:
    hiddenimports.extend(['jaraco.text', 'jaraco.functools', 'jaraco.context'])

# --- Trimesh ---
_safe_print("\n[Collecting trimesh]")
try:
    tm_hidden = collect_submodules('trimesh')
    if tm_hidden: hiddenimports.extend(tm_hidden)
except:
    hiddenimports.append('trimesh')

# --- Standard Lib ---
hiddenimports.extend([
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
    'shutil', 'tempfile', 'copy', 'zipfile'
])

# --- OCC ---
hiddenimports.extend([
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
])

# ==========================================
# 6. SANITIZE DATA (Critical Step)
# ==========================================
# 这里是修复 TypeError 的关键步骤
# PyInstaller 不能处理 None 或非字符串类型，必须清洗
_safe_print("\n[Sanitizing Data]")
hiddenimports = sanitize_imports(hiddenimports)
binaries = sanitize_tuples(binaries)
datas = sanitize_tuples(datas)

_safe_print("  Hidden Imports: %d" % len(hiddenimports))
_safe_print("  Binaries: %d" % len(binaries))

# ==========================================
# 7. Analysis
# ==========================================
block_cipher = None

a = Analysis(
    ['step2stl.py'],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython', 'numpy.f2py.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove pkg_resources hook if present
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]

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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)