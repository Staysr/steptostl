# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller Build Configuration - Optimized for Windows Conda
"""

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ==========================================
# Safe print function
# ==========================================
def _safe_print(msg):
    try:
        print(msg)
    except:
        pass

_safe_print("=" * 70)
_safe_print("step2stl Build Configuration (Refactored)")
_safe_print("=" * 70)

# ==========================================
# Helper: Collect Conda DLLs (The Fix)
# ==========================================
def get_conda_dlls():
    """
    专门解决 Windows 下 "ImportError: DLL load failed" 问题
    直接从 Conda Library/bin 目录收集核心 DLL
    """
    binaries =
    # 仅在 Windows 下执行此逻辑
    if sys.platform!= 'win32':
        return binaries

    conda_prefix = os.environ.get('CONDA_PREFIX')
    if not conda_prefix:
        _safe_print("WARNING: CONDA_PREFIX not set. DLL collection may fail.")
        return binaries

    # Conda 的 DLL 仓库
    dll_dir = os.path.join(conda_prefix, 'Library', 'bin')
    if not os.path.exists(dll_dir):
        _safe_print(f"WARNING: Library/bin not found at {dll_dir}")
        return binaries

    _safe_print(f"Collecting DLLs from: {dll_dir}")
    
    # 关键：手动收集这些数学库和运行时库
    # MKL (Intel Math Kernel Library)
    # OpenBLAS (如果 numpy 是 conda-forge 版)
    # TBB (OpenCASCADE 依赖)
    patterns = [
        'mkl_*.dll', 
        'libopenblas*.dll', 
        'tbb*.dll', 
        'vcruntime*.dll',
        'msvcp*.dll',
        'freetype*.dll'
    ]
    
    count = 0
    for pattern in patterns:
        search_path = os.path.join(dll_dir, pattern)
        for dll_file in glob.glob(search_path):
            # 格式: (源文件路径, 目标文件夹)
            # '.' 表示放在 exe 同级目录，这是 Windows 加载 DLL 的第一搜索位
            binaries.append((dll_file, '.'))
            count += 1
            
    _safe_print(f"  Collected {count} critical DLLs manually")
    return binaries

# ==========================================
# Initialize
# ==========================================
hiddenimports =
datas =
binaries =

# ==========================================
# 1. NumPy (Standard Hook + Hidden Imports)
# ==========================================
# 注意：我们不再使用 collect_all('numpy')，因为它会漏掉 Conda 的 DLL
# 我们改用 PyInstaller 内置 hook + 手动 hiddenimports
hiddenimports += ['numpy', 'numpy.core', 'numpy.lib', 'numpy.linalg', 'numpy.random']

# ==========================================
# 2. Jaraco & Standard Libs
# ==========================================
datas += collect_data_files('jaraco')
hiddenimports += collect_submodules('jaraco')
hiddenimports += [
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
]

# ==========================================
# 3. OCC Modules
# ==========================================
hiddenimports += ['OCC', 'OCC.Core']
try:
    # 收集 OCC 所有子模块
    occ_all = collect_submodules('OCC.Core')
    hiddenimports += occ_all
except:
    pass

# ==========================================
# 4. Trimesh
# ==========================================
try:
    hiddenimports += collect_submodules('trimesh')
except:
    hiddenimports += ['trimesh']

# ==========================================
# 5. Inject Conda DLLs (核心修复步骤)
# ==========================================
# 将手动收集的 DLL 加入构建列表
binaries += get_conda_dlls()

# ==========================================
# Analysis & Build
# ==========================================
excludes = [
    'tkinter', 'PyQt5', 'PyQt6', 'matplotlib',
    'pandas', 'scipy', 'pytest', 'IPython', 'PIL'
]

a = Analysis(
    ['step2stl.py'],
    pathex=,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./hooks'],
    hooksconfig={},
    runtime_hooks=,
    excludes=excludes,
    noarchive=False,
)

# 移除 pkg_resources hook (常引起路径错误)
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
   ,
    name='step2stl',
    debug=False,
    strip=False,
    upx=False,
    console=True,
)