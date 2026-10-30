"""PyInstaller spec file for TriggerEditor application."""

import platform
from argparse import ArgumentParser
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, MERGE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE
from PyInstaller.utils.hooks import collect_submodules

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


# Node modules cannot be reached by import analysis: ``nodes/__init__.py``
# registers each one as a lazy reference and ``LazyNodeReference.load()``
# imports it by string, so PyInstaller never sees them - nor the modules they
# import (``helpers.state_mixin``, ``widgets.select_table_widget``, ...).
# Their subpackages (InOut, Join, Preparation, ...) are PEP 420 namespace
# packages, which ``collect_submodules`` cannot enumerate, so list the sources
# explicitly. Hidden imports make the analysis walk the dependency tree; the
# data entries keep the tree resolvable on disk for the runtime string import
# and the ``os.walk`` sweep in ``nodes/__init__.py``.
_nodes_dir = Path("src/trigger_designer/qt/widgets/nodes")
node_module_datas = []
node_hiddenimports = []
for _path in sorted(_nodes_dir.rglob("*.py")):
    node_module_datas.append(
        (str(_path), _path.parent.relative_to("src").as_posix())
    )
    _parts = _path.relative_to("src").with_suffix("").parts
    if _parts[-1] == "__init__":
        _parts = _parts[:-1]
    node_hiddenimports.append(".".join(_parts))

# --- core hidden imports begin
# Qt-free core packages imported by string from exec'd generated code, importlib
# or plan modules (invisible to PyInstaller's static analysis). ``core/`` and its
# subpackages are PEP 420 namespace packages, so list the sources by file. A
# package that has not landed yet simply yields nothing.
_core_dir = Path("src/trigger_designer/core")
_CORE_PACKAGES = (
    "audit",
    "errors",
    "excel",
    "workpaper",
    "shaping",
    "headless",
    "utils",
)
_CORE_MODULES = (
    "inputs",
    "input_source",
    "profile",
    "profile_report",
    "sql_guard",
    "codegen_safe",
)
core_hiddenimports = []
for _pkg in _CORE_PACKAGES:
    for _path in sorted((_core_dir / _pkg).rglob("*.py")):
        _parts = _path.relative_to("src").with_suffix("").parts
        core_hiddenimports.append(
            ".".join(_parts[:-1] if _parts[-1] == "__init__" else _parts)
        )
for _name in _CORE_MODULES:
    if (_core_dir / f"{_name}.py").exists():
        core_hiddenimports.append(f"trigger_designer.core.{_name}")
core_hiddenimports += ["xlsxwriter", "pyarrow.parquet", "trigger_designer.cli"]
core_hiddenimports += collect_submodules("xlsxwriter")
# --- core hidden imports end

gui_datas = [
    ("src/trigger_designer/qt/resources.json", "trigger_designer/qt"),
    ("src/trigger_designer/resources/qt", "trigger_designer/resources/qt"),
    ("src/trigger_designer/resources/Icon.ico", "trigger_designer/resources"),
    ("src/trigger_designer/resources/splash.png", "trigger_designer/resources"),
] + node_module_datas

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
    # the bundle by ~65 MB. Only the files read at runtime belong here, plus
    # the node sources listed above.
    datas=gui_datas,
    
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

        # Material Symbols: the style/size modules are imported by name at
        # runtime (importlib), so PyInstaller cannot see them.
        "qt_material_icons",
        "qt_material_icons.resources.icons_outlined_20",

        # GUI frameworks. PySide6 ships its Qt DLLs inside the wheel and
        # PyInstaller's hook collects them; shiboken6 is the binding core.
        "qtpy",
        "qtpy.QtCore",
        "qtpy.QtGui",
        "qtpy.QtWidgets",
        "PySide6",
        "shiboken6",

        # Visualization (qtagg is the Qt6 backend; keep qt5agg alias harmless)
        "matplotlib",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt5agg",

        # Other dependencies
        "loguru",
        "psutil",
        "orjson",
    ]
    + node_hiddenimports
    + core_hiddenimports,

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

# Command-line twin (plan 08 S11): a console program beside the GUI exe. It
# reuses the GUI's hidden imports and data so the same nodes resolve, and MERGE
# lets the two share every DLL, so the CLI adds only a few MB. The portable
# single-file build stays GUI-only.
cli_analysis = None
if not options.portable:
    cli_analysis = Analysis(
        ["src/trigger_designer/cli_entry.py"],
        pathex=[],
        binaries=[],
        datas=list(gui_datas),
        hiddenimports=list(analysis.hiddenimports) + ["trigger_designer.qt.headless"],
        hookspath=[],
        hooksconfig={},
        excludes=list(analysis.excludes),
        runtime_hooks=[],
        noarchive=False,
        optimize=1,
    )
    cli_analysis.binaries = [e for e in cli_analysis.binaries if not _is_qt_bloat(e)]
    cli_analysis.datas = [e for e in cli_analysis.datas if not _is_qt_bloat(e)]
    MERGE(
        (analysis, "main", app_name),
        (cli_analysis, "cli_entry", "trigger-designer-cli"),
    )
else:
    print("Note: the portable build does not include trigger-designer-cli.")

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

cli_executable = None
if cli_analysis is not None:
    cli_executable = EXE(
        PYZ(cli_analysis.pure),
        cli_analysis.scripts,
        [],
        bootloader_ignore_signals=False,
        console=True,
        debug=False,
        strip=False,
        upx=False,
        name="trigger-designer-cli",
        icon=icon_path,
        exclude_binaries=True,
        argv_emulation=False,
        target_arch=None,
    )

# Collection (for non-portable builds)
collection = (
    None if options.portable
    else COLLECT(
        executable,
        cli_executable,
        analysis.binaries + cli_analysis.binaries,
        analysis.datas + cli_analysis.datas,
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