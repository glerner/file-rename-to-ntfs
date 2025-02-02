# File Renamer - Ext4 to NTFS

A Python script to safely rename files from Ext4 naming convention to NTFS-compatible format, while preserving UTF-8/UTF-16 characters.

## Features

- Replaces NTFS-incompatible characters with visually similar Unicode alternatives
- Preserves UTF-8/UTF-16 characters
- Applies proper title case formatting with smart word handling:
  - Preserves contractions and possessives (don't, it's, John's)
  - Handles quoted phrases ('This Old House')
  - Special terms like 'til and rock'n'roll
  - Common lowercase words (a, an, the, etc.)
  - Preserves common abbreviations (MD, M.D., PG-13, DES, NY)
- Handles special cases like multiple spaces and trailing punctuation
- Preserves known file extensions in their original case, but extensions are converted to lowercase
- Includes dry-run mode to preview changes
- Debug mode for detailed operation logging
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
python file_renamer.py [directory] [--dry-run] [--debug]
```

Arguments:
- `directory`: Optional. Directory containing files to rename. Defaults to current directory.
- `--dry-run`: Optional. Show what would be renamed without making changes.
- `--debug`: Optional. Enable detailed debug output showing each step of the renaming process.

Examples:
```bash
# Preview changes in current directory
python file_renamer.py --dry-run

# Rename files in specific directory
python file_renamer.py ~/my_files

# Preview changes with debug output
python file_renamer.py --dry-run --debug

# Rename files in specific directory with debug output
python file_renamer.py ~/my_files --debug
```

## Debug Mode

Debug mode can be enabled in three ways:
1. Using the `--debug` command line flag
2. Setting the environment variable `RENAMER_DEBUG=1`
3. Running under unittest (automatically enabled)

When debug mode is enabled, the script outputs detailed information about:
- Each step of the filename cleaning process
- Character replacements and their effects
- Title case decisions for each word
- Extension handling and recognition

## Running Tests

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install test dependencies:
```bash
pip install -r requirements.txt
```

3. Run the tests:
```bash
# Run tests with verbose output
python -m pytest test_file_renamer.py -v

# Run tests with basic coverage report
python -m pytest test_file_renamer.py -v --cov=file_renamer

# Run tests with detailed coverage report showing missing lines
python -m pytest test_file_renamer.py -v --cov=file_renamer --cov-report=term-missing
```

4. Cleanup (when finished):
```bash
deactivate  # Exit virtual environment
rm -rf venv  # Remove virtual environment directory
```

The test suite includes cases for:
- Special character replacements
- Title case formatting rules
- Handling of spaces and punctuation
- Real-world filename examples

## Character Substitutions

The script uses the following character substitutions:
- `\` → `⧵` (Reverse Solidus Operator)
- `:` → `ː` (Modifier Letter Triangular Colon)
- `*` → `✱` (Heavy Asterisk)
- `?` → `⁇` (Reversed Question Mark)
- `"` → `＂` (Full Width Quotation Mark)
- `<` → `❬` (Left Black Lenticular Bracket)
- `>` → `❭` (Right Black Lenticular Bracket)
- `<<` → `《` (Left Double Angle Bracket)
- `>>` → `》` (Right Double Angle Bracket)
- `[[` → `⟦` (Mathematical Left White Square Bracket)
- `]]` → `⟧` (Mathematical Right White Square Bracket)
- `{{` → `⦃` (Left White Curly Bracket)
- `}}` → `⦄` (Right White Curly Bracket)
- `|` → `│` (Box Drawings Light Vertical)
- `&` → `and`
- `$` → `＄` (Full Width Dollar Sign)
- `!` → `!` (Collapses multiple exclamation marks)
- `...` → `…` (Horizontal Ellipsis)

## Title Case Rules

The script applies smart title case rules:
- Capitalizes the first and last words
- Capitalizes words after periods, ellipsis, and opening brackets
- Keeps certain words lowercase when in the middle of a title:
  - Articles (a, an, the)
  - Coordinating Conjunctions (and, but, for, nor, or, so, yet)
  - Short Prepositions (at, by, down, for, from, in, into, etc.)
  - Common Particles (as, if, how, than, vs)
  - Common Media Words (part, vol, feat, ft, remix)
  - Be Verbs (am, are, is, was, were, be, been, being)

## Output Format

The script shows proposed changes in an easy-to-read format:
```
'Original Filename.txt'
  -> 'New Filename.txt'

'Unchanged File.txt'
  -> unchanged
