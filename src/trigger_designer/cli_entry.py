"""PyInstaller entry point of ``trigger-designer-cli.exe`` (plan 08 S11)."""

import sys

from trigger_designer.cli import main

if __name__ == "__main__":
    sys.exit(main())
