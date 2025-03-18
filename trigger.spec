import platform
from argparse import ArgumentParser

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE

parser = ArgumentParser()
parser.add_argument("--portable", action="store_true")
options = parser.parse_args()


system = platform.system()

name = "TriggerEditor" if system == "Windows" else "tagstudio"
icon = None
if system == "Windows":
    icon = "src/trigger_designer/Resource/TriEditorLogo.ico"
elif system == "Darwin":
    icon = "src/trigger_designer/Resource/TriEditorLogo.ico"


a = Analysis(
    ["src/trigger_designer/main.py"],
    pathex=[
        'src/trigger_designer',  # Add the main source directory to Python path
        'src'                    # Add parent directory for imports
    ],
    binaries=[],
    datas=[("src/trigger_designer", "trigger_designer")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    excludes=[],
    runtime_hooks=['log_dist.py'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

include = [a.scripts]
if options.portable:
    include += (a.binaries, a.datas)
exe = EXE(
    pyz,
    *include,
    [],
    bootloader_ignore_signals=False,
    console=False,
    hide_console="hide-early",
    disable_windowed_traceback=False,
    debug=True,
    name=name,
    exclude_binaries=not options.portable,
    icon=icon,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
)

coll = (
    None
    if options.portable
    else COLLECT(
        exe,
        a.binaries,
        a.datas,
        name=name,
        strip=False,
        upx=True,
        upx_exclude=[],
    )
)

if system == "Darwin":
    app = BUNDLE(
        exe if coll is None else coll,
        name=f"{pyproject['name']}.app",
        icon=icon,
        bundle_identifier="com.cyanvoxel.tagstudio",
        version=pyproject["version"],
        info_plist={
            "NSAppleScriptEnabled": False,
            "NSPrincipalClass": "NSApplication",
        },
    )

# vi: ft=python