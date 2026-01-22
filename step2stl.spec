# -*- mode: python ; coding: utf-8 -*-
"""
step2stl PyInstaller 打包配置
修复 Windows 平台 numpy 1.26.4 和 jaraco 打包问题
支持 Windows/macOS 跨平台构建
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
print("🚀 step2stl PyInstaller Build Configuration")
print("=" * 60)

# ==========================================
# 初始化收集列表
# ==========================================
hiddenimports = []
datas = []
binaries = []

# ==========================================
# 🔧 关键修复 1：完整收集 numpy
# ==========================================
print("\n📦 Collecting numpy (complete)...")
try:
    numpy_result = collect_all('numpy')
    hiddenimports += numpy_result[0]
    binaries += numpy_result[1]
    datas += numpy_result[2]
    print(f"  ✓ Hidden imports: {len(numpy_result[0])} modules")
    print(f"  ✓ Binaries: {len(numpy_result[1])} files")
    print(f"  ✓ Data files: {len(numpy_result[2])} files")
except Exception as e:
    print(f"  ⚠ Warning: {e}")
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
# 🔧 关键修复 2：完整收集 jaraco
# ==========================================
print("\n📦 Collecting jaraco (complete)...")
try:
    jaraco_result = collect_all('jaraco')
    hiddenimports += jaraco_result[0]
    binaries += jaraco_result[1]
    datas += jaraco_result[2]
    print(f"  ✓ Hidden imports: {len(jaraco_result[0])} modules")
    print(f"  ✓ Data files: {len(jaraco_result[2])} files")
except Exception as e:
    print(f"  ⚠ Warning: {e}")
    # 备用方案：手动添加核心模块
    hiddenimports += [
        'jaraco',
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
        'jaraco.classes',
    ]

# ==========================================
# 🔧 关键修复 3：标准库模块（解决 ipaddress 错误）
# ==========================================
print("\n📦 Adding standard library modules...")
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
print(f"  ✓ Added {len(standard_modules)} standard library modules")

# ==========================================
# 收集 OCC (pythonocc-core) 模块
# ==========================================
print("\n📦 Collecting OCC modules...")
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
print(f"  ✓ Added {len(occ_modules)} OCC modules")

# 收集 OCC 数据文件和动态库
try:
    occ_datas = collect_data_files('OCC', include_py_files=True)
    datas += occ_datas
    print(f"  ✓ Collected {len(occ_datas)} OCC data files")
except Exception as e:
    print(f"  ⚠ Warning: Failed to collect OCC data files: {e}")

try:
    occ_binaries = collect_dynamic_libs('OCC')
    binaries += occ_binaries
    print(f"  ✓ Collected {len(occ_binaries)} OCC binaries")
except Exception as e:
    print(f"  ⚠ Warning: Failed to collect OCC binaries: {e}")

# ==========================================
# 收集 trimesh 模块
# ==========================================
print("\n📦 Collecting trimesh modules...")
try:
    trimesh_modules = collect_submodules('trimesh')
    hiddenimports += trimesh_modules
    print(f"  ✓ Collected {len(trimesh_modules)} trimesh modules")
except Exception as e:
    print(f"  ⚠ Warning: {e}")
    hiddenimports += ['trimesh']

# 收集 trimesh 数据文件
try:
    trimesh_datas = collect_data_files('trimesh')
    datas += trimesh_datas
    print(f"  ✓ Collected {len(trimesh_datas)} trimesh data files")
except Exception as e:
    print(f"  ⚠ Warning: Failed to collect trimesh data: {e}")

# ==========================================
# 排除不需要的模块（减小体积）
# ==========================================
excludes = [
    # GUI 框架
    'tkinter',
    '_tkinter',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'wx',
    
    # 科学计算（项目不需要的）
    'matplotlib',
    'pandas',
    'scipy',
    'sklearn',
    'tensorflow',
    'torch',
    
    # 开发工具
    'pytest',
    'IPython',
    'jupyter',
    'notebook',
    
    # 文档生成
    'sphinx',
    'docutils',
]

print(f"\n🚫 Excluding {len(excludes)} unnecessary modules")

# ==========================================
# 过滤二进制文件（减小体积）
# ==========================================
def filter_binaries(binaries_list):
    """过滤测试和示例相关的二进制文件"""
    filtered = []
    exclude_patterns = [
        'test', 'tests', 'testing',
        'example', 'examples',
        'doc', 'docs',
        '.pdb',  # Windows 调试符号
        'tcl', 'tk',  # Tkinter 相关
    ]
    
    for item in binaries_list:
        if isinstance(item, tuple) and len(item) >= 2:
            name = item[0]
            name_lower = name.lower() if isinstance(name, str) else ''
            
            # 检查是否包含排除模式
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
print("🔨 Creating Analysis object...")
print("=" * 60)

a = Analysis(
    ['step2stl.py'],                    # 主脚本
    pathex=[],                          # 额外搜索路径
    binaries=binaries,                  # 二进制文件
    datas=datas,                        # 数据文件
    hiddenimports=hiddenimports,        # 隐藏导入
    hookspath=[],                       # 自定义 hook 路径
    hooksconfig={},                     # Hook 配置
    runtime_hooks=[],                   # 🔧 清空 runtime hooks
    excludes=excludes,                  # 排除的模块
    noarchive=False,                    # 是否不创建归档
    win_no_prefer_redirects=False,     # Windows 特定
    win_private_assemblies=False,      # Windows 特定
)

print(f"  ✓ Total hidden imports: {len(hiddenimports)}")
print(f"  ✓ Total data files: {len(datas)}")
print(f"  ✓ Total binaries (before filter): {len(binaries)}")

# ==========================================
# 🔧 关键修复 4：移除 pkg_resources runtime hook
# ==========================================
print("\n🔧 Removing problematic runtime hooks...")
original_scripts = len(a.scripts)
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]]
removed_scripts = original_scripts - len(a.scripts)
print(f"  ✓ Removed {removed_scripts} problematic runtime hook(s)")

# ==========================================
# 过滤二进制文件
# ==========================================
print("\n🔧 Filtering binaries...")
original_binaries = len(a.binaries)
a.binaries = filter_binaries(a.binaries)
removed_binaries = original_binaries - len(a.binaries)
print(f"  ✓ Removed {removed_binaries} unnecessary binaries")
print(f"  ✓ Final binaries count: {len(a.binaries)}")

# ==========================================
# PYZ 配置（Python 字节码归档）
# ==========================================
print("\n📦 Creating PYZ archive...")
pyz = PYZ(a.pure)
print("  ✓ PYZ archive created")

# ==========================================
# EXE 配置（最终可执行文件）
# ==========================================
print("\n🎯 Creating EXE configuration...")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='step2stl',                           # 输出文件名
    debug=False,                               # 调试模式（生产环境关闭）
    bootloader_ignore_signals=False,
    strip=False,                               # 不剥离符号（保持兼容性）
    upx=False,                                 # 🔧 关闭 UPX 压缩（避免问题）
    upx_exclude=[],
    runtime_tmpdir=None,                       # 运行时临时目录
    console=True,                              # 显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,                      # macOS 参数模拟
    target_arch=None,                          # 目标架构（自动检测）
    codesign_identity=None,                    # macOS 代码签名
    entitlements_file=None,                    # macOS 权限文件
    icon=None,                                 # 图标文件（可选）
)

print("  ✓ EXE configuration created")
print("\n" + "=" * 60)
print("✅ Build configuration completed!")
print("=" * 60)
print("\n💡 Tips:")
print("  - Run: pyinstaller step2stl.spec")
print("  - Output: dist/step2stl.exe (Windows) or dist/step2stl (macOS)")
print("  - Test: dist/step2stl --help")
print("=" * 60 + "\n")