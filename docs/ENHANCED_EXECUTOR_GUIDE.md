# Enhanced NodeExecutor - Usage Guide

The enhanced NodeExecutor provides a robust, secure, and feature-rich Python code execution environment for TriggerEditor nodes.

## Key Features

### 🛡️ Security Features
- **Execution Timeouts**: Prevent infinite loops and runaway code
- **Memory Limits**: Protect against memory exhaustion
- **Sandbox Execution**: Restricted built-in functions and imports
- **Code Validation**: Pre-execution security checks

### 📊 Monitoring & Analytics
- **Execution Statistics**: Track performance metrics over time
- **Memory Usage**: Monitor memory consumption per execution
- **Execution History**: Keep detailed logs of past executions
- **Performance Profiling**: Detailed timing and resource usage

### 🔧 Advanced Execution
- **Context Management**: Shared variables between node executions
- **Error Handling**: Comprehensive error reporting with stack traces
- **Output Capture**: Capture both stdout and stderr
- **Cancellation Support**: Interrupt long-running executions

## Quick Start

### Basic Usage

```python
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor

# Create executor with default settings
executor = NodeExecutor()

# Execute node code
result = executor.execute_node(node)

if result.success:
    print(f"Output: {result.output}")
    print(f"Variables: {result.variables}")
else:
    print(f"Error: {result.error}")
```

### With Custom Security Configuration

```python
from trigger_designer.core.ExecutionCheck.executor import (
    NodeExecutor, SecurityConfig
)

# Create custom security config
security_config = SecurityConfig(
    max_execution_time=10.0,  # 10 second timeout
    max_memory_mb=256.0,      # 256MB memory limit
    allow_file_access=False,  # No file operations
    allowed_imports={'pandas', 'numpy', 'math'}  # Limited imports
)

executor = NodeExecutor(security_config=security_config)
```

### Monitoring Execution Statistics

```python
# Execute several nodes
for node in nodes:
    result = executor.execute_node(node)
    print(f"Execution time: {result.execution_time:.4f}s")

# Get overall statistics
stats = executor.get_statistics()
print(f"Total executions: {stats.total_executions}")
print(f"Success rate: {stats.successful_executions / stats.total_executions * 100:.1f}%")
print(f"Average execution time: {stats.average_execution_time:.4f}s")

# Get execution history
history = executor.get_execution_history(limit=10)  # Last 10 executions
for result in history:
    print(f"{result.timestamp}: {'✅' if result.success else '❌'}")
```

## ExecutionResult Object

The `execute_node()` method returns a comprehensive `ExecutionResult` object:

```python
@dataclass
class ExecutionResult:
    success: bool                    # Whether execution succeeded
    output: str                      # Captured stdout
    error: str                       # Error message if failed
    variables: Dict[str, Any]        # Variables created during execution
    execution_time: float            # Time taken (seconds)
    memory_used: float              # Memory used (MB)
    peak_memory: float              # Peak memory during execution (MB)
    lines_executed: int             # Number of code lines
    warnings: List[str]             # Security/other warnings
    timestamp: datetime             # When execution occurred
```

## Security Configuration

```python
@dataclass
class SecurityConfig:
    max_execution_time: float = 30.0        # Max execution time (seconds)
    max_memory_mb: float = 512.0            # Max memory usage (MB)
    allowed_imports: Set[str] = {...}       # Allowed import modules
    forbidden_functions: Set[str] = {...}   # Forbidden function calls
    allow_file_access: bool = False         # Allow file operations
    allow_network_access: bool = False      # Allow network operations
```

### Default Allowed Imports
- **Math/Utilities**: `math`, `random`, `datetime`, `json`, `csv`, `re`
- **Collections**: `collections`, `itertools`, `functools`, `operator`
- **Data Science**: `pandas`, `numpy`, `polars`, `matplotlib`, `seaborn`
- **Statistics**: `statistics`

### Default Forbidden Functions
- **Code Execution**: `exec`, `eval`, `compile`
- **File Operations**: `open`, `file`
- **System Access**: `__import__`, `globals`, `locals`
- **User Input**: `input`, `raw_input`
- **System Control**: `exit`, `quit`, `reload`

## Context Management

