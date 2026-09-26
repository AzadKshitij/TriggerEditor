<#
.SYNOPSIS
Copy locally-modified qtpy-nodeeditor files into the project venv.

.DESCRIPTION
scripts/build.bat installs nodeeditor from the upstream `main` branch, so the
venv only sees what has been committed and pushed. This script is the dev-loop
shortcut for the window *before* that: edit the sibling checkout, run this, and
test the change without a commit.

Once the change is pushed, re-run scripts/build.bat (or set QTNODEEDITOR_REF to
the new SHA) instead - this script will be overwritten by that install.

Note it installs with --no-deps if nodeeditor is missing, because nodeeditor's
metadata asks for newer pyqt6/qtpy than this project pins. Resolving its deps
would silently upgrade Qt.

Any files you edit upstream should be added to $Files below.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Projects\qtpy-nodeeditor'
)

$Source = Join-Path $ProjectRoot 'nodeeditor'

$ErrorActionPreference = 'Stop'

# Files edited in the upstream checkout. The package is installed from a
# pinned git commit, so anything changed here has to be copied across; keep
# this list in step with the changes.
$Files = @(
    'node_scene_history.py'
    'node_scene.py'
    'node_content_widget.py'
    'node_editor_window.py'
)

$dest = Join-Path $PSScriptRoot '..\.venv\Lib\site-packages\nodeeditor'

if (-not (Test-Path $Source)) {
    throw "nodeeditor package not found at $Source"
}

if (-not (Test-Path $dest)) {
    # `uv sync` prunes nodeeditor because it is absent from the lock. Install
    # it the same way scripts/build.bat does before copying the edits over.
    Write-Host 'nodeeditor missing from .venv - installing from the local checkout'
    $python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
    # --no-deps matters: nodeeditor's metadata asks for newer pyqt6/qtpy than
    # this project pins, which is the whole reason it is kept out of the uv
    # lock (see pyproject.toml). Resolving its deps would silently upgrade Qt.
    & uv pip install --python $python --no-deps $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "failed to install nodeeditor from $ProjectRoot"
    }
}

foreach ($file in $Files) {
    $src = Join-Path $Source $file
    if (-not (Test-Path $src)) {
        throw "missing upstream file $src"
    }
    Copy-Item $src (Join-Path $dest $file) -Force
    Write-Host "synced $file"
}

# Stale bytecode would otherwise shadow the copies.
$pycache = Join-Path $dest '__pycache__'
if (Test-Path $pycache) {
    Get-ChildItem $pycache -Filter *.pyc | Remove-Item -Force
}

Write-Host 'nodeeditor in .venv now matches the local checkout.'
