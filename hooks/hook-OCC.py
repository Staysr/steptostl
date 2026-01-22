# -*- coding: utf-8 -*-
"""
PyInstaller hook for pythonocc-core
强制收集所有 OpenCASCADE 动态库和依赖
"""

from PyInstaller.utils.hooks import collect_submodules, get_package_paths
from PyInstaller.compat import is_win, is_darwin, is_linux
import os
import sys
import glob

print("\n" + "=" * 70)
print("CUSTOM OCC HOOK: Collecting pythonocc-core dependencies")
print("=" * 70)

# ==========================================
# 1. 收集所有 Python 模块
# ==========================================
hiddenimports = collect_submodules('OCC')
print(f"[1/4] Collected {len(hiddenimports)} OCC Python modules")

# ==========================================
# 2. 初始化
# ==========================================
datas = []
binaries = []

# ==========================================
# 3. 获取 OCC 包路径
# ==========================================
try:
    pkg_base, occ_pkg_dir = get_package_paths('OCC')
    print(f"[2/4] OCC package location: {occ_pkg_dir}")
except Exception as e:
    print(f"ERROR: Cannot locate OCC package: {e}")
    occ_pkg_dir = None

# ==========================================
# 4. 收集 OCC Python 扩展模块 (.pyd/.so)
# ==========================================
if occ_pkg_dir and os.path.exists(occ_pkg_dir):
    print(f"[3/4] Collecting OCC extension modules...")
    
    # 查找所有扩展文件
    if is_win:
        ext_pattern = '*.pyd'
    else:
        ext_pattern = '*.so'
    
    ext_files = []
    for root, dirs, files in os.walk(occ_pkg_dir):
        for file in files:
            if file.endswith(('.pyd', '.so', '.dylib')):
                src_path = os.path.join(root, file)
                rel_dir = os.path.relpath(root, occ_pkg_dir)
                
                # 目标路径：保持 OCC 的目录结构
                if rel_dir == '.':
                    dest_dir = 'OCC'
                else:
                    dest_dir = os.path.join('OCC', rel_dir)
                
                binaries.append((src_path, dest_dir))
                ext_files.append(file)
    
    print(f"    Found {len(ext_files)} extension files")
    for f in ext_files[:5]:
        print(f"      - {f}")
    if len(ext_files) > 5:
        print(f"      ... and {len(ext_files) - 5} more")

# ==========================================
# 5. 收集 OpenCASCADE 共享库（关键！）
# ==========================================
print(f"[4/4] Collecting OpenCASCADE shared libraries...")

conda_prefix = os.environ.get('CONDA_PREFIX', '')
if not conda_prefix:
    # 尝试从 Python 路径推断
    python_exe = sys.executable
    if 'conda' in python_exe or 'miniconda' in python_exe.lower():
        conda_prefix = os.path.dirname(os.path.dirname(python_exe))

if conda_prefix and os.path.exists(conda_prefix):
    print(f"    Conda environment: {conda_prefix}")
    
    lib_dirs = []
    lib_patterns = []
    
    if is_win:
        # Windows: Library/bin 目录
        lib_dirs = [
            os.path.join(conda_prefix, 'Library', 'bin'),
            os.path.join(conda_prefix, 'Library', 'lib'),
            os.path.join(conda_prefix, 'bin'),
        ]
        # OpenCASCADE 库前缀
        lib_patterns = [
            'TK*.dll',           # OpenCASCADE 核心库
            'freetype*.dll',     # 字体渲染
            'freeimage*.dll',    # 图像处理
            'tbb*.dll',          # Intel Threading Building Blocks
            'msvcp*.dll',        # MSVC 运行时
            'vcruntime*.dll',    # VC 运行时
        ]
    elif is_darwin:
        # macOS: lib 目录
        lib_dirs = [
            os.path.join(conda_prefix, 'lib'),
        ]
        lib_patterns = [
            'libTK*.dylib',
            'libTK*.*.dylib',
            'libfreeimage*.dylib',
            'libfreetype*.dylib',
            'libtbb*.dylib',
        ]
    else:
        # Linux: lib 目录
        lib_dirs = [
            os.path.join(conda_prefix, 'lib'),
            os.path.join(conda_prefix, 'lib64'),
        ]
        lib_patterns = [
            'libTK*.so*',
            'libfreeimage*.so*',
            'libfreetype*.so*',
            'libtbb*.so*',
        ]
    
    collected_libs = []
    for lib_dir in lib_dirs:
        if not os.path.exists(lib_dir):
            continue
        
        print(f"    Searching in: {lib_dir}")
        
        for pattern in lib_patterns:
            lib_files = glob.glob(os.path.join(lib_dir, pattern))
            for lib_file in lib_files:
                lib_name = os.path.basename(lib_file)
                
                # 跳过符号链接（在 macOS/Linux 上）
                if os.path.islink(lib_file) and not is_win:
                    continue
                
                # 添加到根目录（与主程序同级）
                binaries.append((lib_file, '.'))
                collected_libs.append(lib_name)
    
    print(f"    Collected {len(collected_libs)} shared libraries:")
    # 按类型分组显示
    tk_libs = [l for l in collected_libs if 'TK' in l or 'tk' in l.lower()]
    other_libs = [l for l in collected_libs if 'TK' not in l and 'tk' not in l.lower()]
    
    if tk_libs:
        print(f"      OpenCASCADE (TK*): {len(tk_libs)} files")
        for lib in tk_libs[:3]:
            print(f"        - {lib}")
        if len(tk_libs) > 3:
            print(f"        ... and {len(tk_libs) - 3} more")
    
    if other_libs:
        print(f"      Dependencies: {len(other_libs)} files")
        for lib in other_libs[:3]:
            print(f"        - {lib}")
        if len(other_libs) > 3:
            print(f"        ... and {len(other_libs) - 3} more")
    
    if not collected_libs:
        print("    WARNING: No OpenCASCADE libraries found!")
        print(f"    Please verify conda environment: {conda_prefix}")
else:
    print("    WARNING: CONDA_PREFIX not found!")
    print("    OpenCASCADE libraries may not be included!")

# ==========================================
# 6. 收集 OCC 数据文件
# ==========================================
if occ_pkg_dir and os.path.exists(occ_pkg_dir):
    for root, dirs, files in os.walk(occ_pkg_dir):
        for file in files:
            if file.endswith('.py'):
                src = os.path.join(root, file)
                rel_path = os.path.relpath(root, occ_pkg_dir)
                if rel_path == '.':
                    dest = 'OCC'
                else:
                    dest = os.path.join('OCC', rel_path)
                datas.append((src, dest))

# ==========================================
# 汇总
# ==========================================
print("\n" + "=" * 70)
print("OCC HOOK SUMMARY:")
print(f"  Hidden imports: {len(hiddenimports)}")
print(f"  Binary files:   {len(binaries)}")
print(f"  Data files:     {len(datas)}")
print("=" * 70 + "\n")

# 验证关键库是否被收集
tk_count = len([b for b in binaries if 'TK' in b[0] or 'tk' in b[0].lower()])
if tk_count == 0:
    print("⚠️  WARNING: No TK* libraries found!")
    print("   The built executable may fail with 'pythonocc-core not installed' error")
    print("   Please check your conda environment setup.\n")
else:
    print(f"✓  Success: {tk_count} OpenCASCADE TK libraries will be included\n")