# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
优化目标：减小体积、提高兼容性
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs
import sys

# ==========================================
# 收集必要模块
# ==========================================
hiddenimports = []

# 🔧 修复：Windows 必须显式包含这些标准库模块
hiddenimports += [
    'ipaddress',
    'urllib',
    'urllib.parse',
    'pathlib',
    'email',
    'email.mime',
    'zipfile',
    'argparse',
    'time',
    'gc',
    'warnings',
    'traceback',
]

# OCC 核心模块（只收集必要的）
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
datas += collect_data_files('OCC', include_py_files=True)

binaries = []
binaries += collect_dynamic_libs('OCC')

# ==========================================
# 排除不需要的模块（减小体积）
# ==========================================
excludes = [
    # GUI 相关
    'tkinter', '_tkinter', 'tcl', 'tk',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'wx', 'gtk',
    
    # 科学计算（不需要）
    'matplotlib', 'PIL', 'pillow',
    'pandas', 'scipy', 'sklearn', 'scikit-learn',
    
    # Jupyter 相关
    'IPython', 'jupyter', 'notebook', 'jupyterlab',
    
    # 网络相关
    'tornado', 'zmq', 'jinja2', 'flask', 'django',
    
    # 测试相关
    'pytest', 'nose',
    
    # 其他
    'setuptools', 'pkg_resources',
    'xmlrpc',
    'pydoc', 'doctest',
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
    # 🔧 新增：Windows 兼容性优化
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)

# ==========================================
# 过滤不必要的二进制文件（进一步减小体积）
# ==========================================
def filter_binaries(binaries):
    filtered = []
    exclude_patterns = [
        'test', 'tests', 'testing',
        'example', 'examples',
        'doc', 'docs',
        '.pdb',  # Windows 调试符号
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
    strip=True if sys.platform != 'win32' else False,
    upx=False,  # 🔧 建议：禁用 UPX（避免兼容性问题）
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