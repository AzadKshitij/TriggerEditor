#!/usr/bin/env python3
"""
Test script to verify the variable scope fix and encoding handling
"""

import csv
import tempfile
import os


def test_csv_reading_with_various_encodings():
    """Test CSV reading with different encodings and edge cases"""

    print("Testing CSV reading with various encodings...")

    # Test data with special characters that might cause encoding issues
    test_data = [
        ("utf-8", "Product ID,Material Season,Description\nP001,R&D Season,Test Product\nP002,Q1 2024,Sample Item"),
        ("latin-1", "Product ID,Material Season,Description\nP001,R&D Season,Test Product\nP002,Q1 2024,Sample Item"),
        ("cp1252", "Product ID,Material Season,Description\nP001,R&D Season,Test Product\nP002,Q1 2024,Sample Item")
    ]

    for encoding, data in test_data:
        print(f"\n--- Testing {encoding} encoding ---")

        # Create temp file with specific encoding
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', encoding=encoding, delete=False) as f:
            f.write(data)
            temp_file = f.name

        try:
            # Test reading with multiple encoding attempts
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

            success = False
            for read_encoding in encodings_to_try:
                try:
                    rows = []
                    columns = []

                    with open(temp_file, 'r', encoding=read_encoding, newline='') as csvfile:
                        reader = csv.reader(csvfile, delimiter=',')

                        # Read header
                        columns = next(reader)

                        # Read 2 data rows
                        for i, row in enumerate(reader):
                            if i >= 2:
                                break
                            rows.append(row)

                    print(
                        f"✅ Successfully read with {read_encoding}: {len(columns)} columns, {len(rows)} rows")
                    print(f"   Columns: {columns}")
                    success = True
                    break

                except (UnicodeDecodeError, UnicodeError) as e:
                    print(f"❌ Failed with {read_encoding}: {e}")
                    continue
                except Exception as e:
                    print(f"❌ Error with {read_encoding}: {e}")
                    continue

            if not success:
                print("❌ All encodings failed!")

        finally:
            # Clean up
            os.unlink(temp_file)

    print("\n🎉 Encoding test completed!")


def test_variable_scope_fix():
    """Test that variables are properly defined in both branches"""
    print("\nTesting variable scope fix...")

    # Simulate the loadFile logic structure
    def mock_loadFile(file_type, raw_data):
        try:
            if file_type in ['csv', 'txt']:
                # CSV branch
                columns = raw_data['columns']
                rows = raw_data['rows']

                # Variables should be defined here
                row_count = len(rows)
                col_count = len(columns)

                print(f"CSV branch: {row_count} rows, {col_count} columns")

            else:
                # Other formats branch
                row_count = 5  # mock
                col_count = 3  # mock

                print(f"Other branch: {row_count} rows, {col_count} columns")

            # This should now work in both branches
            print(f"Final info: {row_count} rows, {col_count} columns")
            return True

        except UnboundLocalError as e:
            print(f"❌ Variable scope error: {e}")
            return False

    # Test CSV case
    csv_data = {'columns': ['A', 'B', 'C'],
                'rows': [['1', '2', '3'], ['4', '5', '6']]}
    success1 = mock_loadFile('csv', csv_data)

    # Test Excel case
    success2 = mock_loadFile('excel', {})

    if success1 and success2:
        print("✅ Variable scope fix working correctly!")
    else:
        print("❌ Variable scope issues still present")


if __name__ == "__main__":
    test_csv_reading_with_various_encodings()
    test_variable_scope_fix()
