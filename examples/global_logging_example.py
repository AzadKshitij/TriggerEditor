"""
Simple usage example for global logging.

This file demonstrates how any module in the application can easily use logging.
Import this pattern in your own modules for consistent logging.
"""

# Import the global logger
from trigger_designer.qt.helpers import global_logger

# Alternative import for shorter function names
from trigger_designer.qt.helpers.global_logger import (
    info,
    debug,
    warning,
    error,
    critical,
    trace,
)


def example_function():
    """Example function showing different ways to use global logging"""

    # Method 1: Using the global_logger module
    global_logger.info("Function started")
    global_logger.debug("Processing data...")

    try:
        # Simulate some work
        result = "success"
        global_logger.info(f"Operation completed with result: {result}")

    except Exception as e:
        global_logger.error(f"Operation failed: {e}")
        raise

    # Method 2: Using direct function imports (shorter)
    info("Using shorter function names")
    debug("This is more concise")
    warning("Warning message example")

    global_logger.info("Function completed successfully")


def error_handling_example():
    """Example of comprehensive error handling with logging"""

    info("Starting error handling example")

    try:
        # Simulate risky operation
        risky_operation()
        info("Risky operation completed successfully")

    except ValueError as ve:
        warning(f"Expected error occurred: {ve}")

    except Exception as e:
        error(f"Unexpected error: {e}")
        critical("System may be in an unstable state")

    finally:
        debug("Cleanup completed")


def risky_operation():
    """Simulate an operation that might fail"""
    import random

    debug("Performing risky operation")

    if random.random() < 0.3:  # 30% chance of failure
        raise ValueError("Random failure occurred")

    if random.random() < 0.1:  # 10% chance of unexpected error
        raise RuntimeError("Unexpected system error")

    debug("Risky operation succeeded")
    return "success"


# Example of module-level logging
info("global_logging_example module loaded")


if __name__ == "__main__":
    # This won't work without the main application running,
    # but shows how you might test individual functions
    print("Run this from within the main application to see logging in action")
    print("Example usage:")
    print("  from examples.global_logging_example import example_function")
    print("  example_function()")
