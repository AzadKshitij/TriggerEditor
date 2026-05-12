"""
Enhanced Data Preview Window using Polars Table Viewer

This module provides an improved data preview window that uses the memory-efficient
Polars table viewer for better performance with large datasets.
"""

from qtpy.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
)
from qtpy.QtCore import Qt
import polars as pl
import numpy as np
from typing import Any, Union
from .polars_table_viewer import PolarsTableViewer
from loguru import logger
