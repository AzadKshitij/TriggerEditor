# Polars DataFrame Table Viewer

A high-performance, memory-efficient table viewer for Polars DataFrames with advanced features for handling large datasets.

## Features

### Core Capabilities
- **Memory Efficient**: Shows one page at a time and loads row chunks lazily, so
  rows outside the current page are never kept
- **High Performance**: Virtual scrolling and a small in-page chunk cache
- **Large Dataset Support**: Handles millions of rows without performance degradation
- **Real-time Memory Monitoring**: Built-in cache usage reporting

### User Interface Features
- **Paged View**: fixed page size (100-1000, default 250) with first / previous /
  next / last controls and a `Rows a-b of n` label
- **Sortable Columns**: click a header to sort the whole frame (nulls last); a sort
  resets paging to the first page
- **Advanced Search & Filtering**: Search across all columns or specific columns
- **Data Type Formatting**: Automatic formatting for dates, numbers, booleans, and nulls
- **Export Functionality**: Export to CSV and Excel formats
- **Theme Aware**: header, grid and row tint follow the active light/dark theme

### Technical Features
- **Lazy Loading**: Only loads visible data chunks
- **Intelligent Caching**: LRU-based cache with configurable size limits
- **Data Type Awareness**: Proper handling of all Polars data types
- **Error Resilience**: Graceful handling of data access errors
- **Performance Monitoring**: Real-time performance metrics and logging

## Installation

The table viewer is part of the TriggerEditor project. Ensure you have the required dependencies:

```bash
pip install polars qtpy psutil loguru
```

## Quick Start

### Basic Usage

```python
import polars as pl
from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer
from qtpy.QtWidgets import QApplication

# Create sample data
df = pl.DataFrame({
    'id': range(10000),
    'name': [f'Person_{i}' for i in range(10000)],
    'value': [i * 1.5 for i in range(10000)],
    'active': [i % 2 == 0 for i in range(10000)]
})

# Create application and viewer
app = QApplication([])
viewer = PolarsTableViewer(df)
viewer.show()

app.exec_()
```

### Enhanced Preview Window

```python
from trigger_designer.qt.widgets.data_preview_window import DataPreviewWindow

window = DataPreviewWindow(df, "My Dataset")
window.show()
```

## Paging and Display Options

```python
from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer

viewer = PolarsTableViewer(df)      # paging footer + info line (default)
model = viewer.model

model.set_page_size(500)            # 100-1000, keeps the first visible row in view
model.set_page(2)                   # zero-based page index
model.page_offset                   # first row of the current page
model.page_count                    # number of pages
model.total_rows                    # rows in the frame
model.sort_by(column=1, descending=True)

# Embed compactly; show_controls / show_info / show_search / show_export can be off
compact = PolarsTableViewer(df, show_info=False, show_search=False)
```

### Memory Behaviour

A viewer holds one page plus a small chunk cache, so memory scales with the page
size, not with the frame. `viewer.refresh()` re-reads the frame and clears the
cache, and `viewer.model.get_memory_usage()` reports the current cache usage.

## Advanced Usage

### Custom Data Loading

```python
# Create model separately for more control
from trigger_designer.qt.models.polars_table_viewer import PolarsTableModel

model = PolarsTableModel(df, chunk_size=1000, cache_size=5000)

# Use with any QTableView
from qtpy.QtWidgets import QTableView
table_view = QTableView()
table_view.setModel(model)
```

### Search and Filtering

```python
# Programmatic filtering
viewer.search_input.setText("search_term")
viewer.column_filter.setCurrentText("specific_column")
viewer._apply_filter()

# Clear filters
viewer._clear_filter()
```

### Export Data

```python
# Export the current frame (opens a file dialog)
viewer.export_csv()
viewer.export_excel()

# Get selected data as DataFrame
selected_df = viewer.get_selected_data()
```

### Memory Monitoring

```python
# Cache statistics of the current page
stats = viewer.model.get_memory_usage()
print(f"Cache size: {stats['cache_size_mb']:.1f} MB")
print(f"Cached chunks: {stats['cached_chunks']}")
```

## Performance Benchmarks

### Test Results (Sample Hardware)

