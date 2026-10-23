<#
.SYNOPSIS
Overlay a local qtpy-nodeeditor checkout over the installed nodeeditor.

.DESCRIPTION
The venv gets `nodeeditor-qtpy` from PyPI, pinned in pyproject.toml and
uv.lock. This script is the dev-loop shortcut for the window *before* a canvas
change is published: edit the sibling checkout, run this, and test the change
without a commit or a release.

It copies the edited files over the installed package, so the two diverge
until the next `uv sync` (which restores the locked PyPI version) or a new
release. Re-run scripts/build.bat to build against the published package
instead.

Note it installs with --no-deps if nodeeditor is missing, because resolving
nodeeditor's deps would touch the Qt versions this project pins.

Any files you edit upstream should be added to $Files below.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Projects\qtpy-nodeeditor'
)

$Source = Join-Path $ProjectRoot 'nodeeditor'

$ErrorActionPreference = 'Stop'

# Files edited in the upstream checkout. The package is installed from a
# pinned release, so anything changed here has to be copied across; keep
# this list in step with the changes.
$Files = @(
    'node_scene_history.py'
    'node_scene.py'
    'node_content_widget.py'
    'node_editor_window.py'
    # canvas interactivity (pan/zoom/drag) performance work
    'node_graphics_view.py'
    'node_graphics_scene.py'
    'node_graphics_node.py'
    'node_icon_graphics_node.py'
    'node_icon_content_widget.py'
    'node_graphics_edge.py'
    'node_graphics_socket.py'
    'node_node.py'
)

$dest = Join-Path $PSScriptRoot '..\.venv\Lib\site-packages\nodeeditor'

if (-not (Test-Path $Source)) {
    throw "nodeeditor package not found at $Source"
}

if (-not (Test-Path $dest)) {
    # `uv sync` prunes nodeeditor if it is missing from the lock. Install
    # it the same way scripts/build.bat does before copying the edits over.
    Write-Host 'nodeeditor missing from .venv - installing from the local checkout'
    $python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
    # --no-deps keeps uv from touching the pinned Qt versions this project
    # sets (pyqt6, pyqt6-qt6, pyqt6-sip). nodeeditor's own floor
    # (qtpy>=2.4.3) is already satisfied by the locked qtpy.
    & uv pip install --python $python --no-deps --no-build-isolation $ProjectRoot
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
Write-Host 'Run `uv sync --all-groups` to restore the locked PyPI version.'
