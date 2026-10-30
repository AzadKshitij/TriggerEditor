@echo off
REM Build script for TriggerEditor using PyInstaller
REM Usage: scripts\build.bat (run from project root)

REM ---------------------------------------------------------------------------
REM The node canvas is the `nodeeditor-qtpy` distribution on PyPI (the import
REM package is `nodeeditor`). It is pinned in pyproject.toml and locked in
REM uv.lock, so `uv sync` installs it like any other dependency - nothing is
REM installed from git and nothing has to be reinstalled by hand.
REM
REM For canvas work in a local clone of the upstream repo, run
REM scripts\sync-nodeeditor.ps1 instead of this script; it overlays the clone
REM over the installed copy.
REM ---------------------------------------------------------------------------

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

REM Install the locked dependencies (nodeeditor-qtpy included) and the app
REM itself, editable, into .venv. --frozen keeps uv.lock authoritative: a
REM stale lock fails the build instead of silently resolving new versions.
REM --all-groups keeps the profiling tools (py-spy, scalene, objgraph) installed.
echo Installing locked dependencies...
uv sync --frozen --all-groups
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: uv sync failed.
    exit /b %ERRORLEVEL%
)

REM --no-sync on every uv run below: the sync above already put the venv in
REM the state the build wants, and a second sync would prune the profiling
REM group that --all-groups just installed.
uv run --no-sync --project . python -c "import nodeeditor; print('nodeeditor loaded from', nodeeditor.__file__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: nodeeditor was installed but cannot be imported.
    exit /b %ERRORLEVEL%
)

REM Smoke-check source imports before the slow bundle step
echo Verifying source imports...
uv run --no-sync --project . python -c "import sys; sys.path.insert(0, 'src'); import trigger_designer.main; print('source import OK')"
if %ERRORLEVEL% NEQ 0 (
    echo Build aborted: source import check failed.
    exit /b %ERRORLEVEL%
)

REM Run PyInstaller (onedir default; add -- --portable for single-file)
echo Running PyInstaller with trigger.spec...
uv run --no-sync --project . pyinstaller --clean trigger.spec -y %*
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

if not exist "dist\TriggerEditor\trigger-designer-cli.exe" (
    echo Build failed: dist\TriggerEditor\trigger-designer-cli.exe missing.
    exit /b 1
)
"dist\TriggerEditor\trigger-designer-cli.exe" --version
if %ERRORLEVEL% NEQ 0 (
    echo Build failed: the command-line program does not start.
    exit /b 1
)
"dist\TriggerEditor\trigger-designer-cli.exe" validate "savedfiles\0. All Node- Test.tds" --deep --no-files
if %ERRORLEVEL% NEQ 0 (
    echo Build failed: deep validation of the sample workflow failed.
    exit /b 1
)

echo.
echo Build completed successfully.
echo Launch dist\TriggerEditor\TriggerEditor.exe to smoke-test, then compile
echo the installer with Inno Setup on savedfiles\TriggerDesigner_Setup.iss
