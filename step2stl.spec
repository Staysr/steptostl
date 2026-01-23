# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration (Win7 Ultimate Fix)
"""

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ==========================================
# 1. Helper Functions
# ==========================================
def _safe_print(msg):
    try:
        print(msg)
    except:
        pass

def sanitize_imports(raw_list):
    clean = []
    if not raw_list: return clean
    for item in raw_list:
        if item and isinstance(item, str):
            clean.append(item)
    return list(set(clean))

def sanitize_tuples(raw_list):
    clean = []
    if not raw_list: return clean
    for item in raw_list:
        if isinstance(item, tuple) and len(item) == 2:
            if isinstance(item[0], str) and isinstance(item[1], str):
                clean.append(item)
    return list(set(clean))

_safe_print("=" * 70)
_safe_print("step2stl Build Config (Win7 Ultimate Mode)")
_safe_print("=" * 70)

# ==========================================
# 2. Environment
# ==========================================
conda_prefix = os.environ.get('CONDA_PREFIX')
if not conda_prefix:
    try:
        if 'conda' in sys.executable.lower():
            conda_prefix = os.path.dirname(os.path.dirname(sys.executable))
    except:
        pass

# ==========================================
# 3. Init
# ==========================================
hiddenimports = []
datas = []
binaries = []
pathex = []

# ==========================================
# 4. Windows 7 DLL Injection (CRITICAL)
# ==========================================
if sys.platform == 'win32' and conda_prefix:
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin')
    conda_bin = os.path.join(conda_prefix, 'bin') # Sometimes DLLs are here
    
    # Add search paths
    if os.path.exists(lib_bin): pathex.append(lib_bin)
    if os.path.exists(conda_bin): pathex.append(conda_bin)

    _safe_print("\n[Windows 7 Hardcore Fix]")
    
    # 4.1. Standard Dependencies (OCC/Numpy/MKL)
    dll_patterns = [
        'mkl_*.dll', 'libopenblas*.dll', 'libiomp5md.dll', # Numpy
        'tbb*.dll', 'freeimage*.dll', 'freetype*.dll',     # OCC
        'zlib*.dll', 'lzma*.dll',                          # Compression
        'sqlite3.dll'
    ]
    
    # 4.2. UCRT & System API DLLs (The Win7 Fix)
    # 强行打包 UCRT 和 api-ms-win-* 使得程序自带运行环境
    win7_patterns = [
        'ucrtbase.dll',
        'api-ms-win-*.dll',
        'vcruntime*.dll',
        'msvcp*.dll',
        'concrt*.dll'
    ]
    
    all_patterns = dll_patterns + win7_patterns
    
    count = 0
    # Search in both Library/bin and bin (sometimes location varies)
    for search_dir in [lib_bin, conda_bin]:
        if not os.path.exists(search_dir): continue
        
        for pattern in all_patterns:
            found = glob.glob(os.path.join(search_dir, pattern))
            for dll in found:
                # Pack them next to the executable
                binaries.append((dll, '.'))
                count += 1
                
    _safe_print(f"  Injected {count} DLLs (including UCRT/API-MS) for Win7 compatibility")

# ==========================================
# 5. Collect Python Dependencies
# ==========================================
try:
    np_hidden, np_bin, np_data = collect_all('numpy')
    if np_hidden: hiddenimports.extend(np_hidden)
    if np_bin: binaries.extend(np_bin)
    if np_data: datas.extend(np_data)
except:
    hiddenimports.extend(['numpy', 'numpy.core', 'numpy._core'])

try:
    j_hidden, j_bin, j_data = collect_all('jaraco')
    if j_hidden: hiddenimports.extend(j_hidden)
    if j_data: datas.extend(j_data)
except:
    hiddenimports.extend(['jaraco.text', 'jaraco.functools', 'jaraco.context'])

try:
    tm_hidden = collect_submodules('trimesh')
    if tm_hidden: hiddenimports.extend(tm_hidden)
except:
    hiddenimports.append('trimesh')

hiddenimports.extend([
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
    'shutil', 'tempfile', 'copy', 'zipfile', 'ctypes'
])

hiddenimports.extend([
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
])

# ==========================================
# 6. Sanitize
# ==========================================
hiddenimports = sanitize_imports(hiddenimports)
binaries = sanitize_tuples(binaries)
datas = sanitize_tuples(datas)

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
    runtime_hooks=['./rthook_encoding.py'],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython', 'numpy.f2py.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove pkg_resources hook
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