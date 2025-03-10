#!/usr/bin/env python3
"""
Pytest configuration file to ensure exceptions are properly displayed.

This module implements the pytest_exception_interact hook to ensure all unhandled
exceptions are displayed with detailed location information during test runs.
"""

import sys
import traceback
import re
import pytest
from _pytest.config import hookimpl
import builtins
original_excepthook = sys.excepthook


# Common function to format and display exception details
def format_exception_details(exc_type, exc_value, exc_traceback):
    """
    Format exception details in a consistent way.
    
    Returns True if the exception was handled, False otherwise.
    """
    # Skip AssertionErrors
    if exc_type == AssertionError:
        return False
        
    # Get the most recent frame from the traceback for location information
    tb_frames = traceback.extract_tb(exc_traceback)
    
    # Find the frame from the user's code (not from pytest or library code)
    user_frame = None
    for frame in reversed(tb_frames):
        if '/site-packages/' not in frame.filename and '/usr/lib/' not in frame.filename:
            user_frame = frame
            break
    
    if not user_frame and tb_frames:
        user_frame = tb_frames[-1]  # Use the most recent frame if no user frame found
    
    # Format location information if available
    location = f"{user_frame.filename}:{user_frame.lineno} (in {user_frame.name})" if user_frame else "unknown location"
    
    # Get the actual code line from the file
    code_line = ""
    if user_frame:
        try:
            with open(user_frame.filename, 'r') as f:
                lines = f.readlines()
                if 0 <= user_frame.lineno - 1 < len(lines):
                    code_line = lines[user_frame.lineno - 1].strip()
        except Exception:
            pass
    
    # Print directly to stderr to bypass pytest's output capture
    print(f"\n==== EXCEPTION DETAILS ====", file=sys.__stderr__)
    print(f"Exception Type: {exc_type.__name__}", file=sys.__stderr__)
    print(f"Exception Message: {exc_value}", file=sys.__stderr__)
    print(f"Location: {location}", file=sys.__stderr__)
    if code_line:
        print(f"\n    {code_line}", file=sys.__stderr__)
    print("==== END EXCEPTION DETAILS ====\n", file=sys.__stderr__)
    
    return True


def pytest_exception_interact(report, call):
    """
    This function is called by pytest when an exception occurs during test execution.

    It prints concise exception information directly to stderr, bypassing pytest's
    output capture system to ensure the information is always visible.

    It filters out AssertionError details for test failures that are already
    well-explained by the test output, but keeps detailed information for actual code errors.
    """
    if call.excinfo:
        exc_type, exc_value, exc_traceback = call.excinfo._excinfo
        format_exception_details(exc_type, exc_value, exc_traceback)


def pytest_internalerror(excrepr, excinfo):
    """
    This function is called by pytest when an internal error occurs.

    It prints concise information about internal pytest errors directly to stderr.
    """
    try:
        tb_frames = traceback.extract_tb(excinfo.tb)

        # Find the frame from the user's code (not from pytest or library code)
        user_frame = None
        for frame in reversed(tb_frames):
            if '/site-packages/' not in frame.filename and '/usr/lib/' not in frame.filename:
                user_frame = frame
                break

        if not user_frame and tb_frames:
            user_frame = tb_frames[-1]  # Use the most recent frame if no user frame found

        location = f"{user_frame.filename}:{user_frame.lineno} (in {user_frame.name})" if user_frame else "unknown location"

        # Get the actual code line from the file
        code_line = ""
        if user_frame:
            try:
                with open(user_frame.filename, 'r') as f:
                    lines = f.readlines()
                    if 0 <= user_frame.lineno - 1 < len(lines):
                        code_line = lines[user_frame.lineno - 1].strip()
            except Exception:
                pass
    except Exception:
        location = "unknown location"
        code_line = ""

    # Print directly to stderr to bypass pytest's output capture
    print(f"\n==== INTERNAL ERROR DETAILS ====", file=sys.__stderr__)
    print(f"Exception Type: {excinfo.type.__name__}", file=sys.__stderr__)
    print(f"Exception Message: {excinfo.value}", file=sys.__stderr__)
    print(f"Location: {location}", file=sys.__stderr__)
    if code_line:
        print(f"\n    {code_line}", file=sys.__stderr__)
    print("==== END INTERNAL ERROR DETAILS ====\n", file=sys.__stderr__)


# Create a custom exception hook to catch all exceptions
def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom exception hook to display all exceptions in our format."""
    # Use the common formatting function
    if format_exception_details(exc_type, exc_value, exc_traceback):
        # If the exception was handled by our formatter, still call the original
        # excepthook to maintain normal behavior
        return original_excepthook(exc_type, exc_value, exc_traceback)
    else:
        # If our formatter didn't handle it (e.g., for AssertionErrors),
        # just use the original excepthook
        return original_excepthook(exc_type, exc_value, exc_traceback)


# Install our custom exception hook
sys.excepthook = custom_excepthook


@hookimpl(trylast=True)
def pytest_runtest_logreport(report):
    """
    Modify the test report to hide test case details in the output.
    
    This hook intercepts the test report before it's displayed and removes
    detailed test case data that can clutter the output.
    """
    # Only modify AssertionError reports, not other exceptions
    if (report.when == "call" and 
        hasattr(report, "longrepr") and 
        report.longrepr and 
        hasattr(report, "excinfo") and 
        report.excinfo and 
        report.excinfo.type == AssertionError):
        
        # Convert longrepr to string if it's not already
        if not isinstance(report.longrepr, str):
            longrepr_str = str(report.longrepr)
        else:
            longrepr_str = report.longrepr
            
        # Remove test case data from the output
        # This pattern matches Python data structures that are typically test cases
        simplified = re.sub(r'test_cases\s*=\s*\[.*?\]\s*', 'test_cases = [...] ', longrepr_str, flags=re.DOTALL)
        
        # Also remove other variable dumps that contain large data structures
        simplified = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\{[^{}]*(\'[^\']*\'[^{}]*)*\}', r'\1 = {...}', simplified)
        simplified = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\[[^\[\]]*(\'[^\']*\'[^\[\]]*)*\]', r'\1 = [...]', simplified)
        
        # If longrepr is an object with a string representation, we need to modify it differently
        if not isinstance(report.longrepr, str):
            try:
                report.longrepr.reprtraceback.reprentries[-1].reprfileloc.message = simplified
            except (AttributeError, IndexError):
                pass  # If we can't modify it this way, leave it as is
        else:
            report.longrepr = simplified
