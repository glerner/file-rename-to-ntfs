# Python File Renamer Refactoring Guide

## Overview

This document outlines a comprehensive plan for refactoring the File Renamer application into a more modular, testable structure. The current implementation contains large, complex methods that are difficult to test and maintain. This refactoring would break down these methods into smaller, independent functions that can be individually tested.

## Refactoring Goals

1. Improve testability of individual components
2. Enhance maintainability through smaller, focused functions
3. Reduce complexity of individual code units
4. Enable more precise error handling
5. Create a foundation for future enhancements

## Refactoring Scope

### 1. Core Function Extraction (High Priority)

The `_clean_filename` method should be broken down into these independent functions:

#### Unit Processing Functions
- `detect_unit(part: str) -> bool`: Determine if a string contains a unit
- `is_space_separated_unit(parts: List[str], i: int, j: int) -> bool`: Check if parts[i] and parts[j] form a space-separated unit
- `process_unit(part: str) -> str`: Process a part containing a unit
- `combine_unit_parts(parts: List[str], i: int, j: int) -> str`: Combine space-separated unit parts

#### Abbreviation Processing Functions
- `detect_abbreviation(part: str) -> bool`: Determine if a string is an abbreviation
- `process_standard_abbreviation(part: str) -> str`: Handle common abbreviations (e.g., "Dr.", "Mr.")
- `process_technical_abbreviation(part: str) -> str`: Handle technical abbreviations
- `process_domain_specific_abbreviation(part: str) -> str`: Handle domain-specific abbreviations
- `handle_abbreviation_boundaries(part: str, prev_part: str) -> str`: Process boundaries between abbreviations

#### Preserved Terms Processing
- `identify_terms_to_preserve(filename: str) -> List[str]`: Identify terms in the original filename that should be preserved
- `replace_with_markers(filename: str, terms_to_preserve: List[str]) -> str`: Replace preserved terms with markers in the initial processing
- `is_preserved_term_marker(part: str) -> bool`: Check if a part is a preserved term marker
- `store_preserved_term_mapping(original_term: str) -> str`: Generate and store a marker for a preserved term
- `restore_preserved_terms(processed_filename: str, term_mapping: Dict[str, str]) -> str`: Replace markers with original preserved terms in the final filename
- `handle_periods_in_preserved_terms(term: str) -> str`: Special handling for periods within preserved terms

#### Contraction Processing
- `detect_contraction(part: str) -> bool`: Identify contractions
- `process_contraction(part: str) -> str`: Process contractions appropriately

#### Word Boundary Processing
- `detect_word_boundaries(part: str) -> List[int]`: Identify word boundaries within a part
- `split_at_boundaries(part: str, boundaries: List[int]) -> List[str]`: Split a part at identified boundaries
- `process_word_boundaries(part: str) -> str`: Process and normalize word boundaries

#### Character Replacement
- `replace_special_chars(text: str) -> str`: Replace special characters with NTFS-compatible alternatives
- `replace_quotes(text: str) -> str`: Handle quote replacement specifically
- `final_quote_processing(text: str) -> str`: Process any remaining quotes

#### Extension Handling
- `process_extension(extension: str) -> str`: Process file extensions

### 2. State Management Refactoring

Current state variables to be managed:
- `processed_parts`
- `prev_was_abbrev`
- `prior_abbreviation`
- `prior_date_part`
- `last_real_word`
- `preserved_terms`

Options:
1. Create a `FilenameProcessingState` class to encapsulate state
2. Pass state explicitly between functions
3. Use a context manager to handle state

### 3. Test Infrastructure

#### Test Directory Structure
```
tests/
├── unit/
│   ├── test_unit_processing.py
│   ├── test_abbreviation_processing.py
│   ├── test_preserved_terms.py
│   ├── test_contraction_processing.py
│   ├── test_word_boundary_processing.py
│   ├── test_character_replacement.py
│   └── test_extension_handling.py
├── integration/
│   └── test_filename_cleaning.py
└── fixtures/
    └── sample_filenames.py
```

#### Test Case Examples
```python
def test_detect_unit():
    assert detect_unit("5kg") == True
    assert detect_unit("kg") == False
    assert detect_unit("hello") == False

def test_is_space_separated_unit():
    assert is_space_separated_unit(["5", "kg"], 0, 1) == True
    assert is_space_separated_unit(["hello", "world"], 0, 1) == False

def test_identify_terms_to_preserve():
    assert "v1.0.5" in identify_terms_to_preserve("Application v1.0.5 Setup.exe")
    assert "A.B.C" in identify_terms_to_preserve("Test A.B.C File.txt")

def test_replace_with_markers():
    filename = "Application v1.0.5 Setup.exe"
    terms = ["v1.0.5"]
    result = replace_with_markers(filename, terms)
    assert "__PRESERVED_TERM_" in result
    assert "v1.0.5" not in result

def test_restore_preserved_terms():
    mapping = {"__PRESERVED_TERM_123__": "v1.0.5"}
    processed = "Application __PRESERVED_TERM_123__ Setup.exe"
    result = restore_preserved_terms(processed, mapping)
    assert result == "Application v1.0.5 Setup.exe"
    assert "__PRESERVED_TERM_123__" not in result
```

## Estimated Time Investment

| Task | Estimated Hours | Complexity |
|------|----------------|------------|
| Function Extraction | 10-14 | High |
| State Management | 4-6 | Medium |
| Test Infrastructure | 3-4 | Low |
| Unit Test Writing | 8-10 | Medium |
| Integration Tests | 4-6 | Medium |
| Documentation | 2-4 | Low |
| **Total** | **31-44** | **High** |

## Implementation Strategy

### Phase 1: Initial Extraction
1. Create skeleton functions with proper signatures
2. Extract logic from `_clean_filename` into appropriate functions
3. Ensure original functionality is maintained

### Phase 2: State Management
1. Design state management approach
2. Refactor functions to use new state management
3. Verify behavior remains unchanged

### Phase 3: Testing
1. Set up test infrastructure
2. Write unit tests for each function
3. Create integration tests for end-to-end validation

## Benefits of Refactoring

1. **Improved Testability**: Each function can be tested in isolation
2. **Better Error Handling**: Specific error handling for each function
3. **Enhanced Maintainability**: Smaller, focused functions are easier to understand
4. **Easier Debugging**: Pinpoint issues to specific functions
5. **Code Reuse**: Functions can be reused in other contexts
6. **Clearer Documentation**: Each function can be clearly documented

## Challenges

1. **Maintaining Behavior**: Ensuring refactored code behaves exactly like the original
2. **State Management**: Handling shared state between functions
3. **Edge Cases**: Identifying and handling edge cases at function boundaries
4. **Test Coverage**: Ensuring comprehensive test coverage
5. **Performance**: Potential minor performance impact from function calls

## Conclusion

While this refactoring represents a significant investment of time (31-44 hours), the benefits in terms of maintainability, testability, and future development would be substantial. The resulting code would be more robust, easier to debug, and provide a solid foundation for future enhancements.
