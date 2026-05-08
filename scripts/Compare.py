import pandas as pd
import polars as pl
import time
import psutil
import os
import sys
import traceback
from pathlib import Path
import numpy as np


def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def format_size(bytes_size):
    """Format bytes to human readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def test_pandas_read(filename):
    """Test pandas CSV reading"""
    print("\n" + "=" * 60)
    print("TESTING PANDAS")
    print("=" * 60)

    results = {}

    # Standard pandas read_csv
    try:
        memory_before = get_memory_usage()
        start_time = time.time()

        df = pd.read_csv(filename, nrows=10)

        end_time = time.time()
        memory_after = get_memory_usage()

        results["pandas_standard"] = {
            "method": "pandas.read_csv() - standard",
            "time": end_time - start_time,
            "memory_used": memory_after - memory_before,
            "rows": len(df),
            "columns": len(df.columns),
            "success": True,
            "dataframe_memory": df.memory_usage(deep=True).sum() / 1024 / 1024,
        }

        print(f"✓ Standard pandas read completed")
        del df  # Free memory

    except Exception as e:
        results["pandas_standard"] = {
            "method": "pandas.read_csv() - standard",
            "success": False,
            "error": str(e),
        }
        print(f"✗ Standard pandas read failed: {e}")

    # # Pandas with chunking
    # try:
    #     memory_before = get_memory_usage()
    #     start_time = time.time()

    #     chunk_size = 10000
    #     chunks = []
    #     for chunk in pd.read_csv(filename, chunksize=chunk_size):
    #         chunks.append(chunk)
    #     df = pd.concat(chunks, ignore_index=True)

    #     end_time = time.time()
    #     memory_after = get_memory_usage()

    #     results['pandas_chunked'] = {
    #         'method': 'pandas.read_csv() - chunked (10k rows)',
    #         'time': end_time - start_time,
    #         'memory_used': memory_after - memory_before,
    #         'rows': len(df),
    #         'columns': len(df.columns),
    #         'success': True,
    #         'dataframe_memory': df.memory_usage(deep=True).sum() / 1024 / 1024
    #     }

    #     print(f"✓ Chunked pandas read completed")
    #     del df, chunks  # Free memory

    # except Exception as e:
    #     results['pandas_chunked'] = {
    #         'method': 'pandas.read_csv() - chunked',
    #         'success': False,
    #         'error': str(e)
    #     }
    #     print(f"✗ Chunked pandas read failed: {e}")

    # # Pandas with specific dtypes
    # try:
    #     memory_before = get_memory_usage()
    #     start_time = time.time()

    #     # Define dtypes to optimize memory
    #     dtypes = {
    #         'id': 'int32',
    #         'name': 'string',
    #         'age': 'int8',
    #         'salary': 'float32',
    #         'department': 'category',
    #         'score': 'float32',
    #         'active': 'bool',
    #         'city': 'category',
    #         'notes': 'string'
    #     }

    #     df = pd.read_csv(filename, dtype=str, nrows=10)

    #     end_time = time.time()
    #     memory_after = get_memory_usage()

    #     results['pandas_optimized'] = {
    #         'method': 'pandas.read_csv() - optimized dtypes',
    #         'time': end_time - start_time,
    #         'memory_used': memory_after - memory_before,
    #         'rows': len(df),
    #         'columns': len(df.columns),
    #         'success': True,
    #         'dataframe_memory': df.memory_usage(deep=True).sum() / 1024 / 1024
    #     }

    #     print(f"✓ Optimized pandas read completed")
    #     del df  # Free memory

    # except Exception as e:
    #     results['pandas_optimized'] = {
    #         'method': 'pandas.read_csv() - optimized dtypes',
    #         'success': False,
    #         'error': str(e)
    #     }
    #     print(f"✗ Optimized pandas read failed: {e}")

    return results


def test_polars_read(filename):
    """Test polars CSV reading"""
    print("\n" + "=" * 60)
    print("TESTING POLARS")
    print("=" * 60)

    results = {}

    # Standard polars read_csv
    try:
        memory_before = get_memory_usage()
        start_time = time.time()

        df = pl.read_csv(filename, n_rows=10, infer_schema=False)

        end_time = time.time()
        memory_after = get_memory_usage()

        results["polars_standard"] = {
            "method": "polars.read_csv() - standard",
            "time": end_time - start_time,
            "memory_used": memory_after - memory_before,
            "rows": df.height,
            "columns": df.width,
            "success": True,
            "dataframe_memory": df.estimated_size() / 1024 / 1024,
        }

        print(f"✓ Standard polars read completed")
        del df  # Free memory

    except Exception as e:
        results["polars_standard"] = {
            "method": "polars.read_csv() - standard",
            "success": False,
            "error": str(e),
        }
        print(f"✗ Standard polars read failed: {e}")

    # # Polars lazy read
    # try:
    #     memory_before = get_memory_usage()
    #     start_time = time.time()

    #     df = pl.scan_csv(filename, n_rows=10).collect()

    #     end_time = time.time()
    #     memory_after = get_memory_usage()

    #     results['polars_lazy'] = {
    #         'method': 'polars.scan_csv() - lazy loading',
    #         'time': end_time - start_time,
    #         'memory_used': memory_after - memory_before,
    #         'rows': df.height,
    #         'columns': df.width,
    #         'success': True,
    #         'dataframe_memory': df.estimated_size() / 1024 / 1024
    #     }

    #     print(f"✓ Lazy polars read completed")
    #     del df  # Free memory

    # except Exception as e:
    #     results['polars_lazy'] = {
    #         'method': 'polars.scan_csv() - lazy loading',
    #         'success': False,
    #         'error': str(e)
    #     }
    #     print(f"✗ Lazy polars read failed: {e}")

    return results


def test_other_methods(filename):
    """Test other CSV reading methods"""
    print("\n" + "=" * 60)
    print("TESTING OTHER METHODS")
    print("=" * 60)

    results = {}

    # Python built-in csv module
    try:
        import csv

        memory_before = get_memory_usage()
        start_time = time.time()

        rows = []
        with open(filename, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                rows.append(row)

        end_time = time.time()
        memory_after = get_memory_usage()

        results["python_csv"] = {
            "method": "Python built-in csv module",
            "time": end_time - start_time,
            "memory_used": memory_after - memory_before,
            "rows": len(rows),
            "columns": len(rows[0].keys()) if rows else 0,
            "success": True,
            "dataframe_memory": sys.getsizeof(rows) / 1024 / 1024,
        }

        print(f"✓ Python csv module read completed")
        del rows  # Free memory

    except Exception as e:
        results["python_csv"] = {
            "method": "Python built-in csv module",
            "success": False,
            "error": str(e),
        }
        print(f"✗ Python csv module read failed: {e}")

    # Try dask if available
    try:
        import dask.dataframe as dd

        memory_before = get_memory_usage()
        start_time = time.time()

        df = dd.read_csv(filename)
        df = df.compute()  # Actually load the data

        end_time = time.time()
        memory_after = get_memory_usage()

        results["dask"] = {
            "method": "Dask dataframe",
            "time": end_time - start_time,
            "memory_used": memory_after - memory_before,
            "rows": len(df),
            "columns": len(df.columns),
            "success": True,
            "dataframe_memory": df.memory_usage(deep=True).sum() / 1024 / 1024,
        }

        print(f"✓ Dask read completed")
        del df  # Free memory

    except ImportError:
        print("ℹ Dask not available - skipping")
    except Exception as e:
        results["dask"] = {
            "method": "Dask dataframe",
            "success": False,
            "error": str(e),
        }
        print(f"✗ Dask read failed: {e}")

    return results


def print_results(all_results):
    """Print comparison results"""
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON RESULTS")
    print("=" * 80)

    # Collect successful results
    successful_results = []
    failed_results = []

    for category_results in all_results.values():
        for result in category_results.values():
            if result.get("success", False):
                successful_results.append(result)
            else:
                failed_results.append(result)

    if successful_results:
        print(
            f"\n{'Method':<35} {'Time (s)':<10} {'Memory (MB)':<12} {'DF Memory (MB)':<15} {'Rows':<10} {'Cols':<6}"
        )
        print("-" * 88)

        # Sort by time taken
        successful_results.sort(key=lambda x: x["time"])

        for result in successful_results:
            print(
                f"{result['method']:<35} {result['time']:<10.2f} {result['memory_used']:<12.1f} {result.get('dataframe_memory', 0):<15.1f} {result['rows']:<10,} {result['columns']:<6}"
            )

    if failed_results:
        print(f"\n{'FAILED METHODS':<35} {'Error':<50}")
        print("-" * 85)
        for result in failed_results:
            print(f"{result['method']:<35} {result.get('error', 'Unknown error'):<50}")

    # Performance rankings
    if successful_results:
        print(f"\n🏆 PERFORMANCE RANKINGS:")
        print(f"{'Rank':<6} {'Method':<35} {'Time (s)':<10} {'Speed':<15}")
        print("-" * 66)

        fastest_time = successful_results[0]["time"]
        for i, result in enumerate(successful_results, 1):
            speed_factor = result["time"] / fastest_time
            speed_text = f"{speed_factor:.1f}x" if speed_factor > 1 else "Baseline"
            print(
                f"{i:<6} {result['method']:<35} {result['time']:<10.2f} {speed_text:<15}"
            )


def main():
    """Main function to run the comparison"""
    print("CSV Reading Performance Comparison")
    print("=" * 80)

    # Configuration
    test_file = r"C:\Amer\Product Engine\Inputs\20250924_BOM_Placement.csv"
    num_rows = 100  # Adjust this based on your needs

    try:
        # Create test data if needed
        # create_test_csv(test_file, num_rows)

        # Run all tests
        all_results = {}

        # Test pandas methods
        all_results["pandas"] = test_pandas_read(test_file)

        # Test polars methods
        all_results["polars"] = test_polars_read(test_file)

        # Test other methods
        # all_results['others'] = test_other_methods(test_file)

        # Print results
        print_results(all_results)

        print(f"\n✓ Comparison completed successfully!")
        print(f"Test file: {test_file}")
        print(f"File size: {format_size(os.path.getsize(test_file))}")

    except Exception as e:
        print(f"✗ Error during comparison: {e}")
        print(f"Error details: {traceback.format_exc()}")
        return 1

    finally:
        # Cleanup
        if os.path.exists(test_file):
            try:
                # Uncomment the next line if you want to delete the test file
                # os.remove(test_file)
                pass
            except:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
