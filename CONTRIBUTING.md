# Contributing to TriggerEditor

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Prerequisites**: Python 3.13.12+, [uv](https://github.com/astral-sh/uv), [pre-commit](https://pre-commit.com/)
2. **Clone and install**:
   ```bash
   git clone https://github.com/AzadKshitij/TriggerEditor.git
   cd TriggerEditor
   uv sync
   uv run pre-commit install
   ```

## Project Layout

- `src/trigger_designer/` — Main application source code
- `tests/unit/` — Unit tests
- `tests/integration/` — Integration tests and demos
- `docs/` — Documentation
- `scripts/` — Build scripts and utilities
- `data/` — Test data files
- `savedfiles/` — Sample workflow files

## Running Tests

```bash
uv run --project . pytest tests/
```

## Code Style

- **Formatter**: Ruff (line length 88)
- **Linter**: Ruff
- **Type checking**: ty
- Run formatting: `uv run --project . ruff format .`
- Run linting: `uv run --project . ruff check .`
- Run type checking: `uv run --project . ty check`
- Install hooks: `uv run --project . pre-commit install`
- Run hooks manually: `uv run --project . pre-commit run --all-files`

## Adding a New Node

1. Create a new file in the appropriate `src/trigger_designer/qt/widgets/nodes/<Category>/` folder
2. Inherit from the base node content class
3. Register the node type in `src/trigger_designer/core/node_configuration.py`
4. Add tests in `tests/unit/`

## Pull Request Guidelines

- Keep PRs focused on a single change
- Add tests for new functionality
- Update documentation if needed
- Ensure all tests pass before submitting
