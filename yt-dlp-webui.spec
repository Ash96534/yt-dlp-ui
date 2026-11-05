# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# Determine ffmpeg binary names based on platform
if sys.platform == 'win32':
    ffmpeg_bin = 'ffmpeg/bin/ffmpeg.exe'
    ffprobe_bin = 'ffmpeg/bin/ffprobe.exe'
else:
    ffmpeg_bin = 'ffmpeg/bin/ffmpeg'
    ffprobe_bin = 'ffmpeg/bin/ffprobe'

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        (ffmpeg_bin, 'ffmpeg/bin'),
        (ffprobe_bin, 'ffmpeg/bin'),
    ],
    datas=[
        ('config/config.default.json', 'config'),
    ],
    hiddenimports=[
        'yt_dlp',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNetwork',
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

pyz = PYZ(a.pyz, a.packages, a.binaries, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='yt-dlp-webui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # True = console window, False = GUI only
    icon=None,  # Add icon path here: 'build/icon.ico'
    version='file_version_info.txt',
)

app = BUNDLE(
    exe,
    name='yt-dlp-webui.app',
    icon=None,
    bundle_identifier=None,
)
