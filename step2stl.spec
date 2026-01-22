# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
使用自定义 hook 收集 pythonocc-core
"""

from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
    collect_all,
)
import sys
import os

print("=" * 60)
print("step2stl PyInstaller Build Configuration")
print("=" * 60)

# ==========================================
# 初始化收集列表
# ==========================================
hiddenimports = []
datas = []
binaries = []

# ==========================================
# 辅助函数：安全过滤
# ==========================================
def safe_filter_strings(items):
    """确保返回的列表只包含有效字符串"""
    if not items:
        return []
    return [str(item) for item in items if item and isinstance(item, str)]

def safe_filter_tuples(items):
    """确保返回的列表只包含有效元组"""
    if not items:
        return []
    filtered = []
    for item in items:
        if isinstance(item, tuple) and len(item) >= 2:
            if all(isinstance(x, str) or x is None for x in item):
                filtered.append(item)
    return filtered

# ==========================================
# 收集 numpy
# ==========================================
print("\nCollecting numpy (complete)...")
try:
    numpy_result = collect_all('numpy')
    numpy_hidden = safe_filter_strings(numpy_result[0])
    numpy_bins = safe_filter_tuples(numpy_result[1])
    numpy_datas = safe_filter_tuples(numpy_result[2])
    
    hiddenimports += numpy_hidden
    binaries += numpy_bins
    datas += numpy_datas
    
    print(f"  Hidden imports: {len(numpy_hidden)} modules")
    print(f"  Binaries: {len(numpy_bins)} files")
    print(f"  Data files: {len(numpy_datas)} files")
except Exception as e:
    print(f"  Warning: {e}")
    hiddenimports += [
        'numpy',
        'numpy.core',
        'numpy._core',
        'numpy._core._multiarray_umath',
        'numpy.core._multiarray_umath',
    ]

# ==========================================
# 收集 jaraco
# ==========================================
print("\nCollecting jaraco (complete)...")
try:
    jaraco_result = collect_all('jaraco')
    jaraco_hidden = safe_filter_strings(jaraco_result[0])
    jaraco_datas = safe_filter_tuples(jaraco_result[2])
    
    hiddenimports += jaraco_hidden
    datas += jaraco_datas
    
    print(f"  Hidden imports: {len(jaraco_hidden)} modules")
except Exception as e:
    print(f"  Warning: {e}")
    hiddenimports += ['jaraco', 'jaraco.text', 'jaraco.functools', 'jaraco.context']

# ==========================================
# 标准库模块
# ==========================================
print("\nAdding standard library modules...")
standard_modules = [
    'ipaddress',
    'urllib', 'urllib.parse', 'urllib.request', 'urllib.error',
    'email', 'email.mime', 'email.mime.text',
    'pathlib', 'zipfile', 'argparse',
    'collections', 'collections.abc',
    'warnings', 'traceback', 'gc', 'time', 'os', 'sys', 're', 'json', 'base64', 'io',
]
hiddenimports += standard_modules
print(f"  Added {len(standard_modules)} modules")

# ==========================================
# 收集 OCC - 基础模块
# ==========================================
print("\nCollecting OCC base modules...")
occ_core_modules = [
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
    'OCC.Core.TopoDS', 'OCC.Core.TopAbs', 'OCC.Core.gp',
    'OCC.Core.TopExp', 'OCC.Core.TopTools', 'OCC.Core.BRep',
    'OCC.Core.GeomAbs', 'OCC.Core.Interface', 'OCC.Core.XSControl',
]
hiddenimports += occ_core_modules

# 收集所有 OCC.Core 子模块
try:
    occ_all_modules = collect_submodules('OCC.Core')
    occ_all_modules = safe_filter_strings(occ_all_modules)
    hiddenimports += occ_all_modules
    print(f"  Collected {len(occ_all_modules)} OCC.Core modules")
except:
    pass

# ==========================================
# 收集 trimesh
# ==========================================
print("\nCollecting trimesh...")
try:
    trimesh_modules = collect_submodules('trimesh')
    trimesh_modules = safe_filter_strings(trimesh_modules)
    hiddenimports += trimesh_modules
    print(f"  Collected {len(trimesh_modules)} modules")
except Exception as e:
    print(f"  Warning: {e}")
    hiddenimports += ['trimesh']

# ==========================================
# 最终过滤和去重
# ==========================================
print("\nFinal validation...")
hiddenimports = safe_filter_strings(hiddenimports)
binaries = safe_filter_tuples(binaries)
datas = safe_filter_tuples(datas)
hiddenimports = list(set(hiddenimports))

print(f"  Total hidden imports: {len(hiddenimports)}")
print(f"  Total binaries: {len(binaries)}")
print(f"  Total data files: {len(datas)}")

# ==========================================
# 排除模块
# ==========================================
excludes = [
    'tkinter', '_tkinter',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
    'matplotlib', 'pandas', 'scipy', 'sklearn',
    'tensorflow', 'torch',
    'pytest', 'IPython', 'jupyter', 'notebook',
    'sphinx', 'docutils',
]

# ==========================================
# Analysis 配置
# ==========================================
print("\n" + "=" * 60)
print("Creating Analysis object...")
print("=" * 60)

a = Analysis(
    ['step2stl.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./hooks'],  # 🔧 指定自定义 hook 路径
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)

print("Analysis created successfully")

# 移除 pkg_resources runtime hook
print("\nRemoving problematic runtime hooks...")
original_scripts = len(a.scripts)
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]
print(f"  Removed {original_scripts - len(a.scripts)} hook(s)")

# 过滤二进制文件
print("\nFiltering binaries...")
original_binaries = len(a.binaries)

def should_exclude_binary(name):
    exclude_patterns = ['test', 'example', 'doc', '.pdb', 'tcl', 'tk']
    name_lower = name.lower() if isinstance(name, str) else ''
    return any(pattern in name_lower for pattern in exclude_patterns)

a.binaries = [(name, path, typ) for name, path, typ in a.binaries 
              if not should_exclude_binary(name)]

print(f"  Removed {original_binaries - len(a.binaries)} binaries")
print(f"  Final count: {len(a.binaries)}")

# ==========================================
# PYZ 配置
# ==========================================
print("\nCreating PYZ archive...")
pyz = PYZ(a.pure)

# ==========================================
# EXE 配置
# ==========================================
print("\nCreating EXE configuration...")

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

print("\n" + "=" * 60)
print("Build configuration completed!")
print("=" * 60)