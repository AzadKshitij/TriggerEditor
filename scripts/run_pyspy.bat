@echo off
REM ============================================================
REM  py-spy flamegraph profiler for TriggerEditor
REM  Requires: uv sync --group profiling
REM
REM  IMPORTANT: On Windows, py-spy needs to be run as Administrator
REM  to attach to processes. Right-click this .bat and choose
REM  "Run as administrator", OR use the --nonblocking flag (below).
REM
REM  Usage:
REM    run_pyspy.bat              -- profile entire session
REM    run_pyspy.bat file.tds     -- open a .tds file on launch
REM ============================================================

setlocal

REM Build timestamp (YYYYMMDD_HHMMSS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set TIMESTAMP=%DT:~0,8%_%DT:~8,6%

if not exist profiles mkdir profiles

set SVG_OUT=profiles\pyspy_%TIMESTAMP%.svg
set SPD_OUT=profiles\pyspy_%TIMESTAMP%.speedscope.json

echo ============================================================
echo  py-spy Flamegraph Profiler
echo ============================================================
echo  SVG  output : %SVG_OUT%
echo  JSON output : %SPD_OUT%
echo.
echo  The app will launch. Use it normally, then CLOSE the window.
echo  py-spy generates the flamegraph after the process exits.
echo ============================================================
echo.

REM --- SVG flamegraph (opens directly in browser) ---
echo [1/2] Recording SVG flamegraph...
uv run --group profiling py-spy record ^
    --output %SVG_OUT% ^
    --format flamegraph ^
    --native ^
    -- python src/trigger_designer/main.py %1

if errorlevel 1 (
    echo.
    echo  ERROR: py-spy failed. Common fixes:
    echo    - Run this script as Administrator
    echo    - Remove --native flag if no C extensions to profile
    echo    - Try:  py-spy record --output %SVG_OUT% -- python src/trigger_designer/main.py
    goto :done
)

echo.
echo [2/2] Recording Speedscope JSON (alternative viewer)...
uv run --group profiling py-spy record ^
    --output %SPD_OUT% ^
    --format speedscope ^
    -- python src/trigger_designer/main.py %1

echo.
echo ============================================================
echo  Done! Open your flamegraph:
echo.
echo  SVG  (open in any browser):
echo    start %SVG_OUT%
echo.
echo  Speedscope (interactive, richer UI):
echo    1. Go to https://www.speedscope.app
echo    2. Drag-and-drop:  %SPD_OUT%
echo ============================================================

REM Auto-open the SVG
start "" "%SVG_OUT%"

:done
endlocal
pause
