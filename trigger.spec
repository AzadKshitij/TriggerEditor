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
app_name = "TriggerEditor"

# Icon configuration
icon_path = None
if system in {"Windows", "Darwin"}:
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
    
    # Data files to include.
    #
    # Do not copy the whole package: it contains developer-only material
    # (`.opencode/`, examples, qss sources, generated rc modules) that bloats
    # the bundle by ~65 MB. Only the files read at runtime belong here.
    datas=[
        ("src/trigger_designer/qt/resources.json", "trigger_designer/qt"),
        ("src/trigger_designer/resources/qt", "trigger_designer/resources/qt"),
        ("src/trigger_designer/resources/Icon.ico", "trigger_designer/resources"),
        ("src/trigger_designer/resources/splash.png", "trigger_designer/resources"),
    ],
    
    # Hidden imports (modules PyInstaller might miss)
    hiddenimports=[
        # Core data processing
        "numpy",
        "polars",
        # Polars imports pyarrow lazily; DuckDB's register() needs it for
        # Polars -> Arrow conversion, so PyInstaller must not miss it.
        "pyarrow",
        "duckdb",
        "fastexcel",
        "openpyxl",
        "PIL",
        "PIL.ImageQt",

        # GUI frameworks
        "qtpy",
        "qtpy.QtCore",
        "qtpy.QtGui",
        "qtpy.QtWidgets",
        "PyQt6.sip",

        # Visualization (qtagg is the Qt6 backend; keep qt5agg alias harmless)
        "matplotlib",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt5agg",

        # Other dependencies
        "loguru",
        "psutil",
        "orjson",
    ],

    # PyInstaller hooks
    hookspath=[],
    hooksconfig={},

    # Modules to exclude (startup + size: never imported at runtime).
    # pandas/numba/llvmlite/numexpr/seaborn are not application dependencies.
    # pandas remains in the dev group for tests, so it can be installed in the
    # build venv without being bundled. pyarrow stays: DuckDB's register() uses
    # it for the Polars -> Arrow conversion behind Formula/Filter.
    excludes=[
        "tkinter",
        "unittest",
        "test",
        "_pytest",
        "pytest",
        "setuptools",
        "distutils",
        "matplotlib.tests",
        "matplotlib.testing",
        "numpy.tests",
        "numpy.f2py",
        "pandas",
        "pandas.tests",
        "numba",
        "llvmlite",
        "numexpr",
        "seaborn",
        "PIL.ImageTk",
    ],

    # Runtime hooks
    runtime_hooks=(
        ["scripts/log_dist.py"] if Path("scripts/log_dist.py").exists()
        else ["log_dist.py"] if Path("log_dist.py").exists()
        else []
    ),

    # Build options
    noarchive=False,
    optimize=1,
)


def _is_qt_bloat(entry) -> bool:
    """True for Qt translation files and the QtPdf module.

    None of these are imported by the app (no QtPdf/QtPrintSupport/QtWebEngine/
    QtQml anywhere under ``src``), but PyInstaller's Qt hook collects them
    anyway: ~6 MB of ``.qm`` and ~5 MB of ``Qt6Pdf.dll`` in a real build.
    Filtering the collected TOC is more robust than reaching into the hook.
    """
    for index in (0, 1):  # (dest, src) - check both, dest paths vary per OS
        if index >= len(entry):
            continue
        path = str(entry[index]).replace("\\", "/").lower()
        if "/translations/" in path and path.endswith(".qm"):
            return True
        if path.rsplit("/", 1)[-1] in {"qt6pdf.dll", "qt6pdfwidgets.dll", "qpdf.dll"}:
            return True
    return False


analysis.datas = [entry for entry in analysis.datas if not _is_qt_bloat(entry)]
analysis.binaries = [entry for entry in analysis.binaries if not _is_qt_bloat(entry)]

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
    
    # Debug and optimization (production: no debug console, no UPX —
    # UPX decompression + AV rescans cost more cold-start than they save)
    debug=False,
    strip=False,
    upx=False,
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
        upx=False,
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