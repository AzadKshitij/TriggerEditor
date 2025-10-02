#!/usr/bin/env python3
"""
Test script for logging dock functionality.
This script demonstrates the logging dock integration with design windows.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from qtpy.QtWidgets import QApplication
from qtpy.QtCore import QTimer

from trigger_designer.qt.main_window import TriggerWindow


def test_logging_functionality():
    """Test the logging dock functionality"""
    app = QApplication(sys.argv)
    
    # Create main window
    window = TriggerWindow()
    window.show()
    
    # Create multiple design windows to test logging switching
    window.onFileNew()  # First window
    first_window = window.getCurrentNodeEditorWidget()
    
    window.onFileNew()  # Second window  
    second_window = window.getCurrentNodeEditorWidget()
    
    if first_window and second_window:
        # Test logging functionality with a delay
        def test_logs():
            print("Testing shared logging dock functionality...")
            
            # Log to second window (currently active)
            second_window.logInfo("Second window: Application started")
            second_window.logDebug("Second window: Debug message")
            second_window.logWarning("Second window: Warning message")
            
            def switch_and_log():
                # Switch to first window and log
                print("Switching to first window...")
                windows = window.mdiArea.subWindowList()
                if len(windows) >= 2:
                    window.mdiArea.setActiveSubWindow(windows[0])  # Switch to first window
                    
                    # Log to first window
                    first_window.logInfo("First window: Now active!")
                    first_window.logError("First window: Test error message")
                    first_window.logCritical("First window: Critical message")
                    
                def switch_back():
                    # Switch back to second window
                    print("Switching back to second window...")
                    windows = window.mdiArea.subWindowList()
                    if len(windows) >= 2:
                        window.mdiArea.setActiveSubWindow(windows[1])  # Switch to second window
                        second_window.logInfo("Second window: Back to second window!")
                        second_window.logTrace("Second window: Trace message")
                
                # Switch back after 3 seconds
                QTimer.singleShot(3000, switch_back)
            
            # Switch windows after 3 seconds
            QTimer.singleShot(3000, switch_and_log)
            
            print("Log messages sent to shared logging dock!")
            print("Notice how the dock content changes when you switch between windows.")
            print("The dock shows logs only for the currently active design window.")
        
        # Delay the test to give the UI time to initialize
        QTimer.singleShot(1000, test_logs)
    else:
        print("Failed to create design window for testing")
    
    return app.exec_()


if __name__ == "__main__":
    sys.exit(test_logging_functionality())