# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration (Win7 OCC/TK Fix)
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
_safe_print("step2stl Build Config (Win7 + OCC DLL Fix)")
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
# 4. Critical DLL Collection
# ==========================================
if sys.platform == 'win32' and conda_prefix:
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin')
    
    if os.path.exists(lib_bin):
        pathex.append(lib_bin)
        _safe_print("\n[Collecting Critical DLLs]")
        
        # 4.1 OpenCASCADE Core DLLs (The missing link for StlAPI)
        # OCC 的核心是由几十个 TK 开头的 DLL 组成的，必须全部打包
        occ_patterns = [
            'TK*.dll',         # OCC 核心组件 (TKKernel, TKMath, TKStl...)
            'tbb*.dll',        # Intel TBB (OCC 依赖)
            'freeimage*.dll',  # 图像处理 (OCC 依赖)
            'freetype*.dll',   # 字体 (OCC 依赖)
            'gl*.dll',         # OpenGL
            'freet*.dll'
        ]

        # 4.2 Win7 System / Numpy DLLs
        sys_patterns = [
            'mkl_*.dll', 'libopenblas*.dll', 'libiomp5md.dll',
            'api-ms-win-*.dll', # Win7 API 垫片
            'ucrtbase.dll',     # C 运行时
            'vcruntime*.dll',   # VC 运行时
            'msvcp*.dll',       # VC++ 运行时
            'concrt*.dll',
            'zlib*.dll'
        ]
        
        all_patterns = occ_patterns + sys_patterns
        
        count = 0
        for pattern in all_patterns:
            found_dlls = glob.glob(os.path.join(lib_bin, pattern))
            for dll in found_dlls:
                # 排除 debug 版本 (以 d.dll 结尾) 减小体积
                if dll.lower().endswith('d.dll') and not dll.lower().endswith('bnd.dll'):
                    continue
                binaries.append((dll, '.'))
                count += 1
                
        _safe_print(f"  Collected {count} DLLs (TK*, TBB, System)")

# ==========================================
# 5. Collect Python Dependencies
# ==========================================
# Numpy
try:
    np_hidden, np_bin, np_data = collect_all('numpy')
    if np_hidden: hiddenimports.extend(np_hidden)
    if np_bin: binaries.extend(np_bin)
    if np_data: datas.extend(np_data)
except:
    hiddenimports.extend(['numpy', 'numpy.core', 'numpy._core'])

# Jaraco
try:
    j_hidden, j_bin, j_data = collect_all('jaraco')
    if j_hidden: hiddenimports.extend(j_hidden)
    if j_data: datas.extend(j_data)
except:
    hiddenimports.extend(['jaraco.text', 'jaraco.functools', 'jaraco.context'])

# Trimesh
try:
    tm_hidden = collect_submodules('trimesh')
    if tm_hidden: hiddenimports.extend(tm_hidden)
except:
    hiddenimports.append('trimesh')

# OCC (Python side)
hiddenimports.extend([
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
    'OCC.Core.TCollection', 'OCC.Core.Standard', 'OCC.Core.TopoDS'
])

# Misc
hiddenimports.extend([
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
    'shutil', 'tempfile', 'copy', 'zipfile', 'ctypes'
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

# Remove pkg_resources
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
    upx=False, # Win7 必须关闭 UPX
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)