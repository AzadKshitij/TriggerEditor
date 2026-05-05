# TriggerEditor (TriggerDesigner)

TriggerEditor (also referenced as TriggerDesigner) is a visual data-processing application with a node-based workflow editor built in Python. It is designed for fast, interactive data cleansing, transformation, preview and exploration using modern data libraries (Polars, DuckDB, Pandas) together with a PyQt6 GUI and a node-editor UI.

---

## Key features

- Node-based visual workflow editor for composing data transformations.
- Fast data processing using Polars, DuckDB, NumPy and Pandas.
- File I/O helpers for Excel, CSV, JSON and common formats.
- Enhanced executor architecture for safe, incremental execution and previews.
- Global logging plus a docked logging UI (configurable sinks).
- Example and test scripts to illustrate usage and debugging patterns.

---

## Table of contents

- [Quick start](#quick-start)
- [Requirements](#requirements)
- [Install](#install)
- [Run / Usage](#run--usage)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Development](#development)
- [Documentation & guides](#documentation--guides)
- [Contributing](#contributing)
- [License & contact](#license--contact)
- [Notes and troubleshooting](#notes-and-troubleshooting)

---

## Quick start

1. Clone the repo:

   git clone https://github.com/AzadKshitij/TriggerEditor.git
   cd TriggerEditor

2. Create and activate a Python 3.11 virtual environment:

   python -m venv .venv
   # macOS / Linux
   source .venv/bin/activate
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   # Windows (cmd)
   .\.venv\Scripts\activate.bat

3. Upgrade pip and install the package with development dependencies:

   python -m pip install --upgrade pip
   python -m pip install -e .[dev]

---

## Requirements

- Python >= 3.11
- Git (to fetch the node editor git dependency)
- Build tools (if you plan to build wheels or use pyinstaller)

Primary runtime dependencies (declared in `pyproject.toml`):
Polars (with pyarrow), Pandas, NumPy, DuckDB, PyQt6, qtpy, nodeeditor (git), matplotlib, seaborn, pillow, numba, loguru, click, colorama and others. See `pyproject.toml` for exact versions.

---

## Install

Install via pip in editable mode (recommended for development):

python -m pip install -e .[dev]

Notes:
- The project references a git-based node editor source (see `pyproject.toml`). Ensure git is available and reachable when installing dependencies.
- If you don't need development tools, install just the package dependencies (or create a trimmed requirements list).

---

## Run / Usage

This repository contains multiple scripts and example/test files. There is no single packaged launcher in the repository root; to explore:

- Inspect example or demo scripts (filenames beginning with `demo_` / `test_`).
- Open the `src/` directory to identify the main application or add a CLI/entry point to `pyproject.toml` for launching the GUI.
- Example test and utility files include:
  - `demo_enhanced_preview.py` (demo)
  - `check_output.py`, `Compare.py` (utilities)
  - Several `test_*` files that exercise logging, preview, and Polars integration.

If you add a GUI entrypoint (for example `src/trigger_editor/__main__.py` or a console script), you can run the app with `python -m trigger_editor` or configure an entry point in `pyproject.toml`.

---

## Testing

Run the test suite with pytest:

python -m pip install -e .[dev]
python -m pytest -q

Tests in the repo include:
- `test_global_logging.py`
- `test_logging_dock.py`
- `test_polars_preview.py`
- Additional tests under `tests/` (when present)

---

## Project layout (important files/folders)

- src/ — primary source code (GUI, node editor, execution engine)
- docs/ — additional docs and design notes
- examples/ — example flows or scripts
- tests/ — test suite
- ENHANCED_EXECUTOR_GUIDE.md — design and usage of the enhanced executor
- GLOBAL_LOGGING_README.md — global logging system description
- LOGGING_DOCK_README.md — logging dock usage and internals
- trigger.spec — packaging/spec file (used by PyInstaller or build process)
- pyproject.toml — metadata, dependency and tooling configuration

---

## Development

- Formatting: black
- Linting: ruff
- Type checks: mypy (config in `pyproject.toml`)
- Packaging/build: the repository uses `pyproject.toml` and supports common tools (pip, build). A `uv` tool configuration is present for fetching the nodeeditor git dependency.
- To build a standalone executable, pyinstaller is listed in dev-dependencies and can be used with `trigger.spec` (adjust paths as needed).

Recommended workflow:
1. Create a feature branch from main.
2. Run tests, formatters and linters locally.
3. Open a PR with descriptive title and changelog.

---

## Documentation & guides

Start with the in-repo guides:
- `ENHANCED_EXECUTOR_GUIDE.md` — enhanced executor design and usage
- `GLOBAL_LOGGING_README.md` — global logging architecture
- `LOGGING_DOCK_README.md` — logging dock integration and sinks

Use these for implementation details and to understand execution and logging internals.

---

## Contributing

Contributions are welcome. Suggested process:
1. Fork and branch
2. Run tests and linters locally
3. Open a pull request describing the change and rationale
4. Add tests for bug fixes or new features where applicable

Please follow existing code formatting and typing conventions. If you need help with architecture-level changes (for example the node editor integration or the executor model) open an issue or a design PR first.

---

## License & contact

This project is licensed under the MIT License. See the LICENSE file for details.

Author / maintainer:
- Azad Kshitij — azadkshitij08302001@gmail

---

## Notes and troubleshooting

- Node editor dependency is referenced as a git source; installations without git or with restricted network access may fail.
- The GUI depends on PyQt6 — some systems require additional platform packages or Qt runtime components.
- If installation of binary dependencies (numba, llvmlite, polars, etc.) fails, consider using a platform-appropriate wheel or a Conda environment.
- If you want, I can:
  - Add a runnable GUI entrypoint and example flow,
  - Create a requirements/dev-requirements file,
  - Or update the README directly in the repo for you.

---

Thank you for checking out TriggerEditor — if you'd like, I can commit this README.md to the repository for you now or make adjustments (shorter, more tutorial-style, or adding badges/screenshots).
