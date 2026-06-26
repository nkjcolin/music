# -*- mode: python ; coding: utf-8 -*-
# One-folder build: starts instantly (no per-launch extraction of bundled
# ffmpeg). Produces dist/Songtify/ — ship the whole folder.
#   pyinstaller music_onedir.spec

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules('yt_dlp')
    + collect_submodules('syncedlyrics')
    + ['mutagen', 'qtawesome', 'PIL']
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ffmpeg.exe', '.'),
        ('ffprobe.exe', '.'),
        ('assets/youtube_music.ico', '.'),
    ],
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='Songtify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/youtube_music.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Songtify',
)
