#!/usr/bin/env python3
"""
Example demonstrating global logging functionality.
This shows how to use the global logger from anywhere in the application.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from qtpy.QtWidgets import QApplication
from qtpy.QtCore import QTimer

from trigger_designer.qt.main_window import TriggerWindow
from trigger_designer.qt.helpers import global_logger


def demonstrate_global_logging():
    """Demonstrate global logging from outside design window context"""
    
    def test_global_logging():
        print("Testing global logging functionality...")
        
        # These calls can be made from anywhere in the application
        global_logger.info("🌍 Global logger initialized and ready!")
        global_logger.debug("🔧 This is a debug message from global logger")
        global_logger.warning("⚠️ Global warning - this works from any module")
        global_logger.error("❌ Global error message (just a test)")
        global_logger.trace("🔍 Trace message for detailed debugging")
        global_logger.critical("🚨 Critical message from global context")
        
        print("✅ Global logging test completed!")
        print("Check the logging dock to see all messages.")
        print("Press Shift+G in any design window to test more global logging.")
        
    return test_global_logging


def simulate_external_module_logging():
    """Simulate logging from an external module or background process"""
    
    def external_logging():
        # This could be called from any module, background thread, etc.
        global_logger.info("📡 Message from external module")
        global_logger.debug("🔄 Processing background task...")
        global_logger.info("✅ Background task completed")
        
        # Schedule another round
        QTimer.singleShot(5000, external_logging)
        
    return external_logging


def main():
    """Main function to test global logging"""
    app = QApplication(sys.argv)
    
    # Create main window
    window = TriggerWindow()
    window.show()
    
    # Create a design window to receive logs
    window.onFileNew()
    
    # Test global logging after a delay
    test_func = demonstrate_global_logging()
    QTimer.singleShot(1000, test_func)
    
    # Start simulated external logging
    external_func = simulate_external_module_logging()
    QTimer.singleShot(3000, external_func)
    
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())