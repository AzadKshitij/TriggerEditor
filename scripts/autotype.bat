@echo off
REM Autotyping script for TriggerEditor
REM This script runs autotyping to automatically add type annotations
REM Usage: scripts\autotype.bat [file_or_directory]

REM Navigate to project root
cd /d "%~dp0.."

echo Running autotyping for TriggerEditor...
echo.

REM Check if uv is available
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: uv not found. Please install it first.
    echo Visit: https://github.com/astral-sh/uv
    exit /b 1
)

REM Run autotyping with optimized settings
echo Applying type annotations...
uv run autotyping --annotate-optional parent:qtpy.QtWidgets.QWidget --aggressive %*

REM Check result
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Autotyping completed successfully!
) else (
    echo.
    echo ❌ Autotyping failed with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

REM Alternative configuration (commented out):
REM uv run autotyping --none-return --scalar-return --bool-param --int-param --float-param --str-param --bytes-param --guess-common-names %*