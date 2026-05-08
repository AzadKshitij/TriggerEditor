@REM Run script for TriggerEditor
@REM Usage: scripts\run.bat [self|comp]
@REM Navigate to project root
@REM @cd /d "%~dp0.."
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
	echo ERROR: uv not found. Please install it first.
	echo Visit: https://github.com/astral-sh/uv
	exit /b 1
)
@echo %1
IF "%1" == "self" GOTO SELF
IF "%1" == "comp" GOTO COMP
GOTO End1

:SELF
uv run --project . src\trigger_designer\main.py "C:\Projects\TriggerEditor\savedfiles\0. All Node- Test.tds"
GOTO :EOF

:COMP
uv run --project . src\trigger_designer\main.py "C:\Users\KASHVINCHANDRASAN\Desktop\Personal\Github\TriggerEditor\savedfiles\0. All Node- Test.tds"
GOTO :EOF

:End1
uv run --project . src\trigger_designer\main.py 
GOTO :EOF