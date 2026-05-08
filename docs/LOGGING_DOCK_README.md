# Logging Dock Integration

This document describes the logging dock functionality that has been integrated into the Trigger Designer application.

## Overview

The logging dock provides a single, shared logging panel that displays logs for the currently active design window. The dock automatically switches context when you switch between different design windows, showing only the logs relevant to the active window.

## Features

### Shared Logging Dock with Context Switching
- Single logging dock that shows logs for the currently active design window
- Logs are isolated per design window but displayed in a shared interface
- Automatic context switching when you change between design windows
- Clean display when switching to windows with no logs (empty state)

### Docking Capabilities
- The logging dock can be docked to any edge of the main window
- Can be undocked to float as a separate window
- Can be closed and reopened as needed
- Supports tabbed docking with other panels

### Log Filtering
- **Log Level Filter**: Filter logs by minimum level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Text Filter**: Search for specific text within log messages
- **Auto-scroll**: Automatically scroll to the latest log entries

### Log Levels
- **TRACE** (Gray): Detailed debugging information
- **DEBUG** (Green): General debugging information  
- **INFO** (Blue): General information messages
- **WARNING** (Orange): Warning messages
- **ERROR** (Red): Error messages
- **CRITICAL** (Purple): Critical error messages

## Usage

### Automatic Context Switching
When you create a new design window (File → New or Ctrl+N), the existing logging dock automatically starts tracking logs for that window. When you switch between design windows, the logging dock content updates to show logs for the currently active window.

### Manual Logging
From within a design window, you can log messages using these methods:

```python
# In your design window code
self.logTrace("Detailed debugging info")
self.logDebug("Debug information") 
self.logInfo("General information")
self.logWarning("Warning message")
self.logError("Error occurred")
self.logCritical("Critical error")

# Or use the generic log method
self.log("INFO", "Custom message")
```

### Built-in Logging
The application automatically logs various activities:
- Design window creation with welcome messages
- File loading operations
- Workflow execution status
- Node creation events
- Error conditions

### Dock Management
- **Docking**: Drag the dock's title bar to dock it to different areas
- **Undocking**: Drag the dock away from the edges to make it float
- **Closing**: Click the X button on the dock to close it
- **Resizing**: Drag the dock borders to resize the logging area

### Filtering
1. **Log Level**: Use the dropdown to select minimum log level to display
2. **Text Filter**: Type in the filter box to search for specific text
3. **Auto-scroll**: Check/uncheck to enable/disable automatic scrolling
4. **Clear**: Click the "Clear" button to remove all log entries

## Implementation Details

### Architecture
- `LoggingDock`: The main dock widget containing the log viewer
- `LogEntry`: Represents individual log entries with timestamps
- `MainWindowDockMixin`: Manages dock creation and cleanup
- `TriggerSubWindow`: Integrated with logging methods

### Memory Management
- Logs are automatically limited to 1000 entries per design window to prevent memory issues
- Older logs are removed when the limit is exceeded for each window
- Logs for a design window are automatically cleaned up when the window is closed
- Only one dock exists, reducing memory overhead

### Performance
- Log display is updated every 100ms for smooth performance
- Only updates when new logs are added
- Efficient filtering without rebuilding the entire display

## Testing

You can test the logging functionality by running:

```bash
python test_logging_dock.py
```

This will:
1. Create a main window with a new design window
2. Send test messages at different log levels
3. Demonstrate the logging dock functionality

## Future Enhancements

Potential future improvements:
- Export logs to file
- Log search and highlighting
- Log level statistics
- Custom log formatting
- Integration with external logging frameworks
- Log timestamps with different formats
- Log message grouping and folding