The executor maintains a shared execution context between node executions:

```python
# First node creates variables
node1_code = """
shared_list = [1, 2, 3, 4, 5]
multiplier = 2
"""
result1 = executor.execute_node(create_node(node1_code))

# Second node uses variables from first
node2_code = """
processed_list = [x * multiplier for x in shared_list]
print(f"Result: {processed_list}")
"""
result2 = executor.execute_node(create_node(node2_code))

# Get context information
context_info = executor.get_context_info()
for name, info in context_info.items():
    print(f"{name}: {info['type']} ({info['size']} bytes)")

# Clear context when needed
executor.clear_context()
```

## Error Handling

The executor provides detailed error information:

```python
result = executor.execute_node(node_with_error)

if not result.success:
    print(f"Error Type: {type(result.error)}")
    print(f"Error Message: {result.error}")
    
    # Check for specific error types
    if "timeout" in result.error.lower():
        print("Execution timed out")
    elif "memory" in result.error.lower():
        print("Memory limit exceeded")
    elif "security" in result.error.lower():
        print("Security violation detected")
```

## Best Practices

### 1. Configure Security Appropriately
```python
# For data processing nodes
data_security = SecurityConfig(
    max_execution_time=60.0,
    max_memory_mb=1024.0,
    allowed_imports={'pandas', 'numpy', 'polars', 'matplotlib'}
)

# For simple calculation nodes  
calc_security = SecurityConfig(
    max_execution_time=5.0,
    max_memory_mb=128.0,
    allowed_imports={'math', 'statistics'}
)
```

### 2. Monitor Performance
```python
# Regular statistics checking
if executor.stats.total_executions % 10 == 0:
    stats = executor.get_statistics()
    if stats.average_execution_time > 1.0:
        print("Warning: Average execution time is high")
```

### 3. Handle Long-Running Operations
```python
import threading

def execute_with_progress(executor, node):
    # Start execution in background
    result_container = [None]
    
    def execute():
        result_container[0] = executor.execute_node(node)
    
    thread = threading.Thread(target=execute)
    thread.start()
    
    # Show progress while waiting
    while thread.is_alive():
        print(".", end="", flush=True)
        time.sleep(0.5)
    
    return result_container[0]
```

### 4. Context Cleanup
```python
# Clear context periodically to prevent memory buildup
if len(executor.get_context_info()) > 50:  # Too many variables
    executor.clear_context()

# Or clear after major operations
executor.execute_node(large_data_processing_node)
executor.clear_context()  # Clean up large datasets
```

## Backward Compatibility

The legacy `execute_node_legacy()` method maintains compatibility with existing code:

```python
# Old API still works
output, variables = executor.execute_node_legacy(node)

# But new API is recommended
result = executor.execute_node(node)
output = result.output
variables = result.variables
```

## Performance Tips

1. **Memory Management**: Clear context after processing large datasets
2. **Timeout Tuning**: Set appropriate timeouts based on expected operation complexity
3. **Import Restrictions**: Limit allowed imports to reduce attack surface
4. **Statistics Monitoring**: Use execution statistics to identify performance bottlenecks
5. **History Limits**: The executor automatically limits history to 100 entries

## Example: Data Processing Pipeline

```python
# Setup executor for data processing
security_config = SecurityConfig(
    max_execution_time=120.0,  # 2 minutes for complex operations
    max_memory_mb=2048.0,      # 2GB for large datasets
    allowed_imports={'pandas', 'numpy', 'polars', 'matplotlib', 'seaborn'}
)

executor = NodeExecutor(security_config=security_config)

# Execute pipeline nodes
nodes = [load_node, clean_node, transform_node, analyze_node, visualize_node]

for i, node in enumerate(nodes):
    print(f"Executing step {i+1}: {node.__class__.__name__}")
    
    result = executor.execute_node(node)
    
    if result.success:
        print(f"✅ Success in {result.execution_time:.2f}s")
        if result.warnings:
            print(f"⚠️  Warnings: {'; '.join(result.warnings)}")
    else:
        print(f"❌ Failed: {result.error}")
        break

# Final statistics
stats = executor.get_statistics()
print(f"Pipeline completed: {stats.successful_executions}/{stats.total_executions} steps successful")
```