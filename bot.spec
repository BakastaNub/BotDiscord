# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['bot.py'],
    pathex=[],
    binaries=[],
    datas=[],  # Eliminamos config.json y .env de aquí
    hiddenimports=[
        'discord',
        'requests',
        'bs4',
        'fuzzywuzzy',
        'discord.ext.commands',
        'discord.app_commands',
        'discord.ext.tasks',
        'aiohttp',
        'chardet',
        'cchardet',
        'aiodns',
        'discord.http',
        'discord.gateway',
        'discord.ext',
        'dotenv',
        'asyncio',
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
    name='mi_bot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)