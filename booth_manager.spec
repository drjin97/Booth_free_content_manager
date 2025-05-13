# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['booth_manager/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('booth_manager/booth_cookie.txt', '.'),
        ('booth_manager/constants.py', '.'),
        ('booth_manager/logger_config.py', '.'),
        ('booth_manager/data_manager.py', '.'),
        ('booth_manager/downloader_widget.py', '.'),
        ('booth_manager/main_window.py', '.'),
        ('booth_manager/url_input_widget.py', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'requests',
        'bs4',
        'logging',
        'json',
        'os',
        'sys',
        'time',
        're',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HakkaCrawler',
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
    icon='booth_manager/icon.ico'  # 아이콘 파일이 있다면 경로 지정
) 