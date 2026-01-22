# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
修复 numpy 模块收集问题
"""

from PyInstaller.utils.hooks import (
    collect_submodules, 
    collect_data_files, 
    collect_dynamic_libs,
)
import sys

# ==========================================
# 收集必要模块
# ==========================================
hiddenimports = []

# 🔧 修复 PyInstaller 6.8+ jaraco 错误
hiddenimports += [
    'jaraco',
    'jaraco.text',
    'jaraco.functools',
]

# 🔧 标准库模块
hiddenimports += [
    'ipaddress',
    'urllib',
    'urllib.parse',
    'urllib.request',
    'urllib.error',
    'email',
    'email.mime',
    'email.mime.text',
    'pathlib',
    'zipfile',
    'argparse',
    'collections',
    'collections.abc',
    'warnings',
    'traceback',
    'gc',
    'time',
    'os',
    'sys',
    're',
]

# OCC 核心模块
hiddenimports += [
    'OCC.Core.STEPControl',
    'OCC.Core.StlAPI',
    'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect',
    'OCC.Core.Bnd',
    'OCC.Core.BRepBndLib',
    'OCC.Core.TopoDS',
    'OCC.Core.TopAbs',
    'OCC.Core.gp',
]

# 🔧 关键修复：完整收集 numpy 模块
print("Collecting numpy modules...")
try:
    # 方法1：收集所有 numpy 子模块（推荐）
    hiddenimports += collect_submodules('numpy')
    print(f"  ✓ Collected {len([m for m in hiddenimports if 'numpy' in m])} numpy modules")
except Exception as e:
    print(f"  Warning: Failed to collect numpy submodules: {e}")
    # 方法2：手动添加关键模块（备用）
    hiddenimports += [
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'numpy.core.multiarray',
        'numpy.core._methods',
        'numpy.core._internal',
        'numpy.core.function_base',
        'numpy.random',
        'numpy.random._pickle',
        'numpy.fft',
        'numpy.linalg',
        'numpy.polynomial',
        # 🔧 关键：添加缺失的模块
        'numpy._core',
        'numpy._core._multiarray_tests',
        'numpy._core._multiarray_umath',
        'numpy._core.multiarray',
        'numpy._core._methods',
        'numpy._core._internal',
        'numpy._core.function_base',
        'numpy._core._add_newdocs',
        'numpy._core._dtype',
        'numpy._core._exceptions',
        'numpy._core.numerictypes',
        'numpy._core.shape_base',
        'numpy._core.numeric',
        'numpy._core.fromnumeric',
    ]

# trimesh 模块
print("Collecting trimesh modules...")
try:
    hiddenimports += collect_submodules('trimesh')
    print(f"  ✓ Collected trimesh modules")
except Exception as e:
    print(f"  Warning: Failed to collect trimesh: {e}")

# ==========================================
# 收集数据文件和动态库
# ==========================================
datas = []
binaries = []

# OCC 数据文件
try:
    datas += collect_data_files('OCC', include_py_files=True)
except:
    pass

# OCC 动态库
try:
    binaries += collect_dynamic_libs('OCC')
except:
    pass

# 🔧 numpy 数据文件（可能需要）
try:
    numpy_datas = collect_data_files('numpy', include_py_files=False)
    if numpy_datas:
        datas += numpy_datas
        print(f"  ✓ Collected numpy data files")
except:
    pass

# ==========================================
# 排除不需要的模块
# ==========================================
excludes = [
    # GUI 相关
    'tkinter', '_tkinter',
    'PyQt5', 'PyQt6',
    'PySide2', 'PySide6',
    
    # 科学计算（不需要的部分）
    'matplotlib',
    'pandas',
    'scipy',
    
    # 测试相关
    'pytest',
    'IPython',
]

# ==========================================
# Analysis 配置
# ==========================================
a = Analysis(
    ['step2stl.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# 🔧 移除 pkg_resources runtime hook
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]

# ==========================================
# 过滤二进制文件
# ==========================================
def filter_binaries(binaries_list):
    filtered = []
    exclude_patterns = [
        'test', 'tests', 'testing',
        'example', 'examples',
        'doc', 'docs',
        '.pdb',
    ]
    for item in binaries_list:
        if isinstance(item, tuple) and len(item) >= 2:
            name = item[0]
            name_lower = name.lower() if isinstance(name, str) else ''
            if not any(pattern in name_lower for pattern in exclude_patterns):
                filtered.append(item)
        else:
            filtered.append(item)
    return filtered

a.binaries = filter_binaries(a.binaries)

# ==========================================
# PYZ 配置
# ==========================================
pyz = PYZ(a.pure)

# ==========================================
# EXE 配置
# ==========================================
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
    icon=None,
)