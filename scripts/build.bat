@echo off
REM Build script for TriggerEditor using PyInstaller
REM Usage: scripts\build.bat (run from project root)

REM ---------------------------------------------------------------------------
REM qtpy-nodeeditor is installed straight from git and is deliberately kept out
REM of the uv lock: its metadata requires pyqt6>=6.11 / qtpy>=2.4.3, which would
REM upgrade the Qt versions this project pins (pyqt6==6.8.0, qtpy==2.4.2). That
REM is also why --no-deps is used below - resolving its dependencies silently
REM upgrades Qt.
REM
REM The ref is a branch, so a build picks up the latest nodeeditor. Set
REM QTNODEEDITOR_REF to a commit SHA for a reproducible build, e.g.
REM   set QTNODEEDITOR_REF=62583622e73404e5337956463f48ad63d3f41c89
REM ---------------------------------------------------------------------------
if "%QTNODEEDITOR_REF%"=="" set "QTNODEEDITOR_REF=main"
set "QTNODEEDITOR_URL=git+https://github.com/AzadKshitij/qtpy-nodeeditor.git@%QTNODEEDITOR_REF%"

REM Navigate to project root
cd /d "%~dp0.."

where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: uv not found. Please install it first.
    echo Visit: https://github.com/astral-sh/uv
    exit /b 1
)

echo Starting TriggerEditor build process...
echo.

REM Check if spec file exists
if not exist "trigger.spec" (
    echo ERROR: trigger.spec file not found.
    exit /b 1
)

REM Clean previous incremental build (keeps dist/*.exe until new build passes)
if exist "build\trigger" rmdir /s /q "build\trigger"

REM Refresh qtpy-nodeeditor from %QTNODEEDITOR_REF%. --reinstall is what makes
REM "latest" mean latest: without it uv sees the same requirement spec as already
REM satisfied and keeps whatever was installed previously. --no-build-isolation
REM is required since nodeeditor's setup.py does `import nodeeditor` to read
REM __version__, which now imports qtpy (via node_colors_config) - an isolated
REM build env has no qtpy installed, so the build fails without this flag.
echo Installing qtpy-nodeeditor from %QTNODEEDITOR_REF%...
uv pip install --no-deps --no-build-isolation --reinstall "%QTNODEEDITOR_URL%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: failed to install qtpy-nodeeditor from %QTNODEEDITOR_REF%
    exit /b %ERRORLEVEL%
)

uv run --project . python -c "import nodeeditor; print('nodeeditor loaded from', nodeeditor.__file__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: nodeeditor was installed but cannot be imported.
    exit /b %ERRORLEVEL%
)

REM Smoke-check source imports before the slow bundle step
echo Verifying source imports...
uv run --project . python -c "import sys; sys.path.insert(0, 'src'); import trigger_designer.main; print('source import OK')"
if %ERRORLEVEL% NEQ 0 (
    echo Build aborted: source import check failed.
    exit /b %ERRORLEVEL%
)

REM Run PyInstaller (onedir default; add -- --portable for single-file)
echo Running PyInstaller with trigger.spec...
uv run --project . pyinstaller --clean trigger.spec -y %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build failed with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

REM Verify bundle assets
if not exist "dist\TriggerEditor\TriggerEditor.exe" (
    echo Build failed: dist\TriggerEditor\TriggerEditor.exe missing.
    exit /b 1
)
if not exist "dist\TriggerEditor\_internal\trigger_designer\resources.json" (
    if not exist "dist\TriggerEditor\_internal\trigger_designer\qt\resources.json" (
        echo WARNING: resource map not found in bundle; check datas in trigger.spec.
    )
)
if not exist "dist\TriggerEditor\_internal\trigger_designer\resources\qt\themes\base.qss" (
    echo WARNING: theme assets missing in bundle; check datas in trigger.spec.
)

echo.
echo Build completed successfully.
echo Launch dist\TriggerEditor\TriggerEditor.exe to smoke-test, then compile
echo the installer with Inno Setup on savedfiles\TriggerDesigner_Setup.iss