| Dataset Size | Load Time | Memory Usage | Scroll Performance |
|-------------|-----------|--------------|-------------------|
| 1K rows     | < 0.1s    | ~2 MB        | Instant           |
| 10K rows    | < 0.5s    | ~5 MB        | Instant           |
| 100K rows   | < 2s      | ~15 MB       | Smooth            |
| 1M rows     | < 10s     | ~50 MB       | Smooth            |

### Memory Efficiency

- **Lazy Loading**: Only loads the visible page's row chunks
- **Smart Caching**: Keeps recently accessed chunks in memory
- **Auto Cleanup**: Removes old cache entries when memory limits are reached
- **Low Overhead**: Model overhead is typically < 10% of DataFrame size

## Running Tests

```bash
uv run --project . pytest tests/unit/test_polars_table_viewer.py
```

The demo application is `tests/integration/polars_viewer_demo.py`.

## Architecture

### Class Hierarchy

```
PolarsTableModel (QAbstractTableModel)
├── Holds the frame and the current page
├── Loads row chunks lazily with a small cache
├── Provides data formatting and type handling
└── Owns sorting and paging (set_page, set_page_size, sort_by)

PolarsTableViewer (QWidget)
├── Main UI container with controls
├── Search and filtering functionality
├── Paging footer (first / previous / next / last, page size, range label)
├── Export capabilities
└── Uses PolarsTableModel internally

DataPreviewWindow (QMainWindow)
├── Thin host of the shared DataPreviewPanel
└── Used by the Alt+click socket preview
```

### Key Components

1. **PolarsTableModel**: Core data access layer with lazy row chunks
2. **Page Cache**: only the current page's chunks are kept
3. **Paging**: fixed-size pages with first / previous / next / last navigation
4. **Memory Reporting**: cache usage statistics via `get_memory_usage()`
5. **Data Formatting**: Type-aware display formatting
6. **Search Engine**: Efficient filtering across columns

## Data Type Support

### Supported Types
- **Integers**: Int8, Int16, Int32, Int64, UInt8, UInt16, UInt32, UInt64
- **Floats**: Float32, Float64
- **Strings**: Utf8, String
- **Dates**: Date, Datetime
- **Boolean**: Boolean
- **Nulls**: Proper NULL display and handling

### Formatting Features
- **Numbers**: Intelligent precision and alignment
- **Dates**: Configurable date/time formatting
- **Strings**: Truncation for very long strings
- **Nulls**: Clear "NULL" display
- **Tooltips**: Show data type and value information

## Error Handling

The table viewer includes comprehensive error handling:

- **Data Access Errors**: Graceful fallback to loading indicators
- **Memory Errors**: Automatic cache eviction when the cache limit is reached
- **Format Errors**: Safe string conversion for display
- **Filter Errors**: Clear error messages and recovery
- **Export Errors**: Detailed error logging and user feedback

## Best Practices

### For Large Datasets
1. Keep the default page size (250) unless more rows must be on screen
2. Sort or search to work with a subset of the frame
3. Use the export functions for a subset instead of paging through everything
4. Watch the info line for the frame's real size

### For Performance
1. Prefer sorting and searching over paging through many pages
2. Check for complex data types or very large strings
3. Monitor the performance logs for bottlenecks

### For Memory Efficiency
1. Rows outside the current page are never cached - no tuning needed
2. Call `refresh()` to drop the cache after the source data changed
3. Searching or filtering narrows the frame the model reads from
4. Lower the page size if memory is tight

## Troubleshooting

### Common Issues

**High Memory Usage**
- Lower the page size
- Clear the search/filter and refresh the view
- Consider working with data subsets

**Slow Performance**
- Use sorting and searching to work with subsets
- Check for complex data types or large strings
- Monitor performance logs for bottlenecks

**Display Issues**
- Verify data types are supported
- Check for null values or unusual data
- Refresh the view to clear cache issues
- Review error logs for formatting problems

### Debug Information

Viewer messages go through loguru; add a sink filtered to this module:

```python
from loguru import logger

logger.add(
    "polars_viewer.log",
    filter="trigger_designer.qt.models.polars_table_viewer",
    level="DEBUG",
)
```

## Contributing

When contributing to the table viewer:

1. Add tests for new features in `tests/unit/test_polars_table_viewer.py`
2. Update performance benchmarks for significant changes
3. Ensure memory efficiency is maintained
4. Document any new configuration options
5. Test with various data types and sizes

## License

This table viewer is part of the TriggerEditor project. See the main project license for details.
