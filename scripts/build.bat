@echo off
REM Build script for TriggerEditor using PyInstaller
REM Usage: scripts\build.bat (run from project root)
REM         scripts\build.bat -- --folder    onedir build, packaged as a folder zip
REM         scripts\build.bat -- --portable  single-file build, packaged as a portable zip
REM         scripts\build.bat -- --both      onedir first, then the single-file build
REM The single-file build carries its whole payload in one exe, so it extracts
REM to a temp directory on every launch and starts noticeably slower. The
REM folder build starts from already-unpacked files and is the fastest option.

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
REM --all-groups used to pull in the profiling group too, but its setuptools
REM build chain conflicts with PyInstaller's distutils hook and fails the
REM build with a "distutils already imported as ExcludedModule" error.
echo Installing locked dependencies...
uv sync --frozen --dev
if %ERRORLEVEL% NEQ 0 (
	echo ERROR: uv sync failed.
	exit /b %ERRORLEVEL%
)

REM PyInstaller mode. The single-file build passes -- --portable to the spec,
REM which reads sys.argv; extra flags must not leak into the spec parser.
set "MODE=onedir"
echo %* | findstr /C:"--portable" >nul && set "MODE=portable"
echo %* | findstr /C:"--both" >nul && set "MODE=both"

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

if "%MODE%"=="portable" (
	echo Running PyInstaller for the single-file build...
	uv run --no-sync --project . pyinstaller --clean trigger.spec -y -- --portable
) else (
	echo Running PyInstaller for the folder build...
	uv run --no-sync --project . pyinstaller --clean trigger.spec -y
)
if %ERRORLEVEL% NEQ 0 (
	echo.
	echo Build failed with error code %ERRORLEVEL%
	exit /b %ERRORLEVEL%
)

if "%MODE%"=="portable" goto VerifyPortable

REM Verify the folder build. The onedir layout writes dist\TriggerEditor\
REM with the CLI beside the GUI.
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
echo Packaging the folder build...
uv run --no-sync --project . python scripts\package_windows.py --layout folder
if %ERRORLEVEL% NEQ 0 (
	echo Build failed: could not package dist\TriggerEditor.
	exit /b 1
)
if "%MODE%"=="both" (
	echo.
	echo Building the single-file edition as well...
	goto BuildPortable
)
echo.
echo Folder build completed successfully.
echo dist\TriggerEditor starts fastest - no temp extraction at launch.
echo Run scripts\build.bat -- --both to also build the single-file edition.
exit /b 0

:BuildPortable
uv sync --frozen --dev
if %ERRORLEVEL% NEQ 0 (
	echo ERROR: uv sync failed.
	exit /b %ERRORLEVEL%
)
uv run --no-sync --project . pyinstaller --clean trigger.spec -y -- --portable
if %ERRORLEVEL% NEQ 0 (
	echo.
	echo Portable build failed with error code %ERRORLEVEL%
	exit /b %ERRORLEVEL%
)

:VerifyPortable
if not exist "dist\TriggerEditor.exe" (
	echo Build failed: dist\TriggerEditor.exe missing.
	exit /b 1
)
echo.
echo Packaging the single-file build...
uv run --no-sync --project . python scripts\package_windows.py --layout portable
if %ERRORLEVEL% NEQ 0 (
	echo Build failed: could not package dist\TriggerEditor.exe.
	exit /b 1
)
echo.
echo Portable build completed successfully: dist\TriggerEditor.exe
echo The single-file build is GUI-only; it does not include trigger-designer-cli.
exit /b 0
