#!/usr/bin/env python3
"""
File Renamer - Convert filenames from Ext4 to NTFS-compatible format.

This script safely renames files to be compatible with NTFS filesystem while preserving
UTF-8/UTF-16 characters and applying title case formatting rules.

Author: Cascade AI
Date: 2025-01-27
"""

import os
import re
from typing import Dict, List, Tuple
from pathlib import Path
import unicodedata

class FileRenamer:
    """Handles the conversion of filenames from Ext4 to NTFS format."""
    
    # Character substitution mappings
    CHAR_REPLACEMENTS = {
        '\\': '⧵',  # Reverse Solidus Operator
        ':': 'ː',   # Modifier Letter Triangular Colon
        '*': '✱',   # Heavy Asterisk
        '?': '❓',   # Black Question Mark Ornament
        '"': '"',   # Left Double Quotation Mark
        '<': '❬',   # Medium Left-Pointing Angle Bracket Ornament
        '>': '❭',   # Medium Right-Pointing Angle Bracket Ornament
        '|': '│',   # Box Drawings Light Vertical
        '\n': ' ',  # Replace newline with space
        '\t': ' ',  # Replace tab with space
        '$': '＄',  # Full Width Dollar Sign
    }

    # Common words that should not be capitalized in titles
    LOWERCASE_WORDS = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 
        'of', 'on', 'or', 'the', 'to', 'up', 'yet'
    }

    def __init__(self, directory: str = '.', dry_run: bool = True):
        """
        Initialize the FileRenamer.

        Args:
            directory (str): Directory to process files in
            dry_run (bool): If True, only show what would be renamed without making changes
        """
        self.directory = Path(directory)
        self.dry_run = dry_run

    def _clean_filename(self, filename: str) -> str:
        """
        Clean a filename according to the specified rules.

        Args:
            filename (str): Original filename

        Returns:
            str: Cleaned filename
        """
        # Replace special characters
        for old, new in self.CHAR_REPLACEMENTS.items():
            filename = filename.replace(old, new)

        # Split into name and extension
        name_parts = filename.rsplit('.', 1)
        name = name_parts[0]
        ext = name_parts[1] if len(name_parts) > 1 else ''

        # Clean up spaces and multiple special characters
        name = re.sub(r'\s+', ' ', name)  # Collapse multiple spaces
        name = re.sub(r'[!.]+$', '', name)   # Remove trailing exclamation marks and periods
        name = name.strip()                # Remove leading/trailing spaces

        # Apply title case with special rules
        words = name.split()
        titled_words = []
        for i, word in enumerate(words):
            # Check if word is all uppercase
            if word.isupper():
                word = word.title()
            
            # Apply lowercase rules for common words (except first and last word)
            if (i != 0 and i != len(words) - 1 and 
                word.lower() in self.LOWERCASE_WORDS):
                word = word.lower()
            else:
                # Preserve existing case if not all uppercase
                if not word.isupper():
                    word = word
                
            titled_words.append(word)

        new_name = ' '.join(titled_words)
        
        # Reassemble with extension if it exists
        return f"{new_name}.{ext}" if ext else new_name

    def process_files(self) -> List[Tuple[str, str]]:
        """
        Process all files in the directory.

        Returns:
            List[Tuple[str, str]]: List of (original_name, new_name) pairs
        """
        changes = []
        
        for item in self.directory.iterdir():
            if item.is_file():
                original_name = item.name
                new_name = self._clean_filename(original_name)
                
                # Skip if no change needed
                if original_name == new_name:
                    continue
                
                # Check if target already exists
                if (self.directory / new_name).exists():
                    print(f"Warning: Cannot rename '{original_name}' to '{new_name}' - target exists")
                    continue
                
                changes.append((original_name, new_name))
                
                if not self.dry_run:
                    item.rename(self.directory / new_name)
        
        return changes

def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Rename files to be NTFS-compatible while preserving UTF-8/UTF-16 characters'
    )
    parser.add_argument('directory', nargs='?', default='.',
                      help='Directory containing files to rename')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be renamed without making changes')
    
    args = parser.parse_args()
    
    renamer = FileRenamer(args.directory, args.dry_run)
    changes = renamer.process_files()
    
    if args.dry_run:
        print("\nProposed changes (dry run):")
    else:
        print("\nExecuted changes:")
    
    for old, new in changes:
        print(f"'{old}'\n  -> '{new}'\n")

if __name__ == '__main__':
    main()
