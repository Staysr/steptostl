# -*- coding: utf-8 -*-
"""
PyInstaller hook for pythonocc-core (OCC)
手动收集 OpenCASCADE 的所有动态库和数据文件
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules, get_package_paths
import os
import sys
import glob

# 收集所有 OCC 模块
hiddenimports = collect_submodules('OCC')

# 初始化
datas = []
binaries = []

print("=" * 70)
print("Custom OCC Hook: Collecting pythonocc-core files")
print("=" * 70)

# 获取 OCC 包的路径
try:
    pkg_base, pkg_dir = get_package_paths('OCC')
    print(f"OCC package path: {pkg_dir}")
    
    # 1. 收集所有 .pyd/.so 扩展模块（Python C 扩展）
    if sys.platform.startswith('win'):
        ext_pattern = os.path.join(pkg_dir, '**', '*.pyd')
    else:
        ext_pattern = os.path.join(pkg_dir, '**', '*.so')
    
    ext_files = glob.glob(ext_pattern, recursive=True)
    print(f"\nFound {len(ext_files)} extension modules:")
    for ext_file in ext_files[:10]:  # 只打印前10个
        rel_path = os.path.relpath(ext_file, pkg_dir)
        dest_path = os.path.join('OCC', os.path.dirname(rel_path))
        binaries.append((ext_file, dest_path))
        print(f"  + {rel_path}")
    if len(ext_files) > 10:
        print(f"  ... and {len(ext_files) - 10} more")
    
    # 2. 收集所有 .py 文件
    py_pattern = os.path.join(pkg_dir, '**', '*.py')
    py_files = glob.glob(py_pattern, recursive=True)
    print(f"\nFound {len(py_files)} Python files")
    for py_file in py_files:
        rel_path = os.path.relpath(py_file, pkg_dir)
        dest_path = os.path.join('OCC', os.path.dirname(rel_path))
        datas.append((py_file, dest_path))
    
    # 3. 在 conda 环境中查找 OpenCASCADE 共享库
    if 'CONDA_PREFIX' in os.environ:
        conda_prefix = os.environ['CONDA_PREFIX']
        print(f"\nConda environment: {conda_prefix}")
        
        if sys.platform.startswith('win'):
            # Windows: 在 Library/bin 中查找 DLL
            lib_dirs = [
                os.path.join(conda_prefix, 'Library', 'bin'),
                os.path.join(conda_prefix, 'Library', 'lib'),
            ]
            lib_patterns = ['TK*.dll', 'XSDRAW*.dll', 'freetype*.dll', 'freeimage*.dll']
        else:
            # macOS/Linux: 在 lib 中查找 .dylib/.so
            lib_dirs = [
                os.path.join(conda_prefix, 'lib'),
            ]
            if sys.platform == 'darwin':
                lib_patterns = ['libTK*.dylib', 'libfreeimage*.dylib', 'libfreetype*.dylib']
            else:
                lib_patterns = ['libTK*.so*', 'libfreeimage*.so*', 'libfreetype*.so*']
        
        print(f"\nSearching for OpenCASCADE libraries in:")
        for lib_dir in lib_dirs:
            if os.path.exists(lib_dir):
                print(f"  {lib_dir}")
                for pattern in lib_patterns:
                    lib_files = glob.glob(os.path.join(lib_dir, pattern))
                    for lib_file in lib_files:
                        lib_name = os.path.basename(lib_file)
                        binaries.append((lib_file, '.'))
                        print(f"    + {lib_name}")
        
        print(f"\nTotal OpenCASCADE libraries collected: {len([b for b in binaries if 'TK' in b[0] or 'freetype' in b[0] or 'freeimage' in b[0]])}")
    
    # 4. 收集数据文件（如果有）
    data_dirs = ['Data', 'data', 'resources']
    for data_dir in data_dirs:
        full_data_dir = os.path.join(pkg_dir, data_dir)
        if os.path.exists(full_data_dir):
            print(f"\nCollecting data from: {data_dir}")
            for root, dirs, files in os.walk(full_data_dir):
                for file in files:
                    src = os.path.join(root, file)
                    rel_path = os.path.relpath(root, pkg_dir)
                    dest = os.path.join('OCC', rel_path)
                    datas.append((src, dest))
                    print(f"  + {os.path.relpath(src, pkg_dir)}")

except Exception as e:
    print(f"Warning: Error collecting OCC files: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print(f"OCC Hook Summary:")
print(f"  Hidden imports: {len(hiddenimports)}")
print(f"  Binaries: {len(binaries)}")
print(f"  Data files: {len(datas)}")
print("=" * 70 + "\n")