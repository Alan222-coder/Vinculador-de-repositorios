# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/Alanf/Downloads/Herramienta Git/src/main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/Alanf/AppData/Roaming/Python/Python314/site-packages/customtkinter', 'customtkinter'), ('C:/Users/Alanf/Downloads/Herramienta Git/assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GitManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/Alanf/Downloads/Herramienta Git/assets/icon.ico'],
)
