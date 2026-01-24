# -*- mode: python ; coding: utf-8 -*- 
""" 
step2stl PyInstaller Spec (Windows 7 + Mac Fixed)
""" 

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ==========================================
# 辅助函数
# ==========================================
def _safe_print(msg): 
    try: print(msg) 
    except: pass

def validate_tuples(tuple_list, name="data"):
    """验证 binaries/datas 格式，确保是 (str, str)"""
    if not tuple_list: return []
    cleaned = []
    seen = set()
    for item in tuple_list:
        try:
            # 必须是元组或列表，且长度为2
            if not isinstance(item, (list, tuple)) or len(item) != 2: continue
            src, dest = item
            # src 和 dest 必须是字符串
            if not isinstance(src, str) or not isinstance(dest, str): continue
            
            # 检查源文件是否存在
            if not os.path.exists(src): continue
            
            # 去重
            key = (os.path.basename(src), dest)
            if key in seen: continue
            seen.add(key)
            cleaned.append((src, dest))
        except: continue
    return cleaned

# 🔧 新增：清洗 hiddenimports 的函数，专门修复 TypeError
def clean_imports(import_list):
    """确保列表中只有非空字符串"""
    if not import_list: return []
    clean = []
    for item in import_list:
        # 剔除 None, 剔除空字符串, 剔除非字符串类型
        if item and isinstance(item, str) and item.strip():
            clean.append(item)
    return list(set(clean))

_safe_print("=" * 70) 
_safe_print("step2stl Build Config (Cross-Platform Fixed)") 
_safe_print("=" * 70) 

# ==========================================
# 1. 定位 Conda 环境
# ==========================================
conda_prefix = os.environ.get('CONDA_PREFIX') 
if not conda_prefix: 
    try: 
        if 'conda' in sys.executable.lower(): 
            conda_prefix = os.path.dirname(os.path.dirname(sys.executable)) 
    except: pass

if conda_prefix:
    _safe_print(f"Conda Prefix: {conda_prefix}")
else:
    _safe_print("WARNING: Conda prefix not found!")

# ==========================================
# 2. 初始化
# ==========================================
hiddenimports = [] 
datas = [] 
binaries = [] 
pathex = [] 

# ==========================================
# 3. 核心 DLL 收集 (仅 Windows 执行)
# ==========================================
# 只有在 Windows 平台才执行这个 Win7 修复逻辑
if sys.platform == 'win32' and conda_prefix: 
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin') 
    conda_bin = os.path.join(conda_prefix, 'bin') 
    
    # 确保这些路径本身存在且是字符串
    if os.path.exists(lib_bin): pathex.append(lib_bin)
    if os.path.exists(conda_bin): pathex.append(conda_bin)
    
    _safe_print("\n[Collecting DLLs - Win7 Force Mode]") 
    
    dll_patterns = [ 
        'TK*.dll', 'tbb*.dll', 'freeimage*.dll', 'freetype*.dll',   
        'zlib*.dll', 'sqlite3.dll',
        # Win7 关键系统库实体文件
        'ucrtbase.dll', 'vcruntime140*.dll', 'msvcp140*.dll', 
        'concrt140.dll', 'vcomp140.dll', 'api-ms-win-*.dll' 
    ] 
    
    count = 0
    search_paths = [p for p in [lib_bin, conda_bin] if os.path.exists(p)]
    
    for s_dir in search_paths: 
        for pattern in dll_patterns: 
            found = glob.glob(os.path.join(s_dir, pattern)) 
            for dll in found: 
                if dll.lower().endswith('d.dll') and not dll.lower().endswith('bnd.dll'): continue
                binaries.append((dll, '.')) 
                count += 1
                
    _safe_print(f"  Collected {count} Critical DLLs from Conda.") 

# ==========================================
# 4. 依赖处理 (容易出问题的部分)
# ==========================================
# Numpy
try: 
    np_hidden, np_bin, np_data = collect_all('numpy') 
    # 可能会收集到 None，这里只 extend 如果它们是有效的列表
    if np_hidden: hiddenimports.extend(np_hidden)
    
    # 过滤掉系统路径的二进制文件 (Windows only)
    if np_bin:
        for b in np_bin:
            if sys.platform == 'win32' and 'windows\\system32' in str(b[0]).lower(): continue
            binaries.append(b)
            
    if np_data: datas.extend(np_data)
except Exception as e: 
    _safe_print(f"Warning collecting numpy: {e}")
    hiddenimports.extend(['numpy', 'numpy.core']) 

# Trimesh
try: 
    tm_sub = collect_submodules('trimesh')
    if tm_sub: hiddenimports.extend(tm_sub)
except: 
    hiddenimports.append('trimesh') 

hiddenimports.extend(['jaraco.text', 'jaraco.functools', 'jaraco.context']) 

# OCC Modules
hiddenimports.extend([ 
    'OCC', 'OCC.Core', 
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh', 
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib', 
    'OCC.Core.TCollection', 'OCC.Core.Standard', 'OCC.Core.TopoDS',
    'OCC.Core.STEPCAFControl', 'OCC.Core.XCAFDoc', 
    'OCC.Core.TDocStd', 'OCC.Core.TDF', 'OCC.Core.TDataStd',
    'OCC.Core.Quantity', 'OCC.Core.TopAbs'
]) 

# ==========================================
# 5. 关键修复：清洗数据
# ==========================================
_safe_print("Cleaning build lists...")

# 修复 TypeError: expected string 错误
# 强制过滤掉所有不是字符串的项
hiddenimports = clean_imports(hiddenimports)
pathex = clean_imports(pathex)

# 验证二进制和数据文件
binaries = validate_tuples(binaries, "binary")
datas = validate_tuples(datas, "data")

_safe_print(f"Final counts -> HiddenImports: {len(hiddenimports)}, Binaries: {len(binaries)}")

# ==========================================
# 6. Analysis
# ==========================================
block_cipher = None

a = Analysis( 
    ['step2stl.py'], 
    pathex=pathex, 
    binaries=binaries, 
    datas=datas, 
    hiddenimports=hiddenimports, 
    hookspath=['./hooks'], 
    hooksconfig={}, 
    runtime_hooks=['./rthook_win7.py', './rthook_encoding.py'], 
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython'], 
    win_no_prefer_redirects=False, 
    win_private_assemblies=False, 
    cipher=block_cipher, 
    noarchive=False, 
) 

# Windows 特有的清理：移除 System32 的桩文件
if sys.platform == 'win32':
    new_binaries = []
    for b in a.binaries:
        src_lower = b[0].lower()
        if 'system32' in src_lower and ('api-ms-win' in src_lower or 'ucrtbase' in src_lower):
            continue
        new_binaries.append(b)
    a.binaries = new_binaries

a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]] 

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher) 

exe = EXE( 
    pyz, 
    a.scripts, 
    [], 
    exclude_binaries=True,
    name='step2stl', 
    debug=False, 
    bootloader_ignore_signals=False, 
    strip=False, 
    upx=False, 
    console=True, 
    disable_windowed_traceback=False, 
    argv_emulation=False, 
    target_arch=None, 
    codesign_identity=None, 
    entitlements_file=None, 
) 

coll = COLLECT( 
    exe, 
    a.binaries, 
    a.zipfiles, 
    a.datas, 
    strip=False, 
    upx=False, 
    upx_exclude=[], 
    name='step2stl',
)