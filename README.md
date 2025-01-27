# File Renamer - Ext4 to NTFS

A Python script to safely rename files from Ext4 naming convention to NTFS-compatible format, while preserving UTF-8/UTF-16 characters.

## Features

- Replaces NTFS-incompatible characters with visually similar Unicode alternatives
- Preserves UTF-8/UTF-16 characters
- Applies proper title case formatting
- Handles special cases like multiple spaces and trailing punctuation
- Includes dry-run mode to preview changes
- Comprehensive test suite

## Installation

1. Ensure Python 3.6+ is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Basic usage:
```bash
python file_renamer.py [directory] [--dry-run]
```

Arguments:
- `directory`: Optional. Directory containing files to rename. Defaults to current directory.
- `--dry-run`: Optional. Show what would be renamed without making changes.

Examples:
```bash
# Preview changes in current directory
python file_renamer.py --dry-run

# Rename files in specific directory
python file_renamer.py ~/my_files

# Preview changes in specific directory
python file_renamer.py ~/my_files --dry-run
```

## Running Tests

Run the test suite:
```bash
python -m pytest test_file_renamer.py -v
```

## Character Substitutions

The script uses the following character substitutions:
- `\` → `⧵` (Reverse Solidus Operator)
- `:` → `ː` (Modifier Letter Triangular Colon)
- `*` → `✱` (Heavy Asterisk)
- `?` → `❓` (Black Question Mark Ornament)
- `"` → `"` (Left Double Quotation Mark)
- `<` → `❬` (Medium Left-Pointing Angle Bracket Ornament)
- `>` → `❭` (Medium Right-Pointing Angle Bracket Ornament)
- `|` → `│` (Box Drawings Light Vertical)
- Newlines and tabs are converted to spaces
- `$` → `＄` (Full Width Dollar Sign)
