# -*- coding: utf-8 -*- 
""" 
PyInstaller hook for pythonocc-core
Force collect all OpenCASCADE dynamic libraries and dependencies
""" 

import sys
import os

# ==========================================
# Windows Console Encoding Fix
# Compatible with: Windows 7/8/10/11
# ==========================================
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    
    try:
        import io
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding='utf-8', 
                errors='replace', 
                line_buffering=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, 
                encoding='utf-8', 
                errors='replace', 
                line_buffering=True
            )
    except Exception:
        pass

# ==========================================
# Safe Print Function
# ==========================================
_original_print = print

def safe_print(*args, **kwargs):
    """Safe print function with encoding error handling"""
    try:
        _original_print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):
        safe_args = []
        for arg in args:
            try:
                safe_arg = str(arg).encode('ascii', 'replace').decode('ascii')
                safe_args.append(safe_arg)
            except Exception:
                safe_args.append(repr(arg))
        _original_print(*safe_args, **kwargs)

print = safe_print

# ==========================================
# Import PyInstaller Modules
# ==========================================
from PyInstaller.utils.hooks import collect_submodules, get_package_paths
from PyInstaller.compat import is_win, is_darwin, is_linux
import glob

print("\n" + "=" * 70) 
print("CUSTOM OCC HOOK: Collecting pythonocc-core dependencies") 
print("=" * 70) 

# ==========================================
# 1. Collect All Python Modules
# ==========================================
hiddenimports = collect_submodules('OCC') 
print("[1/4] Collected %d OCC Python modules" % len(hiddenimports)) 

# ==========================================
# 2. Initialize
# ==========================================
datas = [] 
binaries = [] 

# ==========================================
# 3. Get OCC Package Path
# ==========================================
try: 
    pkg_base, occ_pkg_dir = get_package_paths('OCC') 
    print("[2/4] OCC package location: %s" % occ_pkg_dir) 
except Exception as e: 
    print("ERROR: Cannot locate OCC package: %s" % str(e)) 
    occ_pkg_dir = None

# ==========================================
# 4. Collect OCC Python Extension Modules (.pyd/.so) 
# ==========================================
if occ_pkg_dir and os.path.exists(occ_pkg_dir): 
    print("[3/4] Collecting OCC extension modules...") 
    
    # Find all extension files
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
                
                # Target path: keep OCC directory structure
                if rel_dir == '.': 
                    dest_dir = 'OCC' 
                else: 
                    dest_dir = os.path.join('OCC', rel_dir) 
                
                binaries.append((src_path, dest_dir)) 
                ext_files.append(file) 
    
    print("    Found %d extension files" % len(ext_files)) 
    for f in ext_files[:5]: 
        print("      - %s" % f) 
    if len(ext_files) > 5: 
        print("      ... and %d more" % (len(ext_files) - 5)) 

# ==========================================
# 5. Collect OpenCASCADE Shared Libraries (CRITICAL!) 
# ==========================================
print("[4/4] Collecting OpenCASCADE shared libraries...") 

conda_prefix = os.environ.get('CONDA_PREFIX', '') 
if not conda_prefix: 
    # Try to infer from Python path
    python_exe = sys.executable
    if 'conda' in python_exe or 'miniconda' in python_exe.lower(): 
        conda_prefix = os.path.dirname(os.path.dirname(python_exe)) 

if conda_prefix and os.path.exists(conda_prefix): 
    print("    Conda environment: %s" % conda_prefix) 
    
    lib_dirs = [] 
    lib_patterns = [] 
    
    if is_win: 
        # Windows: Library/bin directory
        lib_dirs = [ 
            os.path.join(conda_prefix, 'Library', 'bin'), 
            os.path.join(conda_prefix, 'Library', 'lib'), 
            os.path.join(conda_prefix, 'bin'), 
        ] 
        # OpenCASCADE library prefixes
        lib_patterns = [ 
            'TK*.dll',           # OpenCASCADE core libraries
            'freetype*.dll',     # Font rendering
            'freeimage*.dll',    # Image processing
            'tbb*.dll',          # Intel Threading Building Blocks
            'msvcp*.dll',        # MSVC runtime
            'vcruntime*.dll',    # VC runtime
        ] 
    elif is_darwin: 
        # macOS: lib directory
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
        # Linux: lib directory
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
        
        print("    Searching in: %s" % lib_dir) 
        
        for pattern in lib_patterns: 
            lib_files = glob.glob(os.path.join(lib_dir, pattern)) 
            for lib_file in lib_files: 
                lib_name = os.path.basename(lib_file) 
                
                # Skip symbolic links (on macOS/Linux) 
                if os.path.islink(lib_file) and not is_win: 
                    continue
                
                # Add to root directory (same level as main program) 
                binaries.append((lib_file, '.')) 
                collected_libs.append(lib_name) 
    
    print("    Collected %d shared libraries:" % len(collected_libs)) 
    # Group by type
    tk_libs = [l for l in collected_libs if 'TK' in l or 'tk' in l.lower()] 
    other_libs = [l for l in collected_libs if 'TK' not in l and 'tk' not in l.lower()] 
    
    if tk_libs: 
        print("      OpenCASCADE (TK*): %d files" % len(tk_libs)) 
        for lib in tk_libs[:3]: 
            print("        - %s" % lib) 
        if len(tk_libs) > 3: 
            print("        ... and %d more" % (len(tk_libs) - 3)) 
    
    if other_libs: 
        print("      Dependencies: %d files" % len(other_libs)) 
        for lib in other_libs[:3]: 
            print("        - %s" % lib) 
        if len(other_libs) > 3: 
            print("        ... and %d more" % (len(other_libs) - 3)) 
    
    if not collected_libs: 
        print("    WARNING: No OpenCASCADE libraries found!") 
        print("    Please verify conda environment: %s" % conda_prefix) 
else: 
    print("    WARNING: CONDA_PREFIX not found!") 
    print("    OpenCASCADE libraries may not be included!") 

# ==========================================
# 6. Collect OCC Data Files
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
# Summary
# ==========================================
print("\n" + "=" * 70) 
print("OCC HOOK SUMMARY:") 
print("  Hidden imports: %d" % len(hiddenimports)) 
print("  Binary files:   %d" % len(binaries)) 
print("  Data files:     %d" % len(datas)) 
print("=" * 70 + "\n") 

# Verify critical libraries are collected
tk_count = len([b for b in binaries if 'TK' in b[0] or 'tk' in b[0].lower()]) 
if tk_count == 0: 
    print("WARNING: No TK* libraries found!") 
    print("   The built executable may fail with 'pythonocc-core not installed' error") 
    print("   Please check your conda environment setup.\n") 
else: 
    print("SUCCESS: %d OpenCASCADE TK libraries will be included\n" % tk_count)