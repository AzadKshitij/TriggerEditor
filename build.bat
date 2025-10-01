@echo off
REM Build script for TriggerEditor using PyInstaller
REM Usage: build.bat [options]

echo Starting TriggerEditor build process...
echo.

REM Check if PyInstaller is available
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller not found. Please install it first.
    echo Run: pip install pyinstaller
    exit /b 1
)

REM Check if spec file exists
if not exist "trigger.spec" (
    echo ERROR: trigger.spec file not found.
    exit /b 1
)

REM Run PyInstaller
echo Running PyInstaller with trigger.spec...
pyinstaller --clean trigger.spec -y

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