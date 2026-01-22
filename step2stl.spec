# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
修复 Windows/macOS 兼容性问题
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

# 🔧 标准库模块（简单列举，不用 collect_all）
hiddenimports += [
    # Python 标准库
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

# trimesh 模块（收集所有子模块）
try:
    hiddenimports += collect_submodules('trimesh')
except:
    pass

# numpy 核心模块
hiddenimports += [
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',
    'numpy.core.multiarray',
    'numpy.random',
]

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

# ==========================================
# 排除不需要的模块
# ==========================================
excludes = [
    # GUI 相关
    'tkinter', '_tkinter',
    'PyQt5', 'PyQt6',
    'PySide2', 'PySide6',
    
    # 科学计算（不需要）
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
        # 处理不同格式的 binaries 项
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