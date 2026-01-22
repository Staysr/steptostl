# -*- mode: python ; coding: utf-8 -*- 
""" 
step2stl PyInstaller Build Configuration
Enhanced - Force include all OCC dependencies
""" 

import sys
import os

# ==========================================
# Windows Console Encoding Fix (MUST BE FIRST)
# Compatible with: Windows 7/8/10/11
# ==========================================
if sys.platform == 'win32':  # Works on all Windows versions
    # Force UTF-8 encoding
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    
    # Rewrap standard output streams
    try:
        import io
        # Check for buffer attribute (avoid errors in some environments)
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding='utf-8', 
                errors='replace',  # Replace unencodable chars with ?
                line_buffering=True  # Line buffering for real-time output
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, 
                encoding='utf-8', 
                errors='replace', 
                line_buffering=True
            )
    except Exception:
        # If it fails, don't block the rest of the process
        pass

# ==========================================
# Safe Print Function (handle emoji and special chars)
# ==========================================
_original_print = print

def safe_print(*args, **kwargs):
    """
    Safe print function with automatic encoding error handling
    If encountering undisplayable characters, automatically downgrade to ASCII mode
    """
    try:
        _original_print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Downgrade: remove special characters
        safe_args = []
        for arg in args:
            try:
                # Try to convert to ASCII-safe string
                safe_arg = str(arg).encode('ascii', 'replace').decode('ascii')
                safe_args.append(safe_arg)
            except Exception:
                # Last resort: use repr
                safe_args.append(repr(arg))
        _original_print(*safe_args, **kwargs)

# Replace global print function
print = safe_print

# ==========================================
# Import PyInstaller Modules
# ==========================================
from PyInstaller.utils.hooks import collect_all, collect_submodules

print("=" * 70) 
print("step2stl PyInstaller Build Configuration") 
print("=" * 70) 

# ==========================================
# Environment Check
# ==========================================
print("\n[Environment Check]") 
print("Python: %s" % sys.version) 
print("Platform: %s" % sys.platform) 
print("Python executable: %s" % sys.executable) 

conda_prefix = os.environ.get('CONDA_PREFIX', '') 
if conda_prefix: 
    print("Conda prefix: %s" % conda_prefix) 
else: 
    print("WARNING: CONDA_PREFIX not set!") 

print() 

# ==========================================
# Helper Functions
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
# Initialize
# ==========================================
hiddenimports = [] 
datas = [] 
binaries = [] 

# ==========================================
# Collect numpy
# ==========================================
print("[Collecting numpy]") 
try: 
    numpy_result = collect_all('numpy') 
    hiddenimports += safe_filter_strings(numpy_result[0]) 
    binaries += safe_filter_tuples(numpy_result[1]) 
    datas += safe_filter_tuples(numpy_result[2]) 
    print("  [OK] Collected numpy") 
except Exception as e: 
    print("  [WARNING] %s" % str(e)) 
    hiddenimports += ['numpy', 'numpy.core', 'numpy._core'] 

# ==========================================
# Collect jaraco
# ==========================================
print("\n[Collecting jaraco]") 
try: 
    jaraco_result = collect_all('jaraco') 
    hiddenimports += safe_filter_strings(jaraco_result[0]) 
    datas += safe_filter_tuples(jaraco_result[2]) 
    print("  [OK] Collected jaraco") 
except Exception as e: 
    print("  [WARNING] %s" % str(e)) 
    hiddenimports += ['jaraco', 'jaraco.text', 'jaraco.functools'] 

# ==========================================
# Standard Library
# ==========================================
print("\n[Adding standard library modules]") 
hiddenimports += [ 
    'ipaddress', 'urllib', 'urllib.parse', 'pathlib', 'argparse', 
    'collections', 'collections.abc', 'warnings', 'traceback', 
] 
print("  [OK] Added standard modules") 

# ==========================================
# Collect OCC (will use custom hook) 
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
    print("  [OK] Collected %d OCC.Core modules" % len(occ_all)) 
except Exception:
    pass

# ==========================================
# Collect trimesh
# ==========================================
print("\n[Collecting trimesh]") 
try: 
    trimesh_modules = collect_submodules('trimesh') 
    hiddenimports += safe_filter_strings(trimesh_modules) 
    print("  [OK] Collected trimesh") 
except Exception:
    hiddenimports += ['trimesh'] 

# ==========================================
# Deduplicate and Validate
# ==========================================
hiddenimports = list(set(safe_filter_strings(hiddenimports))) 
binaries = safe_filter_tuples(binaries) 
datas = safe_filter_tuples(datas) 

print("\n[Summary Before Analysis]") 
print("  Hidden imports: %d" % len(hiddenimports)) 
print("  Binaries: %d" % len(binaries)) 
print("  Data files: %d" % len(datas)) 

# ==========================================
# Exclude Modules
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
    hookspath=['./hooks'],  # Use custom hook
    hooksconfig={}, 
    runtime_hooks=[], 
    excludes=excludes, 
    noarchive=False, 
) 

# Remove pkg_resources hook
a.scripts = [s for s in a.scripts if 'pyi_rth_pkgres' not in s[1]] 

# Filter unnecessary binaries
def should_keep(name): 
    if not isinstance(name, str): 
        return True
    name_lower = name.lower() 
    exclude = ['test', 'example', 'doc', '.pdb'] 
    return not any(e in name_lower for e in exclude) 

a.binaries = [(n, p, t) for n, p, t in a.binaries if should_keep(n)] 

print("[Final Analysis Summary]") 
print("  Scripts: %d" % len(a.scripts)) 
print("  Binaries: %d" % len(a.binaries)) 
print("  Data files: %d" % len(a.datas)) 

# Check if TK libraries are included
tk_libs = [b[0] for b in a.binaries if 'TK' in b[0] or 'tk' in b[0].lower()] 
if tk_libs: 
    print("  [OK] Found %d OpenCASCADE TK libraries" % len(tk_libs)) 
else: 
    print("  [WARNING] No TK libraries found in binaries!") 

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