@REM Watch source files and restart the app when they change
@REM Usage: scripts\watch.bat [arguments for the app, e.g. a .tds file]
@echo off
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
	echo ERROR: uv not found. Please install it first.
	echo Visit: https://github.com/astral-sh/uv
	exit /b 1
)
uv run --project "%~dp0.." python "%~dp0dev_watch.py" %*
