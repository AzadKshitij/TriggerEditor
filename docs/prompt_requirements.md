
# Requirements
Use the following instructions for all code generation tasks in this project:

1. Data Processing:
Use the Polars library for all data manipulation, analysis, or processing.
Make sure to use Lazyframe always unless it is no possible.
Do not use pandas or alternative libraries unless explicitly instructed.

2. User Interface:
Build GUI components using Qt (via PyQt or PySide).

3. Serialization:
Decorate any class that needs to be serialized with @dataclasses.dataclass.
Ensure these classes are JSON serializable. Do not add this to the Content class because that class does not need to be serialized.

4. Type Hints:
Add explicit type hints to all functions and methods for parameters and return values.

5. Documentation:
Include simple docstring in newly created functions only no need up update already existing functions.

6. Events & Communication:
Use Qt’s signal and slot mechanism (pyqtSignal, connect(), etc.) for event handling and inter-component communication.

7. Code Style:
Follow all code style and naming conventions already established in the project.
Match existing indentation, structure, and formatting.

8. Modularity & Maintainability:
Make code modular; each class or function should serve a single responsibility.
Design components to be easy to test and maintain.

## Summary:
Generate code that:

- Processes data using Polars
- Builds UI with Qt
- Uses @dataclasses.dataclass for serializable classes
- Has type hints everywhere
- Includes docstrings for all entities
- Employs Qt signal/slot for events
- Follows project’s code style
- Is modular and adheres to the Single Responsibility Principle
