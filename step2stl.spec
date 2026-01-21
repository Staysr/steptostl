# -*- mode: python ; coding: utf-8 -*- 
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# 收集所有必要的模块
hiddenimports = [] 
hiddenimports += collect_submodules('OCC') 
hiddenimports += collect_submodules('trimesh') 
hiddenimports += ['numpy', 'numpy.core', 'numpy.core._multiarray_umath'] 

# 收集 OCC 数据文件和动态库
datas = [] 
datas += collect_data_files('OCC', include_py_files=True) 

binaries = [] 
binaries += collect_dynamic_libs('OCC') 
  # 🚀 排除更多不需要的模块
a = Analysis( 
    ['step2stl.py'], 
    pathex=[], 
    binaries=binaries, 
    datas=datas, 
    hiddenimports=hiddenimports, 
    hookspath=[], 
    hooksconfig={}, 
    runtime_hooks=[], 
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 
        'IPython', 'jupyter', 'notebook',
        'pandas', 'scipy', 'sklearn',
        'tornado', 'zmq', 'jinja2',
        '_tkinter', 'tcl', 'tk'
    ],
    noarchive=False, 
) 

pyz = PYZ(a.pure) 

 # 🚀 启用UPX压缩
exe = EXE( 
    pyz, 
    a.scripts, 
    a.binaries, 
    a.datas, 
    [], 
    name='step2stl', 
    debug=False, 
    bootloader_ignore_signals=False, 
    strip=False, 
    upx=True,
    upx_exclude=[], 
    runtime_tmpdir=None, 
    console=True, 
    disable_windowed_traceback=False, 
    argv_emulation=False, 
    target_arch=None, 
    codesign_identity=None, 
    entitlements_file=None, 
    icon=None
)