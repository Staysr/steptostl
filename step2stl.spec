# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for step2stl (cadquery-ocp/OCP version)
输出: step2stl 文件夹，包含 step2stl.exe 和 _internal 目录
"""

import sys
import os

# =========================================================
#                    配置区域
# =========================================================

# 你的脚本文件名
SCRIPT_NAME = 'step2stl_win7.py'

# 生成的可执行文件名
EXE_NAME = 'step2stl'

# 打包模式：False = 文件夹模式 (生成 _internal 目录)
BUILD_MODE_ONEFILE = False

# 是否使用 UPX 压缩
USE_UPX = False

# =========================================================
#                      打包逻辑
# =========================================================

block_cipher = None

# OCP 相关的隐藏导入 (根据你的代码使用情况)
ocp_hidden_imports = [
    'OCP',
    'OCP.STEPCAFControl',
    'OCP.StlAPI',
    'OCP.BRepMesh',
    'OCP.IFSelect',
    'OCP.Bnd',
    'OCP.BRepBndLib',
    'OCP.TDocStd',
    'OCP.XCAFApp',
    'OCP.TCollection',
    'OCP.XCAFDoc',
    'OCP.TDF',
    'OCP.TDataStd',
    'OCP.TopAbs',
    'OCP.TopoDS',
    'OCP.TopExp',
    'OCP.RWGltf',
    'OCP.TColStd',
    'OCP.Message',
    'OCP.gp',
    'OCP.BRep',
    'OCP.BRepBuilderAPI',
    'OCP.Geom',
    'OCP.GeomAbs',
    'OCP.Standard',
    'OCP.Quantity',
]

# 运行时钩子
runtime_hooks_list = []
if os.path.exists('rthook_win7.py'):
    runtime_hooks_list.append('rthook_win7.py')
if os.path.exists('rthook_encoding.py'):
    runtime_hooks_list.append('rthook_encoding.py')

# hook 目录 (如果有 hook-OCC.py)
hooks_path = []
if os.path.exists('hook-OCC.py'):
    hooks_path = ['.']

# 1. 分析依赖
a = Analysis(
    [SCRIPT_NAME],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=ocp_hidden_imports,
    hookspath=hooks_path,
    hooksconfig={},
    runtime_hooks=runtime_hooks_list,
    excludes=[
        'tkinter', 'test', 'unittest', 'email', 'http',
        'xmlrpc', 'html', 'pydoc', 'pdb', 'distutils',
        'matplotlib', 'scipy', 'PIL', 'IPython', 'jupyter',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 2. 压缩 Python 字节码
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 3. 根据模式构建
if BUILD_MODE_ONEFILE:
    # --- 单文件模式 (OneFile) ---
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=EXE_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=USE_UPX,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    # --- 文件夹模式 (OneDir) - 生成 _internal 结构 ---
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=EXE_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=USE_UPX,
        console=True,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    # 收集到文件夹 (名称为 step2stl)
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=USE_UPX,
        upx_exclude=[],
        name=EXE_NAME,  # 生成的文件夹名字：step2stl
    )