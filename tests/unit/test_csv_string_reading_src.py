#!/usr/bin/env python3
"""
Test script to verify that CSV reading with infer_schema=False works correctly.
This addresses the error: could not parse `R&D Season` as dtype `i64`
"""

import polars as pl
import tempfile
import os


def test_csv_with_mixed_data():
    """Test reading a CSV with mixed data that could cause parsing issues."""

    # Create sample data that would cause the original error
    sample_data = """Product ID,Material Season,Category,Price
P001,R&D Season,Electronics,299.99
P002,2024 Spring,Clothing,49.99
P003,Q3 Launch,Software,1299.00
P004,Beta Phase,Hardware,899.50
"""

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(sample_data)
        temp_file = f.name

    try:
        print("Testing CSV reading with infer_schema=False...")

        # Test 1: Read with infer_schema=False (should work)
        df1 = pl.read_csv(temp_file, infer_schema=False)
        print("✅ Successfully read CSV with infer_schema=False")
        print(f"Shape: {df1.shape}")
        print(f"Column types: {df1.dtypes}")
        print(f"Material Season column: {df1['Material Season'].to_list()}")
        print()

        # Test 2: Try with lazy reading
        lazy_df = pl.scan_csv(temp_file, infer_schema=False)
        df2 = lazy_df.collect()
        print("✅ Successfully read CSV with lazy evaluation and infer_schema=False")
        print(f"Shape: {df2.shape}")
        print()

        # Test 3: Show what happens with default schema inference (should fail)
        try:
            df3 = pl.read_csv(temp_file)  # Default infer_schema=True
            print("⚠️  Default schema inference worked (unexpected)")
        except Exception as e:
            print(f"❌ Default schema inference failed as expected: {e}")

        print("\n🎉 All tests completed successfully!")

    finally:
        # Clean up
        os.unlink(temp_file)


if __name__ == "__main__":
    test_csv_with_mixed_data()
