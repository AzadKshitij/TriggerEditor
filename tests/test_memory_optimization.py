#!/usr/bin/env python3
"""
Memory usage test script to verify the optimizations work
"""

import polars as pl
import tempfile
import os
import psutil
import gc


def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def test_memory_optimized_reading():
    """Test memory usage with the new optimized reading approach"""

    print("Testing memory usage optimization...")
    print(f"Initial memory: {get_memory_usage():.1f} MB")

    # Create a larger test CSV file
    sample_data = """Product ID,Material Season,Category,Price,Description,Vendor,Stock
P001,R&D Season,Electronics,299.99,High-tech device,TechCorp,100
P002,2024 Spring,Clothing,49.99,Casual wear,FashionInc,250
P003,Q3 Launch,Software,1299.00,Professional software,SoftwareHub,50
P004,Beta Phase,Hardware,899.50,Computer hardware,HardwarePlus,75
"""

    # Repeat data to make file larger
    large_data = sample_data
    for i in range(1000):  # Create ~4000 rows
        large_data += sample_data.replace("P001", f"P{i:04d}_1").replace(
            "P002", f"P{i:04d}_2").replace("P003", f"P{i:04d}_3").replace("P004", f"P{i:04d}_4")

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(large_data)
        temp_file = f.name

    try:
        print(f"Created test file with ~4000 rows")
        print(f"Memory after file creation: {get_memory_usage():.1f} MB")

        # Test 1: Memory-optimized preview reading (only 5 rows)
        print("\n--- Test 1: Memory-optimized preview reading (5 rows) ---")
        df_preview = pl.read_csv(
            temp_file,
            n_rows=5,
            infer_schema=False,
            low_memory=True,
            rechunk=False
        )
        print(
            f"Preview loaded: {df_preview.shape[0]} rows, {df_preview.shape[1]} columns")
        print(f"Memory after preview: {get_memory_usage():.1f} MB")

        # Immediately clean up
        del df_preview
        gc.collect()
        print(f"Memory after cleanup: {get_memory_usage():.1f} MB")

        # Test 2: Compare with full file loading (without optimizations)
        print("\n--- Test 2: Full file loading (for comparison) ---")
        df_full = pl.read_csv(temp_file)
        print(
            f"Full file loaded: {df_full.shape[0]} rows, {df_full.shape[1]} columns")
        print(f"Memory after full load: {get_memory_usage():.1f} MB")

        del df_full
        gc.collect()
        print(f"Memory after full cleanup: {get_memory_usage():.1f} MB")

        # Test 3: Lazy reading approach
        print("\n--- Test 3: Lazy reading approach ---")
        lazy_df = pl.scan_csv(temp_file, infer_schema=False, low_memory=True)
        preview_lazy = lazy_df.head(5).collect()
        print(
            f"Lazy preview: {preview_lazy.shape[0]} rows, {preview_lazy.shape[1]} columns")
        print(f"Memory after lazy preview: {get_memory_usage():.1f} MB")

        del lazy_df, preview_lazy
        gc.collect()
        print(f"Memory after lazy cleanup: {get_memory_usage():.1f} MB")

        print("\n🎉 Memory optimization tests completed!")
        print("The optimizations should show significantly lower memory usage for preview operations.")

    finally:
        # Clean up
        os.unlink(temp_file)


if __name__ == "__main__":
    test_memory_optimized_reading()
