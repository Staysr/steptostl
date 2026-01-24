# -*- mode: python ; coding: utf-8 -*- 
""" 
step2stl PyInstaller Spec (Windows 7 Compatibility Fix)
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
    """验证并去重"""
    if not tuple_list: return []
    cleaned = []
    seen = set()
    for item in tuple_list:
        try:
            if len(item) != 2: continue
            src, dest = item
            if not isinstance(src, str) or not os.path.exists(src): continue
            # 简单的去重键：目标路径
            key = (os.path.basename(src), dest)
            if key in seen: continue
            seen.add(key)
            cleaned.append((src, dest))
        except: continue
    return cleaned

_safe_print("=" * 70) 
_safe_print("step2stl Build Config (Win7 Hardened)") 
_safe_print("=" * 70) 

# ==========================================
# 1. 定位 Conda 环境 (关键步骤)
# ==========================================
conda_prefix = os.environ.get('CONDA_PREFIX') 
if not conda_prefix: 
    try: 
        if 'conda' in sys.executable.lower(): 
            conda_prefix = os.path.dirname(os.path.dirname(sys.executable)) 
    except: pass

# 确保找到了 Conda，因为我们需要里面的 DLL
if not conda_prefix:
    _safe_print("WARNING: Conda prefix not found! Win7 compatibility might fail.")
else:
    _safe_print(f"Conda Prefix: {conda_prefix}")

# ==========================================
# 2. 初始化
# ==========================================
hiddenimports = [] 
datas = [] 
binaries = [] 
pathex = [] 

# ==========================================
# 3. 核心 DLL 收集 (针对 Windows 7 的特殊处理)
# ==========================================
if sys.platform == 'win32' and conda_prefix: 
    # 定义搜索路径，优先 Conda Library/bin
    lib_bin = os.path.join(conda_prefix, 'Library', 'bin') 
    conda_bin = os.path.join(conda_prefix, 'bin') 
    
    # 将 Conda 路径加入 pathex 且放在最前
    pathex = [lib_bin, conda_bin]
    
    _safe_print("\n[Collecting DLLs - Win7 Force Mode]") 
    
    # 这里的关键是：不要让 PyInstaller 自己去 System32 找 api-ms-win-*
    # 我们手动从 Conda 的 Library/bin 把它们作为二进制文件塞进去
    
    dll_patterns = [ 
        'TK*.dll',         # OCC Core
        'tbb*.dll',        # TBB
        'freeimage*.dll', 
        'freetype*.dll',   
        'zlib*.dll',
        'sqlite3.dll',
        # --- 系统运行库 (必须从 Conda 拿，不能从 System32 拿) ---
        'ucrtbase.dll', 
        'vcruntime140*.dll', 
        'msvcp140*.dll', 
        'concrt140.dll',
        'vcomp140.dll',
        'api-ms-win-*.dll' # 只有 Conda 里的才是实体 DLL，System32 里的是桩代码
    ] 
    
    count = 0
    # 只在 Conda 目录里搜，坚决不去 C:\Windows
    for s_dir in [lib_bin, conda_bin]: 
        if not os.path.exists(s_dir): continue
        
        for pattern in dll_patterns: 
            found = glob.glob(os.path.join(s_dir, pattern)) 
            for dll in found: 
                # 排除 debug 版本
                if dll.lower().endswith('d.dll') and not dll.lower().endswith('bnd.dll'): continue
                
                # 强制将这些 DLL 放在根目录，覆盖系统的查找逻辑
                binaries.append((dll, '.')) 
                count += 1
                
    _safe_print(f"  Collected {count} Critical DLLs from Conda.") 

# ==========================================
# 4. 依赖处理
# ==========================================
# Numpy
try: 
    np_hidden, np_bin, np_data = collect_all('numpy') 
    hiddenimports.extend(np_hidden)
    # 过滤掉 numpy 收集到的 System32 下的 DLL (如果有的话)
    for b in np_bin:
        if 'windows\\system32' in b[0].lower(): continue
        binaries.append(b)
    datas.extend(np_data)
except: 
    hiddenimports.extend(['numpy', 'numpy.core']) 

# Trimesh & Jaraco
try: hiddenimports.extend(collect_submodules('trimesh')) 
except: hiddenimports.append('trimesh') 

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

# 去重
hiddenimports = list(set(hiddenimports))
binaries = validate_tuples(binaries, "binary")
datas = validate_tuples(datas, "data")

# ==========================================
# 5. Analysis
# ==========================================
block_cipher = None

a = Analysis( 
    ['step2stl.py'], 
    pathex=pathex,  # 确保 Conda bin 在路径中
    binaries=binaries, 
    datas=datas, 
    hiddenimports=hiddenimports, 
    hookspath=['./hooks'], 
    hooksconfig={}, 
    runtime_hooks=['./rthook_win7.py', './rthook_encoding.py'], 
    # 关键：排除所有系统层面的转发 DLL，强迫使用我们 bundle 进去的
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'matplotlib', 'scipy', 'pytest', 'IPython'], 
    win_no_prefer_redirects=False, 
    win_private_assemblies=False, 
    cipher=block_cipher, 
    noarchive=False, 
) 

# 删除 PyInstaller 可能自动收集到的 System32 下的 api-ms-win-*
# 这是一个清理步骤，确保只有我们刚才从 Conda 收集的被保留
new_binaries = []
for b in a.binaries:
    src_lower = b[0].lower()
    # 如果源路径在 System32 且是 api-ms 或 ucrt，丢弃它 (因为它是 Win10 桩)
    if 'system32' in src_lower and ('api-ms-win' in src_lower or 'ucrtbase' in src_lower):
        _safe_print(f"  Removing System32 Stub: {os.path.basename(src_lower)}")
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