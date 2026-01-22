# -*- coding: utf-8 -*-
"""
PyInstaller hook for pythonocc-core
"""

# ==========================================
# Import with error handling
# ==========================================
import sys
import os

# Safe print setup
def _safe_print(msg):
    """Ultra-safe print function"""
    try:
        print(msg)
    except:
        try:
            sys.stdout.write(str(msg) + '\n')
            sys.stdout.flush()
        except:
            pass

_safe_print("=" * 70)
_safe_print("OCC Hook: Starting...")

# ==========================================
# Import PyInstaller modules
# ==========================================
try:
    from PyInstaller.utils.hooks import collect_submodules, get_package_paths
    from PyInstaller.compat import is_win, is_darwin, is_linux
    _safe_print("OCC Hook: PyInstaller modules imported OK")
except Exception as e:
    _safe_print("OCC Hook ERROR: Cannot import PyInstaller modules")
    _safe_print(str(e))
    # Provide minimal fallback
    hiddenimports = []
    datas = []
    binaries = []
    raise

import glob

# ==========================================
# Initialize
# ==========================================
hiddenimports = []
datas = []
binaries = []

_safe_print("OCC Hook: Initialized")

# ==========================================
# 1. Collect Python modules
# ==========================================
try:
    hiddenimports = collect_submodules('OCC')
    _safe_print("OCC Hook: Collected %d Python modules" % len(hiddenimports))
except Exception as e:
    _safe_print("OCC Hook WARNING: collect_submodules failed: %s" % str(e))
    hiddenimports = ['OCC', 'OCC.Core']

# ==========================================
# 2. Get OCC package path
# ==========================================
occ_pkg_dir = None
try:
    pkg_base, occ_pkg_dir = get_package_paths('OCC')
    _safe_print("OCC Hook: Package dir = %s" % occ_pkg_dir)
except Exception as e:
    _safe_print("OCC Hook WARNING: get_package_paths failed: %s" % str(e))

# ==========================================
# 3. Collect extension modules
# ==========================================
if occ_pkg_dir and os.path.exists(occ_pkg_dir):
    try:
        _safe_print("OCC Hook: Collecting extensions...")
        ext_count = 0
        
        for root, dirs, files in os.walk(occ_pkg_dir):
            for file in files:
                if file.endswith(('.pyd', '.so', '.dylib')):
                    src_path = os.path.join(root, file)
                    rel_dir = os.path.relpath(root, occ_pkg_dir)
                    
                    if rel_dir == '.':
                        dest_dir = 'OCC'
                    else:
                        dest_dir = os.path.join('OCC', rel_dir)
                    
                    binaries.append((src_path, dest_dir))
                    ext_count += 1
        
        _safe_print("OCC Hook: Found %d extension files" % ext_count)
    except Exception as e:
        _safe_print("OCC Hook WARNING: Extension collection failed: %s" % str(e))

# ==========================================
# 4. Collect shared libraries
# ==========================================
try:
    _safe_print("OCC Hook: Collecting shared libraries...")
    
    conda_prefix = os.environ.get('CONDA_PREFIX', '')
    if not conda_prefix:
        python_exe = sys.executable
        if 'conda' in python_exe.lower() or 'miniconda' in python_exe.lower():
            conda_prefix = os.path.dirname(os.path.dirname(python_exe))
    
    if conda_prefix and os.path.exists(conda_prefix):
        _safe_print("OCC Hook: Conda prefix = %s" % conda_prefix)
        
        lib_dirs = []
        lib_patterns = []
        
        if sys.platform == 'win32':
            lib_dirs = [
                os.path.join(conda_prefix, 'Library', 'bin'),
                os.path.join(conda_prefix, 'Library', 'lib'),
                os.path.join(conda_prefix, 'bin'),
            ]
            lib_patterns = [
                'TK*.dll',
                'freetype*.dll',
                'freeimage*.dll',
                'tbb*.dll',
            ]
        elif sys.platform == 'darwin':
            lib_dirs = [os.path.join(conda_prefix, 'lib')]
            lib_patterns = ['libTK*.dylib', 'libfreeimage*.dylib', 'libfreetype*.dylib']
        else:
            lib_dirs = [
                os.path.join(conda_prefix, 'lib'),
                os.path.join(conda_prefix, 'lib64'),
            ]
            lib_patterns = ['libTK*.so*', 'libfreeimage*.so*', 'libfreetype*.so*']
        
        lib_count = 0
        for lib_dir in lib_dirs:
            if not os.path.exists(lib_dir):
                continue
            
            _safe_print("OCC Hook: Searching %s" % lib_dir)
            
            for pattern in lib_patterns:
                try:
                    lib_files = glob.glob(os.path.join(lib_dir, pattern))
                    for lib_file in lib_files:
                        # Skip symlinks on Unix
                        if sys.platform != 'win32' and os.path.islink(lib_file):
                            continue
                        
                        binaries.append((lib_file, '.'))
                        lib_count += 1
                except Exception as e:
                    _safe_print("OCC Hook WARNING: Pattern %s failed: %s" % (pattern, str(e)))
        
        _safe_print("OCC Hook: Collected %d shared libraries" % lib_count)
    else:
        _safe_print("OCC Hook WARNING: Conda prefix not found")

except Exception as e:
    _safe_print("OCC Hook ERROR: Library collection failed: %s" % str(e))
    import traceback
    _safe_print(traceback.format_exc())

# ==========================================
# 5. Collect data files
# ==========================================
if occ_pkg_dir and os.path.exists(occ_pkg_dir):
    try:
        data_count = 0
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
                    data_count += 1
        
        _safe_print("OCC Hook: Collected %d data files" % data_count)
    except Exception as e:
        _safe_print("OCC Hook WARNING: Data collection failed: %s" % str(e))

# ==========================================
# Summary
# ==========================================
_safe_print("=" * 70)
_safe_print("OCC Hook Summary:")
_safe_print("  hiddenimports: %d" % len(hiddenimports))
_safe_print("  binaries: %d" % len(binaries))
_safe_print("  datas: %d" % len(datas))

# Check TK libraries
tk_count = 0
for b in binaries:
    if 'TK' in b[0] or 'tk' in b[0].lower():
        tk_count += 1

if tk_count > 0:
    _safe_print("  TK libraries: %d [OK]" % tk_count)
else:
    _safe_print("  TK libraries: 0 [WARNING]")

_safe_print("=" * 70)