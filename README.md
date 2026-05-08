# TriggerEditor

A visual data processing tool with a node-based workflow editor. Build complex data pipelines by dragging, dropping, and connecting nodes — no coding required.

## Features

- **Node-based visual editor** — drag nodes onto a canvas and connect them to create workflows
- **Multiple document interface** — work on several workflows simultaneously
- **Rich node library** — input/output, data preparation, joins, transforms, and reporting nodes
- **Polars + pandas backends** — high-performance data processing with lazy evaluation
- **Data preview** — inspect data at any point in your pipeline
- **SQL formula editor** — write SQL expressions for custom transformations
- **Data cleansing** — null handling, whitespace trimming, case normalization, and more
- **Execution engine** — timeout protection, memory limits, and execution statistics
- **Global logging** — centralized logging with per-window log isolation and level filtering

## Quick Start

### Prerequisites

- Python 3.13.12+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/AzadKshitij/TriggerEditor.git
cd TriggerEditor

# Install dependencies with uv
uv sync

# Install the pre-commit hook
uv run pre-commit install
```

### Running

```bash
# Run the application
uv run --project . src/trigger_designer/main.py

# Or with a workflow file
uv run --project . src/trigger_designer/main.py savedfiles/example.tds
```

Logs and terminal output are mirrored to `logs/trigger_designer_<timestamp>.log`, including uncaught Python tracebacks.

## Project Structure

```
TriggerEditor/
├── src/trigger_designer/       # Main application source
│   ├── main.py                 # Entry point
│   ├── core/                   # Core business logic
│   │   ├── ExecutionCheck/     # Node execution engine
│   │   ├── node_configuration.py  # Node type registry
│   │   └── utils/              # Utilities (cleansing, etc.)
│   ├── qt/                     # GUI layer (PyQt6)
│   │   ├── main_window.py      # Main application window
│   │   ├── design_window.py    # Workflow design canvas
│   │   ├── node_base.py        # Base node class
│   │   ├── docks/              # Dock widgets (logging, nodes list)
│   │   ├── helpers/            # Mixins (actions, UI, signals)
│   │   ├── models/             # Data models and dialogs
│   │   └── widgets/            # Custom widgets and node implementations
│   │       └── nodes/          # Node types (InOut, Preparation, Join, etc.)
│   ├── qss/                    # Stylesheets
│   └── resources/              # Icons and assets
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── docs/                       # Documentation
├── examples/                   # Example workflows and scripts
├── scripts/                    # Build and utility scripts
├── savedfiles/                 # Sample workflow files (.tds)
├── data/                       # Test data files
├── pyproject.toml              # Project configuration
└── trigger.spec                # PyInstaller build spec
```

## Available Nodes

| Category | Nodes |
|----------|-------|
| **Input/Output** | File Input, File Output, Text Output |
| **Preparation** | Select, Filter, Formula, Sort, Unique, Split, Cleansing, Group By, Dynamic Row Builder |
| **Join** | Join, Append, Union, Find & Replace |
| **Transform** | Transpose, Running Total, Count Records |
| **Report** | Table, Graph, Image |
| **Documentation** | Comment, Container |

## Editor Controls

- **Scroll** — pan vertically
- **Shift + Scroll** — pan horizontally
- **Ctrl + Scroll** — zoom in/out
- **Ctrl + drag** — snap to socket
- **Ctrl + draw over edges** — delete connections

## Building

```bash
# Build executable with PyInstaller
scripts/build.bat
```

## Contributing

Contributions are welcome! Please see the [docs/](docs/) folder for development notes, feature plans, and architecture details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

MIT
