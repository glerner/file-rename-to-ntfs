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

Author: George Lerner with Cascade AI
Date: 2025-01-27
"""

import os
import re
import sys
from typing import Dict, List, Tuple
from pathlib import Path
import unicodedata
import logging

def is_debug_mode() -> bool:
    """
    Detect if we're running in debug mode. This is true if:
    1. Running under unittest (detected via unittest in sys.modules)
    2. --debug flag was passed
    3. RENAMER_DEBUG environment variable is set
    """
    return (
        'unittest' in sys.modules or
        '--debug' in sys.argv or
        os.environ.get('RENAMER_DEBUG') == '1'
    )

class FileRenamer:
    """Handles the conversion of filenames from Ext4 to NTFS format.

    Extension Rules:
    1. Extensions cannot contain spaces
    2. Extension is the part after the last valid period
    3. Trailing periods are not treated as extension separators
    4. For known extensions (like .py, .js):
       - Keep the original filename case
       - Always use lowercase for the extension
    """

    # Character substitution mappings
    CHAR_REPLACEMENTS = {
        '\\': '⧵',  # Reverse Solidus Operator
        ':': 'ː',   # Modifier Letter Triangular Colon
        '*': '✱',   # Heavy Asterisk
        '?': '⁇',   # Reversed Question Mark
        '"': '＂',  # Full Width Quotation Mark
        '<': '❬',   # Left Black Lenticular Bracket
        '>': '❭',   # Right Black Lenticular Bracket
        '<<': '《',  # Left Double Angle Bracket
        '>>': '》',  # Right Double Angle Bracket
        '[[': '⟦',  # Mathematical Left White Square Bracket
        ']]': '⟧',  # Mathematical Right White Square Bracket
        '{{': '⦃',  # Left White Curly Bracket
        '}}': '⦄',  # Right White Curly Bracket
        '|': '│',   # Box Drawings Light Vertical
        '&': 'and', # Replace ampersand with 'and'
        '$': '＄',  # Full Width Dollar Sign
        '!': '!',   # Keep exclamation mark but collapse multiples
        '...': '…',  # Replace three or more periods with ellipsis character
    }

    # All opening bracket characters (ASCII and replacements)
    OPENING_BRACKETS = {
        # ASCII opening brackets
        '(', '[', '{', '<',
        # Replacement opening brackets
        '❬',  # Left Black Lenticular Bracket
        '《',  # Left Double Angle Bracket
        '⟦',  # Mathematical Left White Square Bracket
        '⦃',  # Left White Curly Bracket
    }

    # All closing bracket characters (ASCII and replacements)
    CLOSING_BRACKETS = {
        # ASCII closing brackets
        ')', ']', '}', '>',
        # Replacement closing brackets
        '❭',  # Right Black Lenticular Bracket
        '》',  # Right Double Angle Bracket
        '⟧',  # Mathematical Right White Square Bracket
        '⦄',  # Right White Curly Bracket
    }

    # Characters that are allowed at the end of a filename
    ALLOWED_TRAILING_CHARS = CLOSING_BRACKETS | {
        '!',            # Exclamation mark
        '＄',           # Full Width Dollar Sign
        '＂',           # Full Width Quotation Mark
        '⁇',           # Double Question Mark
    }

    # Only include special characters that should act as word boundaries
    WORD_BOUNDARY_CHARS = {
        '⧵', 'ː', '✱', '⁇', '│', '＂',  # Special character replacements
        '.', ' ', '-', "'",              # Standard word boundaries
        '❬', '❭',                        # Angle brackets
        '…',                             # Ellipsis
        '(', '[', '{', '<',              # ASCII opening brackets
        ')', ']', '}', '>',              # ASCII closing brackets
        '❬', '《', '⟦', '⦃',             # Replacement opening brackets
        '❭', '》', '⟧', '⦄',             # Replacement closing brackets
    }

    # File extensions where we want to preserve the original case of the base name
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

    # Known file extensions that should be recognized and moved
    KNOWN_EXTENSIONS = PRESERVE_CASE_EXTENSIONS | {
        # Basic text and documents
        'txt', 'rtf', 'pdf',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',  # Microsoft Office
        'odt', 'ods', 'odp',  # OpenDocument (LibreOffice)
        # Images
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp', 'svg',
        # Audio
        'mp3', 'wav', 'ogg', 'flac', 'm4a', 'wma',
        # Video
        'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm',
        # Archives
        'zip', 'rar', 'tar', 'gz', '7z',
        # Database
        'db', 'sqlite', 'mdb',
        # Email
        'eml', 'msg',
        # Font
        'ttf', 'otf', 'woff', 'woff2',
    }

    # Common contractions and possessives to preserve
    CONTRACTIONS = {
        # Contractions (without apostrophe)
        'll',  # will, shall
        's',   # is, has, possessive
        't',   # not (don't, won't, etc)
        're',  # are
        've',  # have
        'd',   # had, would
        'm',   # am

        # Special quoted terms (without apostrophe)
        'em',  # them (informal)
        'til', # until (informal)
        'n',   # and (rock'n'roll)
        'cause', # because
    }

    # Debug mode flag
    _debug = is_debug_mode()

    @classmethod
    def debug_print(cls, *args, **kwargs):
        """Print only if in debug mode"""
        if cls._debug:
            print(*args, **kwargs)

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
            if len(original_char) != 1 and original_char != '...' and original_char not in {'<<', '>>', '[[', ']]', '{{', '}}'}:
                raise ValueError(
                    f"Invalid original character in CHAR_REPLACEMENTS: {original_char}. "
                    "Original character must be a single character, '...', or a valid bracket sequence."
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
        # Articles
        'a', 'an', 'the',

        # Coordinating Conjunctions
        'and', 'but', 'for', 'nor', 'or', 'so', 'yet',

        # Short Prepositions (under 5 letters)
        'at', 'by', 'down', 'for', 'from', 'in', 'into',
        'like', 'near', 'of', 'off', 'on', 'onto', 'out',
        'over', 'past', 'to', 'up', 'upon', 'with',

        # Common Particles
        'as', 'if', 'how', 'than', 'vs', 'vs.',

        # Common Words in Media Titles
        'part', 'vol', 'vs', 'feat', 'ft', 'remix',

        # Be Verbs (when not first/last)
        'am', 'are', 'is', 'was', 'were', 'be', 'been', 'being'
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

    def _clean_trailing_chars(self, text: str, debug_prefix: str = '') -> str:
        """Clean trailing special characters from text.

        Args:
            text: Text to clean
            debug_prefix: Optional prefix for debug output

        Returns:
            Cleaned text with trailing special characters removed
        """
        self.debug_print(f"{debug_prefix}Before trailing cleanup:        {text!r}")

        while text:
            changed = False

            # First handle periods and ellipsis which have special "truly trailing" rules
            if text.endswith('.') or text.endswith('…'):
                # Check if there's more text after the trailing dots/ellipsis
                rest = text.rstrip('.…').strip()
                if not rest:  # If empty, this was truly trailing
                    text = rest
                    changed = True
                # If what's left ends in an allowed char or doesn't end in period/ellipsis, we're done
                elif not (rest.endswith('.') or rest.endswith('…')):
                    text = rest
                    changed = True
                # Otherwise keep going (more trailing periods/ellipsis to remove)
                else:
                    text = rest
                    changed = True

            # Then check for any other special characters that aren't allowed at the end
            for orig, repl in self.CHAR_REPLACEMENTS.items():
                if text.endswith(repl) and repl not in self.ALLOWED_TRAILING_CHARS:
                    text = text[:-len(repl)].rstrip()
                    changed = True
                    break

            if not changed:
                break  # No more trailing characters to remove

        self.debug_print(f"{debug_prefix}After trailing cleanup:         {text!r}\n")
        return text

    def _clean_filename(self, filename: str) -> str:
        """Clean filename to be NTFS-compatible."""
        try:
            filename.encode('utf-16')
        except UnicodeEncodeError as e:
            raise ValueError(f"Input filename contains invalid characters: {e}")

        self.debug_print(f"\n{'='*50}")
        self.debug_print(f"Starting to process: {filename!r}")
        self.debug_print(f"{'='*50}\n")

        # Split into name and extension with rules:
        # 1. Extensions cannot contain spaces
        # 2. Don't treat trailing periods as extension separators
        # 3. Extension comes after the last valid period
        if filename.strip().endswith('.'):
            # If filename ends with periods, don't treat them as extension separator
            name = filename
            extension = ''
        else:
            # Find last period that could be a valid extension separator
            # (not part of trailing periods and not followed by space)
            last_period = -1
            for i in range(len(filename)-1, -1, -1):
                if filename[i] == '.' and (i == len(filename)-1 or filename[i+1] != '.'):
                    potential_ext = filename[i+1:]
                    if ' ' not in potential_ext:  # Extension cannot contain spaces
                        last_period = i
                        break

            if last_period != -1:
                name = filename[:last_period]
                extension = filename[last_period+1:]
            else:
                name = filename
                extension = ''

        # For known file extensions (like .py, .js):
        # - Keep the original filename case (don't title case it)
        # - Always use lowercase for the extension
        preserve_name_case = extension.lower() in self.PRESERVE_CASE_EXTENSIONS

        # First normalize all whitespace to single spaces
        self.debug_print(f"Splitting name: {name!r} (extension: {extension!r})")
        self.debug_print(f"Before whitespace normalization: {name!r}")
        name = re.sub(r'[\n\r\t\f\v]+', ' ', name)  # Convert newlines and other whitespace to spaces
        name = re.sub(r' {2,}', ' ', name)  # Collapse multiple spaces
        self.debug_print(f"After whitespace normalization:  {name!r}\n")

        # Replace special characters
        self.debug_print(f"Before special char replacement: {name!r}")
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if original_char == '...':
                # Handle ellipsis separately to avoid over-replacement
                self.debug_print(f"Before ellipsis replacement:    {name!r}")
                name = re.sub(r'\.{3,}', replacement_char, name)
                self.debug_print(f"After ellipsis replacement:     {name!r}")
            else:
                # Replace multiple occurrences with single replacement
                name = re.sub(f'{re.escape(original_char)}+', replacement_char, name)
        self.debug_print(f"After special char replacement:  {name!r}\n")

        name = name.strip()  # Remove leading/trailing spaces
        self.debug_print(f"After strip:                    {name!r}\n")

        # Remove trailing periods and ellipsis
        # These are never allowed at the end, regardless of what comes before
        name = self._clean_trailing_chars(name)

        # If we have no extension but the cleaned name ends in a recognized extension,
        # move it to be the actual extension (may have affected base name capitalization)
        if not extension and '.' in name:
            self.debug_print(f"\nChecking for recognized extension in cleaned name: {name!r}")
            # Get the potential extension and clean it of special characters
            potential_ext = name.split('.')[-1]
            # Remove any special replacement characters that aren't valid in extensions
            for orig, repl in self.CHAR_REPLACEMENTS.items():
                potential_ext = potential_ext.replace(repl, '')
            potential_ext = potential_ext.lower()
            self.debug_print(f"Potential extension found (after cleanup): {potential_ext!r}")
            if potential_ext in self.KNOWN_EXTENSIONS:
                name = name[:-(len(potential_ext) + 1)]  # remove .ext
                name = self._clean_trailing_chars(name, debug_prefix="\n")  # clean trailing chars from new base name
                extension = potential_ext
                self.debug_print(f"Recognized extension moved: name={name!r}, extension={extension!r}")
            else:
                self.debug_print(f"Extension {potential_ext!r} not in recognized list")

        # For normal files, apply title case to the name
        # For files with known extensions, preserve the original name case
        # Extensions are always lowercased
        if not extension.lower() in self.PRESERVE_CASE_EXTENSIONS:
            # Build pattern that matches our word boundaries
            split_pattern = '([' + ''.join(re.escape(c) for c in self.WORD_BOUNDARY_CHARS) + '])'
            self.debug_print(f"\nSplit pattern: {split_pattern}")
            parts = re.split(split_pattern, name)
            self.debug_print(f"Parts after split: {parts!r}\n")

            titled_parts = []
            prev_part = ''
            last_real_word = None
            for part in parts:
                if part and len(part) > 1 and not any(c in self.WORD_BOUNDARY_CHARS for c in part):
                    last_real_word = part.lower()

            # Now process each part
            for part in parts:
                if not part:  # Skip empty parts
                    continue

                # Convert to title case, handling special cases
                word = part.lower()  # First convert to lowercase

                self.debug_print(f"\nProcessing word: {word!r}")
                self.debug_print(f"Previous part: {prev_part!r}")
                self.debug_print(f"Is contraction: {word in self.CONTRACTIONS}")
                self.debug_print(f"Titled parts so far: {titled_parts}")

                # Skip empty parts
                if not word:
                    continue

                # Keep separators as is
                if len(part) == 1 and part in self.WORD_BOUNDARY_CHARS:
                    self.debug_print(f"Keeping separator: {part!r}")
                    titled_parts.append(part)
                    prev_part = part
                    continue

                # Check if this is a contraction
                if word in self.CONTRACTIONS and len(titled_parts) >= 2:
                    self.debug_print(f"\nFound contraction: {word!r}")
                    self.debug_print(f"Previous part: {prev_part!r}")
                    self.debug_print(f"Previous parts: {titled_parts[-2:]!r}")
                    # Check if it follows a word + apostrophe (not space + apostrophe)
                    if prev_part == "'" and not titled_parts[-2].isspace():
                        self.debug_print(f"Keeping as contraction\n")
                        titled_parts.append(word)
                        prev_part = part
                        continue
                    self.debug_print(f"Not treating as contraction - not after word + apostrophe\n")

                # Check if this word should stay lowercase
                # Word should be lowercase if:
                # 1. It's in our LOWERCASE_WORDS set
                # 2. It's not the first word
                # 3. It's not after a period or ellipsis
                # 4. It's not the last word
                # 5. It's between spaces (not after special chars)
                self.debug_print(f"\nWord: {word!r}")
                self.debug_print(f"In LOWERCASE_WORDS: {word in self.LOWERCASE_WORDS}")
                self.debug_print(f"Not first word: {bool(titled_parts)}")
                self.debug_print(f"After space: {prev_part == ' '}")
                self.debug_print(f"Not last word: {word != last_real_word}")
                self.debug_print(f"Previous parts: {titled_parts[-2:] if len(titled_parts) >= 2 else []!r}")

                # Check if we're between spaces
                is_between_spaces = (
                    prev_part == ' ' and  # Current word follows a space
                    (len(titled_parts) < 2 or  # Start of string
                     (titled_parts[-1] == ' ' and  # Previous was space
                      (len(titled_parts) < 3 or   # Beginning of string
                       titled_parts[-2] not in self.WORD_BOUNDARY_CHARS - {' '})))  # Not after special char
                )

                # Always capitalize after a period/ellipsis or if it's the first/last word
                should_capitalize = (
                    not titled_parts or  # First word
                    prev_part in {'.', self.CHAR_REPLACEMENTS['...']} or  # After period or ellipsis
                    prev_part in self.OPENING_BRACKETS or  # After any opening bracket
                    word == last_real_word  # Last word
                )
                self.debug_print(f"Should capitalize:    {should_capitalize}\n")

                if (word in self.LOWERCASE_WORDS and
                    titled_parts and      # Not first word
                    not should_capitalize and  # Not after period/ellipsis
                    word != last_real_word and  # Not the last word
                    is_between_spaces):   # Between spaces, not after special char
                    self.debug_print(f"Should be lowercase: True")
                    titled_parts.append(word)
                else:
                    self.debug_print(f"Should be lowercase: False")
                    titled_parts.append(word.capitalize())
                prev_part = part

            # Join the parts back together
            name = ''.join(titled_parts)

            # Do one final check for trailing special characters
            name = self._clean_trailing_chars(name)

        # If original had no spaces, remove spaces around special characters
        if ' ' not in filename:
            for char in self.special_chars - {' '}:
                name = name.replace(f' {char} ', char)
                name = name.replace(f' {char}', char)
                name = name.replace(f'{char} ', char)

        # Always use lowercase for extensions, whether known or unknown
        if extension:
            result = f"{name}.{extension.lower()}"
        else:
            result = name

        self.debug_print(f"\n{'='*50}")
        self.debug_print(f"Finished processing: {filename!r}")
        self.debug_print(f"Result: {result!r}")
        self.debug_print(f"{'='*50}\n")

        return result

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
                    self.debug_print(f"Warning: Cannot rename '{original_name}' to '{new_name}' - target exists")
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
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug output')

    # Add a custom -? help option
    parser.add_argument('-?', action='help',
                      help='Show this help message and exit')

    args = parser.parse_args()

    # Update debug mode based on command line flag
    FileRenamer._debug = FileRenamer._debug or args.debug

    renamer = FileRenamer(args.directory, dry_run=args.dry_run)
    changes = renamer.process_files()

    if args.dry_run:
        print("\nProposed changes (dry run):")
    else:
        print("\nExecuted changes:")

    # Track if any files were changed
    any_changes = False
    for old, new in changes:
        if old == new:
            print(f"{old}\n  ->  unchanged\n")
        else:
            any_changes = True
            print(f"{old}\n  -> {new}\n")

    if not any_changes:
        print("\nNo files need to be renamed.")
        return

    if not args.dry_run:
        confirm = input("\nApply these changes? [y/N] ")
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
