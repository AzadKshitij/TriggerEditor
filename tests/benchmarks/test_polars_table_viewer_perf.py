"""Performance and memory benchmarks for the Polars table viewer.

Opt in with ``pytest --run-benchmarks``; the default suite is about behaviour,
not about the machine it happens to run on.
"""

from __future__ import annotations

import time
import unittest

import numpy as np
import polars as pl
import psutil
from qtpy.QtCore import Qt

from trigger_designer.qt.models.polars_table_viewer import PolarsTableModel


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests."""

    def setUp(self):
        """Set up performance test fixtures."""
        self.benchmark_sizes = [1000, 10000, 100000]
        self.results: dict[str, list[float]] = {}

    def _benchmark_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """Benchmark an operation and record results."""
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        end_time = time.time()

        execution_time = end_time - start_time

        if operation_name not in self.results:
            self.results[operation_name] = []
        self.results[operation_name].append(execution_time)

        return result, execution_time

    def test_dataframe_creation_performance(self):
        """Benchmark dataframe creation with different sizes."""
        for size in self.benchmark_sizes:
            _, exec_time = self._benchmark_operation(
                f"create_df_{size}", self._create_benchmark_dataframe, size
            )

            print(f"Created {size:,} row dataframe in {exec_time:.3f}s")
            # Should complete within 10 seconds
            self.assertLess(exec_time, 10.0)

    def test_model_initialization_performance(self):
        """Benchmark model initialization with different sizes."""
        for size in self.benchmark_sizes:
            df = self._create_benchmark_dataframe(size)

            _, exec_time = self._benchmark_operation(
                f"init_model_{size}", PolarsTableModel, df, 1000, 5000
            )

            print(f"Initialized model with {size:,} rows in {exec_time:.3f}s")
            self.assertLess(exec_time, 5.0)  # Should complete within 5 seconds

    def test_data_access_performance(self):
        """Benchmark data access patterns."""
        df = self._create_benchmark_dataframe(50000)
        model = PolarsTableModel(df, chunk_size=1000)

        # Sequential access
        def sequential_access():
            for i in range(0, 1000, 10):
                index = model.createIndex(i, 0)
                model.data(index, Qt.DisplayRole)

        _, exec_time = self._benchmark_operation("sequential_access", sequential_access)

        print(f"Sequential access (100 items) in {exec_time:.3f}s")
        self.assertLess(exec_time, 1.0)

        # Random access
        def random_access():
            indices = np.random.randint(0, 50000, 100)
            for i in indices:
                index = model.createIndex(i, 0)
                model.data(index, Qt.DisplayRole)

        _, exec_time = self._benchmark_operation("random_access", random_access)

        print(f"Random access (100 items) in {exec_time:.3f}s")
        self.assertLess(exec_time, 2.0)

    def _create_benchmark_dataframe(self, rows: int) -> pl.DataFrame:
        """Create a benchmark dataframe."""
        np.random.seed(42)
        return pl.DataFrame(
            {
                "id": range(rows),
                "value1": np.random.random(rows),
                "value2": np.random.random(rows),
                "category": np.random.choice(["A", "B", "C"], rows),
                "text": [f"Item_{i}" for i in range(rows)],
            }
        )


class TestMemoryUsage(unittest.TestCase):
    """Memory usage tests."""

    def setUp(self):
        """Set up memory test fixtures."""
        self.process = psutil.Process()

    def test_memory_efficiency(self):
        """Test memory efficiency with large datasets."""
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        # Create large dataset
        large_df = pl.DataFrame(
            {
                "id": range(100000),
                "value": np.random.random(100000),
                "text": [f"Text_{i}" * 10 for i in range(100000)],  # Large strings
            }
        )

        after_df_memory = self.process.memory_info().rss / 1024 / 1024

        # Create model
        model = PolarsTableModel(large_df, chunk_size=1000, cache_size=5000)

        # Access the visible page so the row cache is exercised
        for i in range(0, model.page_size, 25):
            index = model.createIndex(i, 0)
            model.data(index, Qt.DisplayRole)

        after_model_memory = self.process.memory_info().rss / 1024 / 1024

        # Log memory usage
        df_memory_increase = after_df_memory - initial_memory
        model_memory_increase = after_model_memory - after_df_memory

        print("Memory usage:")
        print(f"  Initial: {initial_memory:.1f} MB")
        print(
            f"  After DataFrame: {after_df_memory:.1f} MB (+{df_memory_increase:.1f} MB)"
        )
        print(
            f"  After Model: {after_model_memory:.1f} MB (+{model_memory_increase:.1f} MB)"
        )

        # The model caches loaded row chunks only, so its own overhead must
        # stay small. RSS noise can make the frame measurement negative, so
        # compare against a fixed cap instead of a ratio.
        self.assertLess(model_memory_increase, 32.0)

    def test_cache_memory_limits(self):
        """Test that cache respects memory limits."""
        df = pl.DataFrame(
            {
                "id": range(50000),
                "data": [f"Large text data {i}" * 100 for i in range(50000)],
            }
        )

        model = PolarsTableModel(df, chunk_size=1000, cache_size=3000)

        # Access many chunks
        for i in range(0, 30000, 1000):
            index = model.createIndex(i, 0)
            model.data(index, Qt.DisplayRole)

        # Cache should not exceed reasonable size
        cached_chunks = len(model._data_cache)
        self.assertLessEqual(cached_chunks, 10)  # Should cleanup automatically

        # Get memory statistics
        memory_stats = model.get_memory_usage()
        cache_mb = memory_stats["cache_size_mb"]

        print(f"Cache usage: {cache_mb:.1f} MB with {cached_chunks} chunks")
        self.assertLess(cache_mb, 100)  # Should stay under 100 MB
