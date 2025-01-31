#!/usr/bin/env python3
"""
File Renamer - Convert filenames from Ext4 to NTFS-compatible format.

This script safely renames files to be compatible with NTFS filesystem while preserving
UTF-8/UTF-16 characters and applying title case formatting rules.

Note on character encoding:
- Input filenames must be valid UTF-8 or UTF-16
- NTFS internally uses UTF-16 LE for filenames
- Maximum path length is 255 UTF-16 characters
- All replacement characters are validated to be valid UTF-16

Future improvements:
- Add option to convert to ASCII-only filenames (if needed for legacy systems)
  Current implementation preserves UTF-8/UTF-16 which works well with modern systems,
  including media files from sources like YouTube.

Author: Cascade AI
Date: 2025-01-27
"""

import os
import re
from typing import Dict, List, Tuple
from pathlib import Path
import unicodedata
import logging

class FileRenamer:
    """Handles the conversion of filenames from Ext4 to NTFS format."""

    # Character substitution mappings
    CHAR_REPLACEMENTS = {
        '\\': '⧵',  # Reverse Solidus Operator
        ':': 'ː',   # Modifier Letter Triangular Colon
        '*': '✱',   # Heavy Asterisk
        '?': '⁇',   # Reversed Question Mark
        '"': '＂',  # Full Width Quotation Mark
        '<': '❬',   # Medium Left-Pointing Angle Bracket Ornament
        '>': '❭',   # Medium Right-Pointing Angle Bracket Ornament
        '|': '│',   # Box Drawings Light Vertical
        '&': 'and', # Replace ampersand with 'and'
        '$': '＄',  # Full Width Dollar Sign
        '!': '!',   # Keep exclamation mark but collapse multiples
        '...': '…',  # Replace three or more periods with ellipsis character
    }

    # Characters that are allowed to be preserved at the end of filenames
    # Should always use the replacement characters from CHAR_REPLACEMENTS
    ALLOWED_TRAILING_CHARS = {
        ')', ']', '}',  # Closing brackets
        '!',            # Exclamation mark (already decided to keep)
        '＄',           # Full Width Dollar Sign (from CHAR_REPLACEMENTS)
        '＂',           # Full Width Quotation Mark (from CHAR_REPLACEMENTS)
    }

    # Only include special characters that should act as word boundaries
    word_boundary_chars = {
        '⧵', 'ː', '✱', '⁇', '│', '＂',  # Special character replacements
        '.', ' ', '-',                    # Standard word boundaries
        '❬', '❭',                        # Angle brackets
        '…'                              # Ellipsis
    }

    # File extensions where we want to preserve the original case
    PRESERVE_CASE_EXTENSIONS = {
        # Web
        'html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'vue', 'php',
        # Documentation
        'md', 'rst', 'log',
        # Data
        'json', 'yaml', 'yml', 'xml', 'csv', 'sql',
        # Programming
        'py', 'ipynb', 'java', 'c', 'cpp', 'h', 'hpp',
        'cs', 'go', 'rs', 'rb', 'pl', 'sh', 'bash',
        # Config
        'ini', 'conf', 'cfg', 'env',
        # Build
        'make', 'cmake', 'gradle', 'pom',
    }

    @classmethod
    def validate_replacements(cls) -> None:
        """
        Validate the CHAR_REPLACEMENTS dictionary.
        Raises ValueError if any replacement is invalid.
        """
        for original_char, replacement_char in cls.CHAR_REPLACEMENTS.items():
            if not isinstance(original_char, str) or not isinstance(replacement_char, str):
                raise ValueError(
                    f"Invalid type in CHAR_REPLACEMENTS: {original_char} -> {replacement_char}. "
                    "Both key and value must be strings."
                )
            if len(original_char) != 1 and original_char != '...':
                raise ValueError(
                    f"Invalid original character in CHAR_REPLACEMENTS: {original_char}. "
                    "Original character must be a single character or '...'."
                )
            if not replacement_char:
                raise ValueError(
                    f"Invalid replacement for {original_char} in CHAR_REPLACEMENTS. "
                    "Replacement cannot be empty."
                )

            # Validate UTF-16 encoding
            try:
                replacement_char.encode('utf-16le')
            except UnicodeEncodeError:
                raise ValueError(
                    f"Invalid replacement character {replacement_char!r} for {original_char!r}. "
                    "All characters must be valid UTF-16."
                )

    # Common words that should not be capitalized in titles
    LOWERCASE_WORDS = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in',
        'is', 'of', 'on', 'or', 'the', 'to', 'up', 'with', 'yet'
    }

    def __init__(self, directory: str = '.', dry_run: bool = False):
        """
        Initialize the FileRenamer.

        Args:
            directory (str): Directory to process files in
            dry_run (bool): If True, only show what would be renamed without making changes
        """
        self.directory = Path(directory)
        self.dry_run = dry_run

        # Define word boundary delimiters
        self.delimiters = [' ', '.', '-']

        # Build the split pattern from delimiters and single-char replacements
        special_chars = [replacement_char for original_char, replacement_char in self.CHAR_REPLACEMENTS.items()
            if len(replacement_char) == 1]  # Only single-char replacements
        split_chars = self.delimiters + special_chars
        self.split_pattern = f"([{''.join(re.escape(c) for c in split_chars)}])"
        self.special_chars = set(special_chars)  # For faster lookups

    def _clean_filename(self, filename: str) -> str:
        """Clean filename to be NTFS-compatible."""
        try:
            filename.encode('utf-16')
        except UnicodeEncodeError as e:
            raise ValueError(f"Input filename contains invalid characters: {e}")

        # Split into name and extension
        name_parts = filename.rsplit('.', 1)
        name = name_parts[0]
        extension = name_parts[1].lower() if len(name_parts) > 1 else ''

        # For known file extensions (like .py, .js, .css):
        # - Keep the original filename case (don't title case it)
        # - Always use lowercase for the extension
        preserve_name_case = extension.lower() in self.PRESERVE_CASE_EXTENSIONS

        # First normalize all whitespace to single spaces
        print(f"\nBefore whitespace normalization: {name!r}")
        name = re.sub(r'[\n\r\t\f\v]+', ' ', name)  # Convert newlines and other whitespace to spaces
        name = re.sub(r' {2,}', ' ', name)  # Collapse multiple spaces
        print(f"After whitespace normalization: {name!r}")

        # Replace special characters
        print(f"Before special char replacement: {name!r}")
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if original_char == '...':
                # Handle ellipsis separately to avoid over-replacement
                print(f"Before ellipsis replacement: {name!r}")
                name = re.sub(r'\.{3,}', replacement_char, name)
                print(f"After ellipsis replacement: {name!r}")
            else:
                # Replace multiple occurrences with single replacement
                name = re.sub(f'{re.escape(original_char)}+', replacement_char, name)
        print(f"After special char replacement: {name!r}")

        name = name.strip()  # Remove leading/trailing spaces
        print(f"After strip: {name!r}")

        # Only remove trailing periods and ellipsis if they're actually at the end
        # (no more text after them)
        while name and (name.endswith('.') or name.endswith('…')):
            # Check if there's more text after the trailing dots
            rest = name.rstrip('.…').strip()
            if not rest:  # If empty, this is truly trailing
                name = rest
            else:
                break  # There's more text after, so keep the periods/ellipsis
        print(f"After trailing cleanup: {name!r}")

        # For normal files, apply title case to the name
        # For known extensions (like .py files), keep original name case
        if not preserve_name_case:
            # Build pattern that matches our word boundaries
            split_pattern = '([' + ''.join(re.escape(c) for c in self.word_boundary_chars) + '])'
            print(f"\nSplit pattern: {split_pattern}")
            parts = re.split(split_pattern, name)
            print(f"Parts after split: {parts}")
            titled_parts = []
            prev_part = ''

            # Find the last real word (non-separator) in advance
            last_real_word = None
            for part in parts:
                if part and len(part) > 1 and not any(c in self.word_boundary_chars for c in part):
                    last_real_word = part.lower()

            # Now process each part
            for part in parts:
                if not part:  # Skip empty parts
                    continue

                # Keep separators as is
                if len(part) == 1 and part in self.word_boundary_chars:
                    print(f"Keeping separator: {part!r}")
                    titled_parts.append(part)
                    prev_part = part
                    continue

                # Convert to title case, handling special cases
                word = part.lower()  # First convert to lowercase

                # Check if this word should stay lowercase
                # Word should be lowercase if:
                # 1. It's in our LOWERCASE_WORDS set
                # 2. It's not the first word
                # 3. It's not after a period or ellipsis
                # 4. It's not the last word
                # 5. It's between spaces (not after special chars)
                print(f"\nWord: {word!r}")
                print(f"In LOWERCASE_WORDS: {word in self.LOWERCASE_WORDS}")
                print(f"Not first word: {bool(titled_parts)}")
                print(f"After space: {prev_part == ' '}")
                print(f"Not last word: {word != last_real_word}")
                print(f"Previous parts: {titled_parts[-2:] if len(titled_parts) >= 2 else []}")

                # Check if we're between spaces
                is_between_spaces = (
                    prev_part == ' ' and  # Current word follows a space
                    (len(titled_parts) < 2 or  # Start of string
                     (titled_parts[-1] == ' ' and  # Previous was space
                      (len(titled_parts) < 3 or   # Beginning of string
                       titled_parts[-2] not in self.word_boundary_chars - {' '})))  # Not after special char
                )

                # Always capitalize after a period/ellipsis or if it's the first/last word
                should_capitalize = (
                    not titled_parts or  # First word
                    prev_part in {'.', '…'} or  # After period or ellipsis
                    word == last_real_word  # Last word
                )

                if (word in self.LOWERCASE_WORDS and
                    titled_parts and      # Not first word
                    not should_capitalize and  # Not after period/ellipsis
                    word != last_real_word and  # Not the last word
                    is_between_spaces):   # Between spaces, not after special char
                    print(f"Should be lowercase: True")
                    titled_parts.append(word)
                else:
                    print(f"Should be lowercase: False")
                    titled_parts.append(word.capitalize())
                prev_part = part

            name = ''.join(titled_parts)

        # If original had no spaces, remove spaces around special characters
        if ' ' not in filename:
            for char in self.special_chars - {' '}:
                name = name.replace(f' {char} ', char)
                name = name.replace(f' {char}', char)
                name = name.replace(f'{char} ', char)

        # Always use lowercase for extensions, whether known or unknown
        return f"{name}.{extension}" if extension else name

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
    """Rename files to be NTFS-compatible."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Rename files to be NTFS-compatible while preserving UTF-8/UTF-16 characters',
        add_help=True,  # This adds -h/--help by default
    )
    parser.add_argument('directory', nargs='?', default='.',
                      help='Directory containing files to rename')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be renamed without making changes')

    # Add a custom -? help option
    parser.add_argument('-?', action='help',
                      help='Show this help message and exit')

    args = parser.parse_args()

    renamer = FileRenamer(args.directory)
    changes = renamer.process_files()

    if args.dry_run:
        print("\nProposed changes (dry run):")
    else:
        print("\nExecuted changes:")

    for old, new in changes:
        print(f"'{old}'\n  -> '{new}'\n")

    if not args.dry_run:
        confirm = input("Apply these changes? [y/N] ")
        if confirm.lower() != 'y':
            print("No changes made.")
            return

        # Actually rename the files
        for old, new in changes:
            try:
                os.rename(old, new)
            except OSError as e:
                print(f"Error renaming {old}: {e}")

# Validate replacements when module is loaded
FileRenamer.validate_replacements()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
