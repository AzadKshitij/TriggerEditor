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

REM Run PyInstaller
echo Running PyInstaller with trigger.spec...
uv run --project . pyinstaller --clean trigger.spec -y

REM Check build result
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Build completed successfully!
    echo Built executable can be found in the dist/ folder
) else (
    echo.
    echo ❌ Build failed with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

pause