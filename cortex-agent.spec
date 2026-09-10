# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for cortex-agent
# Build: uv run pyinstaller cortex-agent.spec
#
# Output locations:
#   dist/cortex-agent          (macOS / Linux)
#   dist/cortex-agent.exe      (Windows)

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    # Entry point — the same function the pyproject.toml script calls
    ['cortex_agent/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # prompt_toolkit ships data files (key bindings, etc.)
        *collect_data_files('prompt_toolkit'),
    ],
    hiddenimports=[
        # PyInstaller sometimes misses these with dynamic imports
        *collect_submodules('prompt_toolkit'),
        'cortex_agent.setup_wizard',
        'cortex_agent.mcp_server',
        'getpass',
        'importlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test frameworks and dev tools to keep binary small
        'pytest', 'unittest', 'doctest', 'pdb',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cortex-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # terminal app — keep console open
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows: embed a version resource (optional, harmless if missing)
    version=None,
    icon=None,
)
