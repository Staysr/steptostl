# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# =========================================================
#                    用户配置区域
# =========================================================

# [开关] True = 打包成单个EXE (体积最小，便于分发)
#        False = 打包成文件夹 (启动最快，便于调试)
BUILD_MODE_ONEFILE = False

# 你的脚本文件名
SCRIPT_NAME = 'step2stl.py'

# 生成的 EXE 名字
EXE_NAME = 'StepToStl'

# 是否使用 UPX 压缩 (需要你下载 upx.exe 放在目录里，没有则设为 False)
# 建议设为 False 以避免 Win7 下极个别兼容性问题，除非你非常在意体积
USE_UPX = False

# =========================================================
#                      打包逻辑
# =========================================================

block_cipher = None

# 1. 分析依赖
a = Analysis(
    [SCRIPT_NAME],
    pathex=[],
    binaries=[],
    datas=[],
    # 强制包含 OCP，防止 PyInstaller 找不到
    hiddenimports=['OCP'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 剔除不必要的标准库，大幅减小体积
    excludes=[
        'tkinter', 'test', 'unittest', 'email', 'http',
        'xmlrpc', 'html', 'pydoc', 'pdb', 'distutils',
        'matplotlib', 'scipy', 'numpy', 'PIL' # 如果你的代码没用到这些，排除它们
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
        runtime_tmpdir=None, # 默认解压到临时目录
        console=True,        # 开启黑框显示进度
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    # --- 文件夹模式 (OneDir) ---
    exe = EXE(
        pyz,
        a.scripts,
        [], # 注意：文件夹模式这里不包含二进制文件
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
    # 收集文件夹
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=USE_UPX,
        upx_exclude=[],
        name=EXE_NAME + '_Folder', # 生成的文件夹名字
    )