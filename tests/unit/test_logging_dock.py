#!/usr/bin/env python3
"""
Test script for logging dock functionality.
This script demonstrates the logging dock integration with design windows.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

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

            def switch_to_empty_window():
                # Switch to first window (which has no logs yet)
                print("Switching to first window (empty logs)...")
                windows = window.mdiArea.subWindowList()
                if len(windows) >= 2:
                    window.mdiArea.setActiveSubWindow(
                        windows[0]
                    )  # Switch to first window
                    print("Notice: Logging dock should now be empty!")

                    def add_logs_to_first():
                        # Add logs to first window after a delay
                        print("Adding logs to first window...")
                        first_window.logInfo("First window: Now active!")
                        first_window.logError("First window: Test error message")
                        first_window.logCritical("First window: Critical message")

                        def switch_back():
                            # Switch back to second window
                            print("Switching back to second window...")
                            windows = window.mdiArea.subWindowList()
                            if len(windows) >= 2:
                                window.mdiArea.setActiveSubWindow(
                                    windows[1]
                                )  # Switch to second window
                                print(
                                    "Back to second window - should see original logs again!"
                                )
                                second_window.logInfo(
                                    "Second window: Back to second window!"
                                )

                        # Switch back after 3 seconds
                        QTimer.singleShot(3000, switch_back)

                    # Add logs to first window after 2 seconds
                    QTimer.singleShot(2000, add_logs_to_first)

            # Switch windows after 3 seconds
            QTimer.singleShot(3000, switch_to_empty_window)

            print("Log messages sent to shared logging dock!")
            print("Watch how the dock clears when switching to windows with no logs.")
            print("The dock shows logs only for the currently active design window.")

        # Delay the test to give the UI time to initialize
        QTimer.singleShot(1000, test_logs)
    else:
        print("Failed to create design window for testing")

    return app.exec_()


if __name__ == "__main__":
    sys.exit(test_logging_functionality())
