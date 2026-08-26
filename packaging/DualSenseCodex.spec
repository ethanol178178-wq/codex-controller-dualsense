# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_dir = Path(SPECPATH).parent

a = Analysis(
    [str(project_dir / "launcher.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        (str(project_dir / "index.html"), "."),
        (str(project_dir / "app.js"), "."),
        (str(project_dir / "styles.css"), "."),
        (str(project_dir / "VERSION"), "."),
        (str(project_dir / "LICENSE"), "."),
        (str(project_dir / "NOTICE.md"), "."),
        (str(project_dir / "README.md"), "."),
        (str(project_dir / "CHANGELOG.md"), "."),
        (str(project_dir / "SECURITY.md"), "."),
        (str(project_dir / "THIRD_PARTY_NOTICES.md"), "."),
        (str(project_dir / "assets" / "dualsense-wireframe.png"), "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DualSenseCodex",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DualSenseCodex",
)
