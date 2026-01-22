# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
修复 Windows ipaddress 导入错误
"""

from PyInstaller.utils.hooks import (
    collect_submodules, 
    collect_data_files, 
    collect_dynamic_libs,
    collect_all
)
import sys

# ==========================================
# 收集必要模块
# ==========================================
hiddenimports = []
datas = []
binaries = []

# 🔧 方案A：激进收集标准库（推荐）
stdlib_modules = [
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
]

for module in stdlib_modules:
    try:
        tmp = collect_all(module)
        hiddenimports += tmp[1]
        datas += tmp[0]
        binaries += tmp[2]
    except:
        hiddenimports.append(module)

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

# trimesh 模块
hiddenimports += collect_submodules('trimesh')

# numpy 核心
hiddenimports += collect_submodules('numpy')

# 收集 OCC 数据文件和库
datas += collect_data_files('OCC', include_py_files=True)
binaries += collect_dynamic_libs('OCC')

# ==========================================
# 排除不需要的模块
# ==========================================
excludes = [
    'tkinter', '_tkinter',
    'PyQt5', 'PyQt6',
    'matplotlib',
    'pandas',
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)

# ==========================================
# 过滤二进制文件
# ==========================================
def filter_binaries(binaries):
    filtered = []
    exclude_patterns = [
        'test', 'tests', 'testing',
        'example', 'examples',
        'doc', 'docs',
        '.pdb',
    ]
    for name, path, type_ in binaries:
        name_lower = name.lower()
        if not any(pattern in name_lower for pattern in exclude_patterns):
            filtered.append((name, path, type_))
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
    strip=False,  # Windows 不需要 strip
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