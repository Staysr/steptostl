# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration (Win7 FINAL FIX)
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
_safe_print("step2stl Build Config (Win7 PATH FIX)")
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
    conda_bin = os.path.join(conda_prefix, 'bin')
    
    # 将可能的路径都加上
    search_dirs = [lib_bin, conda_bin]
    
    for d in search_dirs:
        if os.path.exists(d):
            pathex.append(d)
    
    _safe_print("\n[Collecting Critical DLLs]")
    
    # 针对 Win7 的全量 DLL 收集
    # 注意：这里我们增加了 d3dcompiler (Direct3D) 和 opengl，防止图形库报错
    dll_patterns = [
        'TK*.dll',         # OCC Core
        'tbb*.dll',        # TBB
        'freeimage*.dll',  # FreeImage
        'freetype*.dll',   # Freetype
        'gl*.dll', 'opengl*.dll', # OpenGL
        'd3dcompiler*.dll', # Direct3D (Win7 sometimes lacks this)
        'mkl_*.dll', 'libopenblas*.dll', 'libiomp5md.dll', # Numpy
        'api-ms-win-*.dll', # UCRT Forwarders
        'ucrtbase.dll',
        'vcruntime*.dll',
        'msvcp*.dll',
        'concrt*.dll',
        'zlib*.dll',
        'sqlite3.dll'
    ]
    
    count = 0
    for s_dir in search_dirs:
        if not os.path.exists(s_dir): continue
        
        for pattern in dll_patterns:
            found = glob.glob(os.path.join(s_dir, pattern))
            for dll in found:
                # 排除 debug DLL
                if dll.lower().endswith('d.dll') and not dll.lower().endswith('bnd.dll'):
                    continue
                # 排除 python3.dll (防止冲突)
                if 'python3.dll' in dll.lower():
                    continue
                    
                binaries.append((dll, '.'))
                count += 1

    _safe_print(f"  Collected {count} DLLs for bundling.")

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

# OCC
hiddenimports.extend([
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
    'OCC.Core.TCollection', 'OCC.Core.Standard', 'OCC.Core.TopoDS',
    'OCC.Core.Wrappers' # 可能会用到
])

# Misc
hiddenimports.extend([
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
    'shutil', 'tempfile', 'copy', 'zipfile', 'ctypes', 'typing', 'sys', 'os'
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
    # 关键修改：同时加载 Win7 路径修复钩子 和 编码修复钩子
    runtime_hooks=['./rthook_win7.py', './rthook_encoding.py'],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython', 'numpy.f2py.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

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