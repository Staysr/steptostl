# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
修复 Windows/macOS 跨平台兼容性问题
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
# 辅助函数：安全过滤字符串列表
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
            # 确保元组中的字符串有效
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
    # 备用方案：手动添加关键模块
    hiddenimports += [
        'numpy',
        'numpy.core',
        'numpy._core',
        'numpy._core._multiarray_tests',
        'numpy._core._multiarray_umath',
        'numpy._core.multiarray',
        'numpy._core._methods',
        'numpy.core._multiarray_umath',
        'numpy.core.multiarray',
    ]

# ==========================================
# 收集 jaraco
# ==========================================
print("\nCollecting jaraco (complete)...")
try:
    jaraco_result = collect_all('jaraco')
    jaraco_hidden = safe_filter_strings(jaraco_result[0])
    jaraco_bins = safe_filter_tuples(jaraco_result[1])
    jaraco_datas = safe_filter_tuples(jaraco_result[2])
    
    hiddenimports += jaraco_hidden
    binaries += jaraco_bins
    datas += jaraco_datas
    
    print(f"  Hidden imports: {len(jaraco_hidden)} modules")
    print(f"  Data files: {len(jaraco_datas)} files")
except Exception as e:
    print(f"  Warning: {e}")
    # 备用方案
    hiddenimports += [
        'jaraco',
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
        'jaraco.classes',
    ]

# ==========================================
# 标准库模块
# ==========================================
print("\nAdding standard library modules...")
standard_modules = [
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
    'json',
    'base64',
    'io',
]
hiddenimports += standard_modules
print(f"  Added {len(standard_modules)} standard library modules")

# ==========================================
# 收集 OCC 模块
# ==========================================
print("\nCollecting OCC modules...")
occ_modules = [
    'OCC',
    'OCC.Core',
    'OCC.Core.STEPControl',
    'OCC.Core.StlAPI',
    'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect',
    'OCC.Core.Bnd',
    'OCC.Core.BRepBndLib',
    'OCC.Core.TopoDS',
    'OCC.Core.TopAbs',
    'OCC.Core.gp',
    'OCC.Core.TopExp',
    'OCC.Core.TopTools',
    'OCC.Core.BRep',
    'OCC.Core.GeomAbs',
    'OCC.Core.Interface',
    'OCC.Core.XSControl',
]
hiddenimports += occ_modules
print(f"  Added {len(occ_modules)} OCC modules")

# 收集 OCC 数据文件和动态库
try:
    occ_datas = collect_data_files('OCC', include_py_files=True)
    occ_datas = safe_filter_tuples(occ_datas)
    datas += occ_datas
    print(f"  Collected {len(occ_datas)} OCC data files")
except Exception as e:
    print(f"  Warning: Failed to collect OCC data files: {e}")

try:
    occ_binaries = collect_dynamic_libs('OCC')
    occ_binaries = safe_filter_tuples(occ_binaries)
    binaries += occ_binaries
    print(f"  Collected {len(occ_binaries)} OCC binaries")
except Exception as e:
    print(f"  Warning: Failed to collect OCC binaries: {e}")

# ==========================================
# 收集 trimesh 模块
# ==========================================
print("\nCollecting trimesh modules...")
try:
    trimesh_modules = collect_submodules('trimesh')
    trimesh_modules = safe_filter_strings(trimesh_modules)
    hiddenimports += trimesh_modules
    print(f"  Collected {len(trimesh_modules)} trimesh modules")
except Exception as e:
    print(f"  Warning: {e}")
    hiddenimports += ['trimesh']

# 收集 trimesh 数据文件
try:
    trimesh_datas = collect_data_files('trimesh')
    trimesh_datas = safe_filter_tuples(trimesh_datas)
    datas += trimesh_datas
    print(f"  Collected {len(trimesh_datas)} trimesh data files")
except Exception as e:
    print(f"  Warning: Failed to collect trimesh data: {e}")

# ==========================================
# 最终过滤：确保所有列表有效
# ==========================================
print("\nFinal validation...")
hiddenimports = safe_filter_strings(hiddenimports)
binaries = safe_filter_tuples(binaries)
datas = safe_filter_tuples(datas)

# 去重
hiddenimports = list(set(hiddenimports))

print(f"  Total hidden imports: {len(hiddenimports)}")
print(f"  Total binaries: {len(binaries)}")
print(f"  Total data files: {len(datas)}")

# ==========================================
# 排除不需要的模块
# ==========================================
excludes = [
    'tkinter',
    '_tkinter',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'wx',
    'matplotlib',
    'pandas',
    'scipy',
    'sklearn',
    'tensorflow',
    'torch',
    'pytest',
    'IPython',
    'jupyter',
    'notebook',
    'sphinx',
    'docutils',
]

print(f"\nExcluding {len(excludes)} unnecessary modules")

# ==========================================
# 过滤二进制文件
# ==========================================
def filter_binaries(binaries_list):
    """过滤测试和示例相关的二进制文件"""
    filtered = []
    exclude_patterns = [
        'test', 'tests', 'testing',
        'example', 'examples',
        'doc', 'docs',
        '.pdb',
        'tcl', 'tk',
    ]
    
    for item in binaries_list:
        if isinstance(item, tuple) and len(item) >= 2:
            name = item[0]
            if isinstance(name, str):
                name_lower = name.lower()
                should_exclude = any(pattern in name_lower for pattern in exclude_patterns)
                if not should_exclude:
                    filtered.append(item)
        else:
            filtered.append(item)
    
    return filtered

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
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)

print(f"Analysis created successfully")

# ==========================================
# 移除 pkg_resources runtime hook
# ==========================================
print("\nRemoving problematic runtime hooks...")
original_scripts = len(a.scripts)
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]
removed_scripts = original_scripts - len(a.scripts)
print(f"  Removed {removed_scripts} problematic runtime hook(s)")

# ==========================================
# 过滤二进制文件
# ==========================================
print("\nFiltering binaries...")
original_binaries = len(a.binaries)
a.binaries = filter_binaries(a.binaries)
removed_binaries = original_binaries - len(a.binaries)
print(f"  Removed {removed_binaries} unnecessary binaries")
print(f"  Final binaries count: {len(a.binaries)}")

# ==========================================
# PYZ 配置
# ==========================================
print("\nCreating PYZ archive...")
pyz = PYZ(a.pure)
print("  PYZ archive created")

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

print("  EXE configuration created")
print("\n" + "=" * 60)
print("Build configuration completed!")
print("=" * 60)
print("\nTips:")
print("  - Run: pyinstaller step2stl.spec")
print("  - Output: dist/step2stl.exe (Windows) or dist/step2stl (macOS)")
print("  - Test: dist/step2stl --help")
print("=" * 60 + "\n")