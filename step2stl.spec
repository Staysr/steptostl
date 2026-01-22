# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
增强版 - 强制包含所有 OCC 依赖
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules
import sys
import os

print("=" * 70)
print("step2stl PyInstaller Build Configuration")
print("=" * 70)

# ==========================================
# 环境检查
# ==========================================
print("\n[Environment Check]")
print(f"Python: {sys.version}")
print(f"Platform: {sys.platform}")
print(f"Python executable: {sys.executable}")

conda_prefix = os.environ.get('CONDA_PREFIX', '')
if conda_prefix:
    print(f"Conda prefix: {conda_prefix}")
else:
    print("WARNING: CONDA_PREFIX not set!")

print()

# ==========================================
# 辅助函数
# ==========================================
def safe_filter_strings(items):
    if not items:
        return []
    return [str(item) for item in items if item and isinstance(item, str)]

def safe_filter_tuples(items):
    if not items:
        return []
    filtered = []
    for item in items:
        if isinstance(item, tuple) and len(item) >= 2:
            if all(isinstance(x, str) or x is None for x in item):
                filtered.append(item)
    return filtered

# ==========================================
# 初始化
# ==========================================
hiddenimports = []
datas = []
binaries = []

# ==========================================
# 收集 numpy
# ==========================================
print("[Collecting numpy]")
try:
    numpy_result = collect_all('numpy')
    hiddenimports += safe_filter_strings(numpy_result[0])
    binaries += safe_filter_tuples(numpy_result[1])
    datas += safe_filter_tuples(numpy_result[2])
    print(f"  ✓ Collected numpy")
except Exception as e:
    print(f"  ⚠ {e}")
    hiddenimports += ['numpy', 'numpy.core', 'numpy._core']

# ==========================================
# 收集 jaraco
# ==========================================
print("\n[Collecting jaraco]")
try:
    jaraco_result = collect_all('jaraco')
    hiddenimports += safe_filter_strings(jaraco_result[0])
    datas += safe_filter_tuples(jaraco_result[2])
    print(f"  ✓ Collected jaraco")
except Exception as e:
    print(f"  ⚠ {e}")
    hiddenimports += ['jaraco', 'jaraco.text', 'jaraco.functools']

# ==========================================
# 标准库
# ==========================================
print("\n[Adding standard library modules]")
hiddenimports += [
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse',
    'collections', 'collections.abc', 'warnings', 'traceback',
]
print(f"  ✓ Added standard modules")

# ==========================================
# 收集 OCC (会使用自定义 hook)
# ==========================================
print("\n[Collecting OCC modules]")
occ_modules = [
    'OCC', 'OCC.Core',
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh',
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib',
]
hiddenimports += occ_modules

try:
    occ_all = collect_submodules('OCC.Core')
    hiddenimports += safe_filter_strings(occ_all)
    print(f"  ✓ Collected {len(occ_all)} OCC.Core modules")
except:
    pass

# ==========================================
# 收集 trimesh
# ==========================================
print("\n[Collecting trimesh]")
try:
    trimesh_modules = collect_submodules('trimesh')
    hiddenimports += safe_filter_strings(trimesh_modules)
    print(f"  ✓ Collected trimesh")
except:
    hiddenimports += ['trimesh']

# ==========================================
# 去重和验证
# ==========================================
hiddenimports = list(set(safe_filter_strings(hiddenimports)))
binaries = safe_filter_tuples(binaries)
datas = safe_filter_tuples(datas)

print(f"\n[Summary Before Analysis]")
print(f"  Hidden imports: {len(hiddenimports)}")
print(f"  Binaries: {len(binaries)}")
print(f"  Data files: {len(datas)}")

# ==========================================
# 排除模块
# ==========================================
excludes = [
    'tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 
    'pandas', 'scipy', 'pytest', 'IPython',
]

# ==========================================
# Analysis
# ==========================================
print("\n" + "=" * 70)
print("Creating Analysis...")
print("=" * 70 + "\n")

a = Analysis(
    ['step2stl.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./hooks'],  # 使用自定义 hook
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# 移除 pkg_resources hook
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]

# 过滤不需要的二进制
def should_keep(name):
    if not isinstance(name, str):
        return True
    name_lower = name.lower()
    exclude = ['test', 'example', 'doc', '.pdb']
    return not any(e in name_lower for e in exclude)

a.binaries = [(n, p, t) for n, p, t in a.binaries if should_keep(n)]

print(f"[Final Analysis Summary]")
print(f"  Scripts: {len(a.scripts)}")
print(f"  Binaries: {len(a.binaries)}")
print(f"  Data files: {len(a.datas)}")

# 检查是否包含 TK 库
tk_libs = [b[0] for b in a.binaries if 'TK' in b[0] or 'tk' in b[0].lower()]
if tk_libs:
    print(f"  ✓ Found {len(tk_libs)} OpenCASCADE TK libraries")
else:
    print(f"  ⚠️  WARNING: No TK libraries found in binaries!")

print()

# ==========================================
# PYZ & EXE
# ==========================================
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='step2stl',
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

print("=" * 70)
print("Build configuration completed!")
print("=" * 70)