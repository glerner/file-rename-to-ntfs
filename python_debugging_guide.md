# Python Debugging Guide

## Global Exception Handling in Python

This guide explains how to implement robust exception handling in Python programs to make debugging easier and prevent silent failures.

## Why Use Global Exception Handling?

When Python programs crash, they sometimes provide limited or cryptic error information. A global exception handler ensures:

1. All unhandled exceptions are caught and displayed
2. Detailed error information (including full tracebacks) is shown
3. Error messages are properly formatted for readability
4. Exceptions are visible even when running with testing frameworks

## Standard Pattern for Python Programs

### 1. In Your Main Python File

Add these imports at the top of your file with other imports:

```python
import sys
import traceback
```

Add this code at the end of your file:

```python
# Define a custom exception handler
def global_exception_handler(exc_type, exc_value, exc_traceback):
    # Write to stderr to bypass pytest output capture
    sys.stderr.write(f"\nGLOBAL HANDLER - Unhandled exception: {exc_type.__name__}: {exc_value}\n")
    sys.stderr.write("\nDetailed traceback:\n")
    sys.stderr.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    sys.stderr.write("\nPlease report this error with the above information.\n")
    sys.stderr.flush()

    # Force the exception to be visible even when running with pytest
    if 'pytest' in sys.modules:
        import pytest
        pytest.fail(f"Unhandled exception: {exc_type.__name__}: {exc_value}")

# Install the custom exception handler
sys.excepthook = global_exception_handler

# Main execution block
if not 'pytest' in sys.modules:
    logging.basicConfig(level=logging.DEBUG)
    try:
        main()  # Call your main function here
    except Exception as e:
        print(f"\nUnhandled exception: {type(e).__name__}: {e}")
        print("\nDetailed traceback:")
        print(traceback.format_exc())
        print("\nPlease report this error with the above information.")
```

### 2. In Your Test Files (Optional)

For test files, you can use a simplified version:

```python
import sys
import traceback

# Define a custom exception handler for tests
def global_exception_handler(exc_type, exc_value, exc_traceback):
    sys.stderr.write(f"\nGLOBAL HANDLER - Unhandled exception: {exc_type.__name__}: {exc_value}\n")
    sys.stderr.write("\nDetailed traceback:\n")
    sys.stderr.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    sys.stderr.write("\nPlease report this error with the above information.\n")
    sys.stderr.flush()

# Install the custom exception handler
sys.excepthook = global_exception_handler
```

## Running Tests with Visible Exceptions

When running tests with pytest, use the `-s` flag or `--capture=no` to ensure all output is visible:

```bash
# Basic test run with visible output
python -m pytest test_file.py -v -s

# Equivalent command
python -m pytest test_file.py -v --capture=no

# With coverage
python -m pytest test_file.py -v -s --cov=your_module
```

## Configurable Debug Levels

For more complex applications, it's helpful to implement multiple debug verbosity levels. This allows users to control how much information is displayed during execution.

### Implementing Debug Levels

Add this function to your code:

```python
def get_debug_level() -> str:
    """
    Get the debug level from environment. Returns one of:
    - 'detail': Show all processing steps (RENAMER_DEBUG=detail)
    - 'normal': Show key transformations only (RENAMER_DEBUG=1 or running tests)
    - 'off': No debug output (default)
    """
    debug_env = os.environ.get('RENAMER_DEBUG')
    if debug_env == 'detail':
        return 'detail'
    if 'unittest' in sys.modules or '--debug' in sys.argv or debug_env:
        return 'normal'
    return 'off'
```

### Using Debug Levels in Your Code

You can then use the debug level to control output verbosity:

```python
debug_level = get_debug_level()

# For important transformations (shown in 'normal' and 'detail' modes)
if debug_level != 'off':
    print(f"Transformed: {original} -> {transformed}")
    
# For detailed step-by-step information (only in 'detail' mode)
if debug_level == 'detail':
    print(f"Processing step: {step_name}")
    print(f"Intermediate result: {intermediate_value}")
```

### Activating Different Debug Levels

Users can activate different debug levels in several ways:

1. **Command-line flag** (normal debug level):
   ```bash
   python your_script.py --debug
   ```

2. **Environment variable** (normal debug level):
   ```bash
   RENAMER_DEBUG=1 python your_script.py
   ```

3. **Detailed debug level**:
   ```bash
   RENAMER_DEBUG=detail python your_script.py
   ```

4. **No debug output** (default):
   ```bash
   python your_script.py
   ```

5. **Automatic in tests**:
   Debug output is automatically enabled when running under unittest or pytest.

### Benefits of Multiple Debug Levels

1. **User control**: Users can choose how much information they want to see
2. **Developer efficiency**: Detailed debugging information available when needed
3. **Clean output**: Regular users aren't overwhelmed with technical details
4. **Troubleshooting**: Detailed mode helps diagnose complex issues

## How This Works

1. **sys.excepthook**: Catches any unhandled exceptions in your program
2. **stderr output**: Bypasses pytest's output capturing
3. **pytest.fail()**: Ensures exceptions cause test failures
4. **try-except block**: Provides a safety net for direct script execution
5. **Condition check**: Prevents main() from running during testing

## When to Use This Pattern

This pattern is most useful for:

- Scripts that might be run directly or imported for testing
- Programs where you want consistent error reporting
- Code that needs to work with pytest
- Any Python program where detailed error information is important

## Benefits

1. Catches any unhandled exceptions from anywhere in the program
2. Provides detailed error information (exception type, message, and full traceback)
3. Makes debugging much easier by showing exactly where errors occur
4. Prevents silent failures with cryptic error messages
5. Works consistently whether running directly or with pytest

## Simpler Alternative

For very simple scripts, you can use just the try-except part:

```python
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\nUnhandled exception: {type(e).__name__}: {e}")
        print("\nDetailed traceback:")
        print(traceback.format_exc())
        print("\nPlease report this error with the above information.")
```

This is sufficient for scripts that don't need the more advanced features of the full pattern.

## Testing Your Global Exception Handler

To verify that your global exception handler is working correctly, you can add code that deliberately triggers an exception. This helps confirm that:

1. Unhandled exceptions are properly caught by the global handler
2. The error information is displayed correctly
3. The traceback shows the exact location of the error

### Example Code

Add this code to your main function, outside of any try-except blocks:

```python
# Deliberately trigger an exception to demonstrate the global exception handler
# This code is outside any try-except block to show how the global handler works
# To trigger the exception, set the TRIGGER_EXCEPTION environment variable to 'true'
# TRIGGER_EXCEPTION=true python your_script.py [arguments]

if os.environ.get('TRIGGER_EXCEPTION', '').lower() == 'true':
    print("\nDeliberately triggering an exception to demonstrate the global exception handler...")
    # This will raise a ZeroDivisionError
    result = 1 / 0
    # This line will never be reached
    print(f"Result: {result}")
```

### Running the Test

To test the global exception handler, run your script with the environment variable set:

```bash
TRIGGER_EXCEPTION=true python your_script.py [arguments]
```

### Expected Output

You should see output similar to this:

```
Deliberately triggering an exception to demonstrate the global exception handler...

Unhandled exception: ZeroDivisionError: division by zero

Detailed traceback:
Traceback (most recent call last):
  File "/path/to/your_script.py", line XXX, in <module>
    main()
  File "/path/to/your_script.py", line YYY, in main
    result = 1 / 0
ZeroDivisionError: division by zero

Please report this error with the above information.
```

This confirms that your global exception handler is working correctly and providing useful debugging information.
