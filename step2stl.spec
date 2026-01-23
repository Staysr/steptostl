# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration (Nuclear Option for Win7)
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
_safe_print("step2stl Build Config (Nuclear Option)")
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

_safe_print(f"Conda Prefix: {conda_prefix}")

# ==========================================
# 3. Init
# ==========================================
hiddenimports = []
datas = []
binaries = []
pathex = []

# ==========================================
# 4. DLL Collection (The Nuclear Approach)
# ==========================================
if sys.platform == 'win32' and conda_prefix:
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin')
    
    if os.path.exists(lib_bin):
        pathex.append(lib_bin)
        _safe_print("\n[DLL Injection: Nuclear Mode]")
        _safe_print("Copying ALL DLLs from Library/bin to ensure Win7 compatibility...")
        
        # 暴力获取所有 DLL，不再筛选
        all_dlls = glob.glob(os.path.join(lib_bin, '*.dll'))
        
        count = 0
        for dll_path in all_dlls:
            dll_name = os.path.basename(dll_path).lower()
            
            # 排除 python 自身的 dll，防止冲突 (由 PyInstaller 处理)
            if dll_name.startswith('python3') or dll_name == 'python.dll':
                continue
                
            # 排除一些典型的系统级驱动，避免权限问题
            if dll_name in ['opengl32.dll', 'glu32.dll', 'd3d9.dll', 'kernel32.dll']:
                continue

            binaries.append((dll_path, '.'))
            count += 1
            
        _safe_print(f"  Brute-force injected {count} DLLs.")
    else:
        _safe_print("Warning: Library/bin not found!")

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
    'OCC.Core.TCollection', 'OCC.Core.TColStd', 'OCC.Core.Standard', # 增加一些基础模块
    'OCC.Core.TopoDS', 'OCC.Core.TopExp'
])

# Misc
hiddenimports.extend([
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
    'shutil', 'tempfile', 'copy', 'zipfile', 'ctypes', 'typing'
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
    binaries=binaries, # 包含了所有的 Library/bin DLL
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
    upx=False, # 坚决关闭 UPX，Win7 对压缩壳很敏感
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)