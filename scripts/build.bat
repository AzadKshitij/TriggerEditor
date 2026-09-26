@echo off
REM Build script for TriggerEditor using PyInstaller
REM Usage: scripts\build.bat (run from project root)

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

REM Ensure git-only dependency (kept out of uv lock: its metadata wants newer Qt)
uv run --project . python -c "import nodeeditor" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing qtpy-nodeeditor from git...
    uv pip install "git+https://github.com/AzadKshitij/qtpy-nodeeditor.git@89c59958f13537143745660a9b750c9fffe53ad2"
    if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
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