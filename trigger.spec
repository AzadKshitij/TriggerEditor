"""PyInstaller spec file for TriggerEditor application."""

import platform
from argparse import ArgumentParser
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE

# Parse command line arguments
parser = ArgumentParser(description="Build TriggerEditor with PyInstaller")
parser.add_argument("--portable", action="store_true", 
                   help="Create a portable single-file executable")
options = parser.parse_args()

# Platform-specific configuration
system = platform.system()
app_name = "TriggerEditor" if system == "Windows" else "TriggerEditor"

# Icon configuration
icon_path = None
if system == "Windows":
    icon_path = "src/trigger_designer/resources/TriEditorLogo.ico"
elif system == "Darwin":
    icon_path = "src/trigger_designer/resources/TriEditorLogo.ico"

# Verify icon exists
if icon_path and not Path(icon_path).exists():
    print(f"Warning: Icon file not found at {icon_path}")
    icon_path = None


# Analysis configuration
analysis = Analysis(
    # Entry point
    ["src/trigger_designer/main.py"],
    
    # Path configuration
    pathex=[],
    
    # Binary files
    binaries=[],
    
    # Data files to include
    datas=[("src/trigger_designer", "trigger_designer")],
    
    # Hidden imports (modules PyInstaller might miss)
    hiddenimports=[
        # Core data processing
        "pandas",
        "numpy", 
        "polars",
        "duckdb",
        
        # GUI frameworks
        "qtpy",
        "qtpy.QtCore",
        "qtpy.QtGui", 
        "qtpy.QtWidgets",
        
        # Visualization
        "matplotlib",
        "matplotlib.backends.backend_qt5agg",
        "seaborn",
        
        # Other dependencies
        "loguru",
        "psutil",
        "orjson",
    ],
    
    # PyInstaller hooks
    hookspath=[],
    hooksconfig={},
    
    # Modules to exclude
    excludes=[
        "tkinter",
        "unittest",
        "test",
        "_pytest",
    ],
    
    # Runtime hooks
    runtime_hooks=["log_dist.py"] if Path("log_dist.py").exists() else [],
    
    # Build options
    noarchive=False,
    optimize=0,
)

# Python bytecode archive
pyz = PYZ(analysis.pure)

# Executable configuration
include_files = [analysis.scripts]
if options.portable:
    include_files += (analysis.binaries, analysis.datas)

executable = EXE(
    pyz,
    *include_files,
    [],
    
    # Bootloader options
    bootloader_ignore_signals=False,
    console=False,
    hide_console="hide-early",
    disable_windowed_traceback=False,
    
    # Debug and optimization
    debug=True,
    strip=False,
    upx=True,
    upx_exclude=[],
    
    # Executable properties  
    name=app_name,
    icon=icon_path,
    exclude_binaries=not options.portable,
    
    # Platform options
    argv_emulation=False,
    target_arch=None,
    runtime_tmpdir=None,
    
    # Code signing (for macOS)
    codesign_identity=None,
    entitlements_file=None,
)

# Collection (for non-portable builds)
collection = (
    None if options.portable
    else COLLECT(
        executable,
        analysis.binaries, 
        analysis.datas,
        name=app_name,
        strip=False,
        upx=True,
        upx_exclude=[],
    )
)

# macOS app bundle (only for macOS builds)
if system == "Darwin":
    app_bundle = BUNDLE(
        executable if collection is None else collection,
        name=f"{app_name}.app",
        icon=icon_path,
        bundle_identifier="com.trigger.designer",
        version="0.0.1",
        info_plist={
            "CFBundleName": "Trigger Designer",
            "CFBundleDisplayName": "Trigger Designer", 
            "CFBundleGetInfoString": "Trigger Designer - Visual Data Processing Tool",
            "CFBundleIdentifier": "com.trigger.designer",
            "CFBundleVersion": "0.0.1",
            "CFBundleShortVersionString": "0.0.1",
            "NSAppleScriptEnabled": False,
            "NSPrincipalClass": "NSApplication",
            "NSHighResolutionCapable": True,
        },
    )

# vi: ft=python