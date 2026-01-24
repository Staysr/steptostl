# -*- mode: python ; coding: utf-8 -*- 
""" 
step2stl PyInstaller Spec (OneDir Mode for Win7 Stability) 
""" 

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ==========================================
# 1. Helper Functions
# ==========================================
def _safe_print(msg): 
    try: 
        print(msg) 
    except: 
        pass

def sanitize_imports(raw_list): 
    clean = [] 
    if not raw_list: return clean
    for item in raw_list: 
        if item and isinstance(item, str): 
            clean.append(item) 
    return list(set(clean)) 

# ==========================================
# 🔧 新增：数据格式验证函数
# ==========================================
def validate_tuples(tuple_list, name="data"):
    """验证并清理 binaries/datas 列表格式"""
    if not tuple_list:
        return []
    
    cleaned = []
    for item in tuple_list:
        try:
            # 必须是元组或列表
            if not isinstance(item, (tuple, list)):
                _safe_print(f"[WARNING] Skipping invalid {name} item (not tuple/list): {type(item)}")
                continue
            
            # 必须是2元素
            if len(item) != 2:
                _safe_print(f"[WARNING] Skipping invalid {name} item (length={len(item)}): {item}")
                continue
            
            src, dest = item
            
            # src 必须是字符串
            if not isinstance(src, str):
                _safe_print(f"[WARNING] Skipping {name} with invalid src type: {type(src)}")
                continue
            
            # dest 必须是字符串
            if not isinstance(dest, str):
                _safe_print(f"[WARNING] Skipping {name} with invalid dest type: {type(dest)}")
                continue
            
            # src 必须存在（对于文件）
            if not os.path.exists(src):
                _safe_print(f"[WARNING] Skipping missing {name} file: {src}")
                continue
            
            cleaned.append((src, dest))
            
        except Exception as e:
            _safe_print(f"[ERROR] Failed to validate {name} item: {e}")
            continue
    
    return cleaned

_safe_print("=" * 70) 
_safe_print("step2stl Build Config (OneDir / Win7 Fix)") 
_safe_print("=" * 70) 

# ==========================================
# 2. Environment
# ==========================================
conda_prefix = os.environ.get('CONDA_PREFIX') 
if not conda_prefix: 
    try: 
        if 'conda' in sys.executable.lower(): 
            conda_prefix = os.path.dirname(os.path.dirname(sys.executable)) 
    except: 
        pass

# ==========================================
# 3. Init
# ==========================================
hiddenimports = [] 
datas = [] 
binaries = [] 
pathex = [] 

# ==========================================
# 4. Critical DLL Collection
# ==========================================
if sys.platform == 'win32' and conda_prefix: 
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin') 
    conda_bin = os.path.join(conda_prefix, 'bin') 
    search_dirs = [lib_bin, conda_bin] 
    
    for d in search_dirs: 
        if os.path.exists(d): 
            pathex.append(d) 
    
    _safe_print("\n[Collecting DLLs for Folder Mode]") 
    
    # 收集核心 DLL
    dll_patterns = [ 
        'TK*.dll',         # OCC Core
        'tbb*.dll',        # TBB (关键!) 
        'freeimage*.dll', 
        'freetype*.dll',   
        'gl*.dll', 'opengl*.dll', 
        'mkl_*.dll', 'libopenblas*.dll', 'libiomp5md.dll', # Numpy
        'api-ms-win-*.dll', # UCRT
        'ucrtbase.dll', 
        'vcruntime*.dll', 
        'msvcp*.dll', 
        'concrt*.dll', 
        'zlib*.dll', 
        'sqlite3.dll' 
    ] 
    
    count = 0
    for s_dir in search_dirs: 
        if not os.path.exists(s_dir): continue
        for pattern in dll_patterns: 
            found = glob.glob(os.path.join(s_dir, pattern)) 
            for dll in found: 
                # 排除 debug 和 python dll
                if dll.lower().endswith('d.dll') and not dll.lower().endswith('bnd.dll'): continue
                if 'python3.dll' in dll.lower() or 'python38.dll' in dll.lower(): continue
                
                binaries.append((dll, '.')) 
                count += 1
    _safe_print(f"  Collected {count} DLLs.") 

# ==========================================
# 5. Dependencies
# ==========================================
# Numpy
try: 
    _safe_print("\n[Collecting Numpy dependencies]")
    np_hidden, np_bin, np_data = collect_all('numpy') 
    
    # 🔧 关键修复：验证格式
    _safe_print(f"  Raw: hiddenimports={len(np_hidden)}, binaries={len(np_bin)}, datas={len(np_data)}")
    
    hiddenimports.extend(np_hidden if np_hidden else [])
    
    # 验证并清理 numpy binaries
    if np_bin:
        np_bin_clean = validate_tuples(np_bin, "numpy binary")
        binaries.extend(np_bin_clean)
        _safe_print(f"  Numpy binaries: {len(np_bin)} -> {len(np_bin_clean)} (cleaned)")
    
    # 验证并清理 numpy datas
    if np_data:
        np_data_clean = validate_tuples(np_data, "numpy data")
        datas.extend(np_data_clean)
        _safe_print(f"  Numpy datas: {len(np_data)} -> {len(np_data_clean)} (cleaned)")
        
except Exception as e:
    _safe_print(f"[WARNING] collect_all('numpy') failed: {e}")
    hiddenimports.extend(['numpy', 'numpy.core']) 

# Trimesh & Jaraco
try: 
    tm_hidden = collect_submodules('trimesh') 
    hiddenimports.extend(tm_hidden) 
except: 
    hiddenimports.append('trimesh') 

hiddenimports.extend(['jaraco.text', 'jaraco.functools', 'jaraco.context']) 

# OCC
hiddenimports.extend([ 
    'OCC', 'OCC.Core', 
    'OCC.Core.STEPControl', 'OCC.Core.StlAPI', 'OCC.Core.BRepMesh', 
    'OCC.Core.IFSelect', 'OCC.Core.Bnd', 'OCC.Core.BRepBndLib', 
    'OCC.Core.TCollection', 'OCC.Core.Standard', 'OCC.Core.TopoDS',
    # 🔧 新增：部件识别相关模块
    'OCC.Core.STEPCAFControl', 'OCC.Core.XCAFDoc', 
    'OCC.Core.TDocStd', 'OCC.Core.TDF', 'OCC.Core.TDataStd',
    'OCC.Core.Quantity', 'OCC.Core.TopAbs'
]) 

hiddenimports = sanitize_imports(hiddenimports) 

# ==========================================
# 🔧 关键：最终验证
# ==========================================
_safe_print("\n[Final Validation]")
_safe_print(f"  Before: binaries={len(binaries)}, datas={len(datas)}")

binaries = validate_tuples(binaries, "binary")
datas = validate_tuples(datas, "data")

_safe_print(f"  After:  binaries={len(binaries)}, datas={len(datas)}")
_safe_print(f"  hiddenimports: {len(hiddenimports)}")

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
    # Win7 路径修复钩子依然保留，双重保险
    runtime_hooks=['./rthook_win7.py', './rthook_encoding.py'], 
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython'], 
    win_no_prefer_redirects=False, 
    win_private_assemblies=False, 
    cipher=block_cipher, 
    noarchive=False, 
) 

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

# COLLECT 负责生成目录
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