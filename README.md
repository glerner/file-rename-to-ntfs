<!-- THIS FILE IS MANUALLY MAINTAINED; DO NOT SUGGEST CHANGES -->
# File Renamer - Ext4 to NTFS

A Python script to safely rename files from Ext4 naming convention to NTFS-compatible format, while preserving UTF-8/UTF-16 characters.

## Features

- Replaces NTFS-incompatible characters with visually similar Unicode alternatives
- Includes dry-run mode to preview changes
- Preserves UTF-8/UTF-16 characters (this program doesn't modify them).
- Applies proper title case formatting with smart word handling:
  - Preserves contractions and possessives (don't, it's, John's)
  - Handles quoted phrases ('This Old House')
  - Special terms like 'til and rock'n'roll
  - Common lowercase words (a, an, the, etc.)
  - Preserves common abbreviations (MD, M.D., PG-13, DES, NY)
  - User's abbreviations can be added via settings.ini
  - Handles common military ranks (SGT, Sgt, Sgt.)
  - Handles common units (min, g, km, lbs, mpg or L/100km etc.)
  - Handles some date formats (2024-01-01, 2024/01/01, 2024.01.01, 2-23-2024 but doesn't validate dates)
- Advanced character substitution system:
  - Uses visually similar Unicode replacements that maintain readability
  - Handles multiple forms of quotes, apostrophes, and slashes with context-aware replacements
  - Preserves visual similarity while ensuring NTFS compatibility
- Extensive unit pattern support:
  - Weight units (mg, g, kg)
  - Data units (KB, MB, GB, TB)
  - Network speed (kbps, mbps, etc.)
  - Frequency units (Hz, kHz, MHz)
  - Time units (AM/PM formatting)
  - Volume units (L, mL)
  - Video resolutions (1080p, 4K)
  - Electrical units (W, V, A, J, N)
  - Temperature units
  - Digital measurements (bit, fps, rpm)
  - Speed and efficiency units (mph, mpg)
- Ordinal number handling:
  - Special handling for ordinal numbers (1st, 2nd, 3rd, 4th, etc.)
  - Preserves proper lowercase formatting for these numbers
- International support:
  - Handles abbreviations for Mexican states
  - Handles abbreviations for Canadian provinces
  - Supports international time zones
  - Recognizes some country codes
- Handles special cases like multiple spaces and trailing punctuation
- Normalizes whitespace (converts tabs, newlines, and other whitespace to spaces)
- Intelligently handles compound abbreviations (e.g., Lt.Col becomes LtCol)
- Preserves file names of known programming language file extensions in their original case, but extensions themselves are always converted to lowercase
- Properly handles filenames with no spaces (preserves the no-space format)
- Debug mode for detailed operation logging with configurable verbosity
- Comprehensive test suite

Note that UTF-8 (macOS, Linux) characters convert to different UTF-16 characters (NTFS) depending on the operating system and users's preferred encoding settings.

## Additional Features

- **Version Compatibility**
  - Works with Python 3.6+ for broad compatibility across systems

- **Automatic Settings Discovery**
  - Searches for settings files in multiple standard locations automatically
  - Provides a clear hierarchy for settings precedence
  - Allows custom abbreviations and preserved phrases to be added via settings.ini

- **Customizable Colorized Output**
  - When colorama is installed, the debug output uses color coding to highlight character replacements (UTF-16 look-alike characters)
  - Makes it easier to identify exactly what changes were made

- **Comprehensive Abbreviation System**
  - Handles various types of abbreviations including:
    - Academic degrees
    - Professional titles
    - Military ranks
    - Government organizations
    - Technology standards
    - Business terms
  - Easily extensible with custom abbreviations via settings.ini

## Installation

1. Ensure Python 3.6+ is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Optional: Install colorama for colored debug output:
   ```bash
   pip install colorama
   ```
   When colorama is installed, special character replacements will be highlighted in cyan in the debug output,
   making it easier to spot where characters have been replaced.

## Usage

Run in your Terminal. There is no graphical user interface.

Basic usage:
```bash
python file_renamer.py [directory] [--dry-run] [--debug] [--settings SETTINGS_FILE]
```

Arguments:
- `directory`: Optional. Directory containing files to rename. Defaults to current directory.
- `--dry-run`: Optional. Show what would be renamed without making changes.
- `--debug`: Optional. Enable detailed debug output showing each step of the renaming process.
- `--settings`: Optional. Path to custom settings file. Defaults to settings.ini.

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

# Use a custom settings file
python file_renamer.py --settings ~/my_custom_settings.txt
```

## User Settings

File Renamer supports customization through a settings file that allows you to define your own abbreviations and preserved terms.

### Settings File Location

The program looks for settings in the following locations (in order):
1. Path specified with `--settings` command-line option
2. `./settings.ini` (in the current directory)
3. `~/.config/file_renamer/settings.ini` (in your home directory)

### Format

The settings file uses a simple format with section headers in brackets and one entry per line:

```
[abbreviations]
AI
ML

[preserved_terms]
My Product Name
```

### Sections

1. **[abbreviations]** - Terms that should maintain their exact capitalization
   - Example: "AI" will always remain "AI" instead of being converted to "Ai"
   - These are recognized as complete words during filename processing

2. **[preserved_terms]** - Phrases that should be preserved with their formatting
   - Example: "Star Trek: The Next Generation" will maintain its capitalization and structure
   - These can include special characters, spaces, and punctuation
   - NTFS-illegal characters will still be substituted with similar Unicode alternatives
   - The renamer will preserve the overall appearance while ensuring compatibility

### Rules and Limitations

- Maximum entry length: 255 UTF-16 characters (NTFS filename limit)
- Special characters are allowed and will be handled by the renamer
- Control characters (non-printable) are not allowed
- User-defined terms take precedence over built-in terms
- Invalid entries will be skipped with a warning message

### Example

```
# My custom settings

[abbreviations]
AI
ML
MyCompany
AWS

[preserved_terms]
My Product Name
Company-Specific™ Term
Star Trek: The Next Generation
```

### Creating Your First Settings File

1. Modify the existing text file named `settings.ini` in the same directory as the script (or create new one)
2. Add section headers `[abbreviations]` and `[preserved_terms]`
3. Add your custom terms under each section
4. Save the file and run File Renamer normally

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
clear; python -m pytest test_file_renamer.py -v --capture=no

# --capture=no is for seeing try-except details in pytest
# -s is shortcut for --capture=no

# Run tests with basic coverage report
clear; python -m pytest test_file_renamer.py -v -s --cov=file_renamer

# Run tests with detailed coverage report showing missing lines
clear; python -m pytest test_file_renamer.py -v -s --cov=file_renamer --cov-report=term-missing
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

The script uses several character substitutions to maintain visual similarity while ensuring NTFS compatibility. These include:
- `\` → `⧵` (Reverse Solidus Operator)
- `:` → `ː` (Modifier Letter Triangular Colon)
- `*` → `✱` (Heavy Asterisk)
- `?` → `⁇` (Reversed Question Mark)
- `"` → `＂` (Full Width Quotation Mark)
- `'` → `ʼ` (Modifier Letter Apostrophe) - Used for contractions and possessives
- `'` → `'` (Left Single Quotation Mark) - Preserved if in original text
- `'` → `'` (Right Single Quotation Mark) - Preserved if in original text
- `<` → `❬` (Left Black Lenticular Bracket)
- `>` → `❭` (Right Black Lenticular Bracket)
- `<<` → `《` (Left Double Angle Bracket)
- `>>` → `》` (Right Double Angle Bracket)
- `[[` → `⟦` (Mathematical Left White Square Bracket)
- `]]` → `⟧` (Mathematical Right White Square Bracket)
- `{{` → `⦃` (Left White Curly Bracket)
- `}}` → `⦄` (Right White Curly Bracket)
- `|` → `│` (Box Drawings Light Vertical)
- `&` → ` and `
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

## Unit Formatting Rules

The script applies special case rules for units:

### Units vs. Abbreviations Priority
When a text could be interpreted as either a unit or an abbreviation, units are given priority. For example:
- `SEC` could be "Securities and Exchange Commission" or "seconds" - treated as a unit (seconds)
- `HR` could be "Human Resources" or "hour" - treated as a unit (hour)

This prioritization helps maintain consistency in filenames with measurements and technical specifications.

### Bits and Bytes (b/B)
Since we cannot determine whether a unit refers to bits or bytes from the text alone, we preserve the original case of 'b' or 'B' while enforcing proper case for the SI unit prefix symbols:
- Prefixes kilo and smaller (k) are always lowercase
- Prefixes mega and larger (M, G, T) are always uppercase

Examples:
```
2tb -> 2Tb    (T uppercase, original b preserved)
5Gb -> 5Gb    (G uppercase, original b preserved)
10KB -> 10kB  (k lowercase, original B preserved)
5MB -> 5MB    (M uppercase, original B preserved)
```

## Output Format

The script shows proposed changes in an easy-to-read format:
```
'Original Filename.txt'
  -> 'New Filename.txt'

'Unchanged File.txt'
  -> unchanged
