#!/usr/bin/env python3
"""
Test script for the settings file functionality in file_renamer.py.

This script tests loading user settings from a settings.ini file.
"""

import os
import sys
import tempfile
from pathlib import Path

# Import the FileRenamer class from file_renamer.py
from file_renamer import FileRenamer

def test_settings_file_loading():
    """Test loading settings from a file."""
    # Create a temporary settings file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as temp:
        temp.write("""
# Test settings file
[abbreviations]
AI
ML
MyCompany
AWS

[preserved_terms]
My Product Name
Company-Specific™ Term
Star Trek: The Next Generation
""")
        temp_path = temp.name

    try:
        # Enable debug output
        FileRenamer._debug = True
        os.environ['RENAMER_DEBUG'] = 'normal'

        # Load settings from the temporary file
        user_abbreviations, user_preserved_terms = FileRenamer.load_user_settings(temp_path)

        # Verify abbreviations
        expected_abbreviations = {'AI', 'ML', 'MyCompany', 'AWS'}
        assert user_abbreviations == expected_abbreviations, \
            f"Expected abbreviations {expected_abbreviations}, got {user_abbreviations}"

        # Verify preserved terms
        expected_preserved_terms = {'My Product Name', 'Company-Specific™ Term', 'Star Trek: The Next Generation'}
        assert user_preserved_terms == expected_preserved_terms, \
            f"Expected preserved terms {expected_preserved_terms}, got {user_preserved_terms}"

        print("✅ Settings file loading test passed!")
    finally:
        # Clean up the temporary file
        os.unlink(temp_path)

def test_settings_file_validation():
    """Test validation of settings entries."""
    # Valid entries
    assert FileRenamer._is_valid_settings_entry("Valid Entry"), "Should accept valid entry"
    assert FileRenamer._is_valid_settings_entry("Special Chars: !@#$%^&*()"), "Should accept special chars"
    
    # Invalid entries (control characters)
    assert not FileRenamer._is_valid_settings_entry("Invalid\x00Entry"), "Should reject null byte"
    assert not FileRenamer._is_valid_settings_entry("Invalid\tEntry"), "Should reject tab"
    
    # Test entry that's too long (> 255 UTF-16 chars)
    long_entry = "x" * 256
    assert not FileRenamer._is_valid_settings_entry(long_entry), "Should reject entry > 255 chars"
    
    print("✅ Settings validation test passed!")

def test_settings_file_search():
    """Test finding settings file in standard locations."""
    # Create a temporary directory to simulate user's home
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save original home directory
        original_home = os.environ.get('HOME')
        
        # Check if settings.ini exists in current directory and temporarily rename it
        current_settings = os.path.join(os.getcwd(), 'settings.ini')
        current_exists = os.path.exists(current_settings)
        temp_name = None
        
        if current_exists:
            # Temporarily rename the existing settings file
            temp_name = current_settings + '.bak'
            os.rename(current_settings, temp_name)
            print(f"Temporarily renamed existing settings.ini to {temp_name}")
        
        try:
            # Set home to temp directory for testing
            os.environ['HOME'] = temp_dir
            
            # Create .config/file_renamer directory
            config_dir = os.path.join(temp_dir, '.config', 'file_renamer')
            os.makedirs(config_dir, exist_ok=True)
            
            # Create settings file in home directory
            home_settings = os.path.join(config_dir, 'settings.ini')
            with open(home_settings, 'w') as f:
                f.write("# Home settings file")
            
            # Test finding settings in home directory (should find home since current doesn't exist)
            found = FileRenamer._find_settings_file()
            assert found == home_settings, f"Expected {home_settings}, got {found}"
            
            # Create settings file in current directory
            with open(current_settings, 'w') as f:
                f.write("# Current directory settings file")
            
            # Test finding settings in current directory (should take precedence)
            found = FileRenamer._find_settings_file()
            assert found == current_settings, f"Expected {current_settings}, got {found}"
            
            # Clean up temporary file
            os.unlink(current_settings)
            
            # Test explicit path
            explicit_path = os.path.join(temp_dir, 'explicit_settings.ini')
            with open(explicit_path, 'w') as f:
                f.write("# Explicit settings file")
            
            found = FileRenamer._find_settings_file(explicit_path)
            assert found == explicit_path, f"Expected {explicit_path}, got {found}"
            
            print("✅ Settings file search test passed!")
        finally:
            # Restore original home directory
            if original_home:
                os.environ['HOME'] = original_home
                
            # Restore the original settings file if it existed
            if temp_name and os.path.exists(temp_name):
                if os.path.exists(current_settings):
                    os.unlink(current_settings)  # Remove any test file that might be left
                os.rename(temp_name, current_settings)
                print(f"Restored original settings.ini")

def test_settings_integration():
    """Test integration with FileRenamer class."""
    # Create a temporary settings file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as temp:
        temp.write("""
# Test settings file
[abbreviations]
AI
ML

[preserved_terms]
My Product Name
""")
        temp_path = temp.name

    try:
        # Create a FileRenamer instance with the settings file
        renamer = FileRenamer('.', dry_run=True, settings_path=temp_path)
        
        # Verify that the settings were loaded
        assert 'AI' in renamer.user_abbreviations, "AI should be in user_abbreviations"
        assert 'ML' in renamer.user_abbreviations, "ML should be in user_abbreviations"
        assert 'My Product Name' in renamer.user_preserved_terms, "My Product Name should be in user_preserved_terms"
        
        # Verify that the class variables were updated
        assert 'AI' in FileRenamer.USER_ABBREVIATIONS, "AI should be in USER_ABBREVIATIONS"
        assert 'ML' in FileRenamer.USER_ABBREVIATIONS, "ML should be in USER_ABBREVIATIONS"
        assert 'My Product Name' in FileRenamer.USER_PRESERVED_TERMS, "My Product Name should be in USER_PRESERVED_TERMS"
        
        print("✅ Settings integration test passed!")
    finally:
        # Clean up the temporary file
        os.unlink(temp_path)

def main():
    """Run all tests."""
    print("Running settings file tests...\n")
    
    test_settings_file_loading()
    test_settings_file_validation()
    test_settings_file_search()
    test_settings_integration()
    
    print("\nAll tests passed! 🎉")

if __name__ == "__main__":
    main()
