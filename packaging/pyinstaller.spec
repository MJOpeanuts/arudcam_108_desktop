from pathlib import Path

project_root = Path(SPECPATH).parent
app = Analysis(
    [str(project_root / "src/arducam_capture/launcher/main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "migrations"), "migrations"),
        (str(project_root / "alembic.ini"), "."),
        (
            str(project_root / "src/arducam_capture/frontends/streamlit_app/app.py"),
            "arducam_capture/frontends/streamlit_app",
        ),
    ],
    hiddenimports=["streamlit.web.cli"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(app.pure)
exe = EXE(
    pyz,
    app.scripts,
    app.binaries,
    app.datas,
    [],
    name="ArducamCapture",
    console=False,
    upx=True,
    bootloader_ignore_signals=False,
    strip=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, app.binaries, app.datas, strip=False, upx=True, name="ArducamCapture")
