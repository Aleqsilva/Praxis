# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['praxis.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('fds_config_generator.py', '.'),
        ('xml_utils.py', '.'),
        ('images', 'images'),
        ('Validador', 'Validador'),
        ('logo.png', '.'),
        ('praxis_config.json', '.'),
    ],
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
    name='Praxis',
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
    icon='icon.ico',
)