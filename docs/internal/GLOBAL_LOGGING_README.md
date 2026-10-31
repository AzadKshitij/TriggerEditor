# Global Logging Functionality

The Trigger Designer application now includes a global logging system that allows you to easily log messages from anywhere in the application code, without needing direct access to a design window instance.

## Overview

The global logger automatically routes log messages to the currently active design window's logging dock. This makes it easy to add logging from:
- Background processes
- Utility functions
- External modules
- Any part of the application

## Usage

### Basic Global Logging

```python
from trigger_designer.qt.helpers import global_logger

# Log to the currently active design window
global_logger.info("Application started successfully")
global_logger.debug("Processing data...")
global_logger.warning("Low memory warning")
global_logger.error("Connection failed")
global_logger.critical("System error occurred")
global_logger.trace("Detailed trace information")
```

### Shorter Function Names

```python
from trigger_designer.qt.helpers.global_logger import (
    info, debug, warning, error, critical, trace
)

# Use shorter function names
info("This is an info message")
debug("Debug information")
warning("Warning message")
error("Error occurred")
```

### Logging to Specific Design Window

```python
from trigger_designer.qt.helpers import global_logger

# Log to a specific design window (if you have a reference)
global_logger.info("Message for specific window", design_window=my_window)
```

### Generic Log Function

```python
from trigger_designer.qt.helpers.global_logger import log

# Use the generic log function with custom level
log("INFO", "Custom log message")
log("DEBUG", "Debug information")
```

## Integration

### Automatic Setup

The global logger is automatically initialized when the main window is created. No additional setup is required.

### From Design Windows

Design windows can use both local and global logging:

```python
# Local logging (instance method)
self.logInfo("Local message")

# Global logging (works from anywhere)
global_logger.info("Global message")
```

### From External Modules

Any module can import and use the global logger:

```python
# In any Python module
from trigger_designer.qt.helpers import global_logger

def my_function():
    global_logger.info("Function executed successfully")
    
    try:
        # Some operation
        result = perform_operation()
        global_logger.debug(f"Operation result: {result}")
    except Exception as e:
        global_logger.error(f"Operation failed: {e}")
```

## Features

### Thread-Safe

The global logger is implemented as a thread-safe singleton, making it safe to use from background threads and async operations.

### Automatic Routing

Messages are automatically routed to:
1. The currently active design window (preferred)
2. The logging dock directly (fallback)
3. Console output (final fallback)

### Fallback Handling

If no design window is available or there's an error in the logging system, messages fall back to console output to ensure no logs are lost.

### Error Resilience

The logging system is designed to never throw exceptions - if logging fails, it falls back to console output and continues.

## Examples

### Background Process Logging

```python
import threading
from trigger_designer.qt.helpers import global_logger

def background_task():
    """Example background task with logging"""
    global_logger.info("Background task started")
    
    for i in range(10):
        global_logger.debug(f"Processing item {i+1}/10")
        # Simulate work
        time.sleep(1)
    
    global_logger.info("Background task completed")

# Start background task
thread = threading.Thread(target=background_task)
thread.start()
```

### Error Handling with Logging

```python
from trigger_designer.qt.helpers import global_logger

def risky_operation():
    """Example function with comprehensive logging"""
    global_logger.debug("Starting risky operation")
    
    try:
        # Potentially failing operation
        result = perform_complex_calculation()
        global_logger.info(f"Operation successful: {result}")
        return result
        
    except ValueError as e:
        global_logger.warning(f"Invalid input detected: {e}")
        return None
        
    except Exception as e:
        global_logger.error(f"Unexpected error in operation: {e}")
        global_logger.critical("System may be in unstable state")
        raise
```

### Module-Level Logging

```python
# In a utility module
from trigger_designer.qt.helpers.global_logger import info, error

def load_configuration(filename):
    """Load configuration with logging"""
    info(f"Loading configuration from {filename}")
    
    try:
        with open(filename, 'r') as f:
            config = json.load(f)
        info("Configuration loaded successfully")
        return config
    except FileNotFoundError:
        error(f"Configuration file not found: {filename}")
        return {}
    except json.JSONDecodeError as e:
        error(f"Invalid JSON in configuration file: {e}")
        return {}
```

## Testing

### Interactive Testing

Press `Shift+G` in any design window to test global logging with sample messages at different levels.

### Automated Testing

Run the test script:

```bash
python test_global_logging.py
```

This demonstrates:
- Global logging from application startup
- Logging from simulated external modules
- Background/periodic logging
- Integration with the design window system

## Best Practices

### When to Use Global vs Local Logging

**Use Global Logging:**
- Utility functions and modules
- Background processes
- Error handlers
- System-level events
- When you don't have access to a design window instance

**Use Local Logging:**
- Design window specific events
- User interactions within a window
- Workflow execution steps
- When you have direct access to the design window

### Performance Considerations

- Global logging adds minimal overhead
- Thread-safe but avoid excessive logging in tight loops
- Fallback mechanisms ensure no blocking

### Error Handling

- Global logger never throws exceptions
- Always provides fallback logging to console
- Graceful degradation when UI components aren't available

The global logging system provides a robust, easy-to-use logging infrastructure that works seamlessly with the existing design window logging dock system!