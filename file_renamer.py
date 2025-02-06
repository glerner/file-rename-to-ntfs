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

    # Multi-character replacements that are valid
    MULTI_CHAR_REPLACEMENTS = {
        '...', '<<', '>>', '[[', ']]', '{{', '}}',  # Special sequences
        # Commented out fraction patterns - keeping for reference
        # '1/2', '1/3', '2/3', '1/4', '3/4',          # Common fractions
        # '1/5', '2/5', '3/5', '4/5',
        # '1/6', '5/6',
        # '1/8', '3/8', '5/8', '7/8'
    }

    # Character substitution mappings
    CHAR_REPLACEMENTS = {
        '\\': '⧵',  # Reverse Solidus Operator
        '/': '⧸',   # Big Solidus (for paths and non-fractions)
        # Commented out fraction mappings - keeping for reference
        # '1/2': '½', # Fraction One Half
        # '1/3': '⅓', # Fraction One Third
        # '2/3': '⅔', # Fraction Two Thirds
        # '1/4': '¼', # Fraction One Quarter
        # '3/4': '¾', # Fraction Three Quarters
        # '1/5': '⅕', # Fraction One Fifth
        # '2/5': '⅖', # Fraction Two Fifths
        # '3/5': '⅗', # Fraction Three Fifths
        # '4/5': '⅘', # Fraction Four Fifths
        # '1/6': '⅙', # Fraction One Sixth
        # '5/6': '⅚', # Fraction Five Sixths
        # '1/8': '⅛', # Fraction One Eighth
        # '3/8': '⅜', # Fraction Three Eighths
        # '5/8': '⅝', # Fraction Five Eighths
        # '7/8': '⅞', # Fraction Seven Eighths
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

    # Common abbreviations to preserve in uppercase
    @classmethod
    def _clean_abbreviation(cls, abbr: str) -> str:
        """
        Clean abbreviations for filename use:
        1. Remove all periods (we want MD not M.D.)
        2. Remove trailing whitespace
        3. Store in standard form for case-insensitive matching
        """
        # Remove periods and whitespace
        return re.sub(r'\.', '', abbr.strip())

    # Common abbreviations to preserve in uppercase
    ABBREVIATIONS = {
        # Academic Degrees (single-letter-per-part use periods)
        'B.A', 'B.S', 'M.A', 'M.B.A', 'M.D', 'M.S', 'Ph.D', 'J.D',

        # Professional Titles (multi-letter, no periods)
        'Dr', 'Mr', 'Mrs', 'Ms', 'Prof', 'Rev',
        'Hon',  # Honorable (Judge)
        'Sr', 'Sra', 'Srta',  # Señor, Señora, Señorita

        # Name Suffixes (no periods)
        'Jr', 'Sr', 'II', 'III', 'IV',  # Note: V excluded as it conflicts with 'versus'

        # Military Ranks (no periods)
        'Cpl', 'Sgt', 'Lt', 'Capt', 'Col', 'Gen',  # Common ranks
        'Maj', 'Adm', 'Cmdr',  # More ranks
        'USMC', 'USN', 'USAF', 'USA',  # Service branches

        # Movie/TV Ratings (no periods)
        'TV', 'G', 'PG', 'PG-13', 'R', 'NC-17', 'TV-14', 'TV-MA', 'TV-PG', 'TV-Y',

        # TV Networks
        'ABC', 'BBC', 'CBS', 'CNN', 'CW', 'HBO', 'NBC', 'PBS',
        'TBS', 'TNT', 'USA', 'ESPN', 'MTV', 'TLC', 'AMC',

        # US States (excluding those that conflict with common words)
        'AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL',
        'GA', 'HI', 'ID', 'IL', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI',
        'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV',
        'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT',
        'VA', 'VT', 'WA', 'WI', 'WV', 'WY',

        # Canadian Provinces (excluding ON, a lowercase word)
        'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'PE', 'QC', 'SK', 'YT',

        # Countries and Regions
        'UK', 'USA', 'US', 'EU', 'UAE', 'USSR',

        # Time/Date (AM and PM handled special case)
        'EST', 'EDT', 'CST', 'CDT', 'MST', 'MDT', 'PST', 'PDT', 'GMT', 'UTC',

        # Government/Organizations
        'CIA', 'DEA', 'DHS', 'DMV', 'DOD', 'DOE', 'DOJ', 'FBI', 'FCC',
        'FDA', 'FEMA', 'FTC', 'IRS', 'NASA', 'NOAA', 'NSA', 'TSA', 'USDA',
        'EPA', 'ICE', 'SEC', 'SSA', 'UN', 'USPS',

        # Mexican States (official abbreviations)
        'AGS',  # Aguascalientes
        'BC',   # Baja California
        'BCS',  # Baja California Sur
        'CAMP', # Campeche
        'CHIS', # Chiapas
        'CHIH', # Chihuahua
        'COAH', # Coahuila
        'COL',  # Colima
        'CDMX', # Ciudad de México
        'DGO',  # Durango
        'GTO',  # Guanajuato
        'GRO',  # Guerrero
        'HGO',  # Hidalgo
        'JAL',  # Jalisco
        'MEX',  # Estado de México
        'MICH', # Michoacán
        'MOR',  # Morelos
        'NAY',  # Nayarit
        'NL',   # Nuevo León
        'OAX',  # Oaxaca
        'PUE',  # Puebla
        'QRO',  # Querétaro
        'QROO', # Quintana Roo
        'SLP',  # San Luis Potosí
        # 'SIN',  # Sinaloa exclude, a word
        # 'SON',  # Sonora exclude, a word
        # 'TAB',  # Tabasco exclude, a word
        'TAMPS',# Tamaulipas
        'TLAX', # Tlaxcala
        'VER',  # Veracruz
        'YUC',  # Yucatán
        'ZAC',  # Zacatecas

        # Operating Systems and File Systems
        'DOS', 'OS/X', 'NTFS', 'FAT32', 'exFAT',

        # Technology Standards and Formats
        'CD', 'DVD', 'GB', 'HD', 'HDMI', 'VGA', 'HTML', 'HTTP', 'HTTPS',
        'IP', 'ISO', 'KB', 'MB', 'MP3', 'MP4', 'MPEG', 'PDF', 'RAM', 'ROM',
        'SQL', 'TB', 'USB', 'VHS', 'XML', 'JSON', 'PHP', 'Wi-Fi',
        'CPU', 'GPU', 'SSD', 'HDD', 'NVMe', 'SATA', 'RAID', 'LAN', 'WAN',
        'DNS', 'FTP', 'SSH', 'SSL', 'TLS', 'URL', 'URI', 'API', 'SDK',
        'IDE', 'GUI', 'CLI', 'CSS', 'RSS', 'UPC', 'QR', 'AI', 'ML',

        # Media Formats
        # Images
        'JPEG', 'JPG', 'PNG', 'GIF', 'BMP', 'TIF', 'TIFF', 'SVG', 'WebP',
        # Video
        'AVI', 'MP4', 'MKV', 'MOV', 'WMV', 'FLV', 'WebM', 'M4V', 'VOB',
        # Audio
        'MP3', 'WAV', 'AAC', 'OGG', 'FLAC', 'WMA', 'M4A',
        # Quality/Standards
        '4K', '8K', 'HDR', 'DTS', 'IMAX', 'UHD', 'fps', 

        # Medical/Scientific
        'DNA', 'RNA', 'CRISPR', 'CPAP', 'BiPAP', 'HIV', 'AIDS', 'CDC',
        'MRI', 'CT', 'EKG', 'ECG', 'X-Ray', 'ICU', 'ER',

        # Business/Organizations
        'CEO', 'CFO', 'CIO', 'COO', 'CTO', 'HR', 'LLC', 'LLP',
        'VP', 'vs',  # Note: removed VS to avoid confusion

        # Other Common
        'ID', 'OK', 'PC', 'PIN', 'PO', 'PS', 'RIP', 'UFO', 'VIP', 'ZIP',
        'DIY', 'FAQ', 'ASAP', 'IMAX', 'STEM',

        # Software/Platforms
        'WordPress', 'iOS', 'macOS', 'SQL', 'NoSQL', 'MySQL',
    }

    # Words with specific capitalization (not uppercase, not regular title case)
    SPECIAL_CASE_WORDS = {
        'iPad', 'iPhone', 'iPod', 'iTunes', 'iMac',  # Apple products
        'macOS', 'iOS',  # Operating systems
        'MySQL', 'NoSQL', 'PostgreSQL',  # Databases
        'JavaScript', 'TypeScript', 'WordPress',  # Software,
        'Wi-Fi'
    }

    # Common units in filenames that need specific capitalization
    R = CHAR_REPLACEMENTS  # Shorthand for readability
    UNIT_PATTERNS = {
        # Storage (k lowercase, M/G/T uppercase + B)
        r'\d+kb': lambda s: f"{s[:-2]}kB",  # 5kb -> 5kB
        r'\d+KB': lambda s: f"{s[:-2]}kB",  # 5KB -> 5kB
        r'\d+[mgt]b': lambda s: f"{s[:-2]}{s[-2].upper()}B",  # 5mb -> 5MB

        # Frequency (k lowercase, M/G/T uppercase + Hz)
        r'\d+hz\b': lambda s: f"{s[:-2]}Hz",  # 100hz -> 100Hz
        r'\d+khz': lambda s: f"{s[:-3]}kHz",  # 100khz -> 100kHz
        r'\d+[mgt]hz': lambda s: f"{s[:-3]}{s[-3].upper()}Hz",  # 100mhz -> 100MHz

        # Time (always uppercase)
        r'\d+[ap]m': lambda s: f"{s[:-2]}{s[-2:].upper()}",  # 5pm -> 5PM

        # Liters (L always uppercase)
        r'\d+l\b': lambda s: f"{s[:-1]}L",  # 5l -> 5L
        r'\d+[kmgt]l\b': lambda s: f"{s[:-2]}{s[-2].lower()}L",  # 5ml -> 5mL

        # Greek letter units (always uppercase)
        r'\d+ω\b': lambda s: f"{s[:-1]}Ω",  # 100ω -> 100Ω

        # Single-letter SI units (W, V, A, J, N)
        r'\d+w\b': lambda s: f"{s[:-1]}W",   # 100w -> 100W (Watt)
        r'\d+v\b': lambda s: f"{s[:-1]}V",   # 5v -> 5V (Volt)
        r'\d+a\b': lambda s: f"{s[:-1]}A",   # 5a -> 5A (Ampere)
        r'\d+j\b': lambda s: f"{s[:-1]}J",   # 100j -> 100J (Joule)
        r'\d+n\b': lambda s: f"{s[:-1]}N",   # 10n -> 10N (Newton)

        # SI prefixes for single-letter units
        # k (kilo) is lowercase, M/G/T uppercase
        r'\d+k[wvajn]\b': lambda s: f"{s[:-2]}k{s[-1].upper()}", # 5kw -> 5kW
        r'\d+[mgt][wvajn]\b': lambda s: f"{s[:-2]}{s[-2].upper()}{s[-1].upper()}", # 5mw -> 5MW, 5gw -> 5GW, 5tw -> 5TW

        # Temperature units (always uppercase)
        r'\d+k\b': lambda s: f"{s[:-1]}K",   # 5k -> 5K (Kelvin)
        r'\d+c\b': lambda s: f"{s[:-1]}C",   # 25c -> 25C (Celsius)
        r'\d+f\b': lambda s: f"{s[:-1]}F",   # 75f -> 75F (Fahrenheit)

        # Two-letter units
        r'\d+pa\b': lambda s: f"{s[:-2]}Pa",  # 100pa -> 100Pa
        r'\d+kpa\b': lambda s: f"{s[:-3]}kPa",  # 5kpa -> 5kPa
        r'\d+[mgt]pa\b': lambda s: f"{s[:-3]}{s[-3].upper()}Pa",  # 5mpa -> 5MPa, 5gpa -> 5GPa

        r'\d+wh\b': lambda s: f"{s[:-2]}Wh",  # 100wh -> 100Wh
        r'\d+kwh\b': lambda s: f"{s[:-3]}kWh",  # 5kwh -> 5kWh
        r'\d+[mgt]wh\b': lambda s: f"{s[:-3]}{s[-3].upper()}Wh",  # 5mwh -> 5MWh, 5gwh -> 5GWh

        r'\d+va\b': lambda s: f"{s[:-2]}VA",  # 100va -> 100VA
        r'\d+kva\b': lambda s: f"{s[:-3]}kVA",  # 5kva -> 5kVA
        r'\d+[mgt]va\b': lambda s: f"{s[:-3]}{s[-3].upper()}VA",  # 5mva -> 5MVA, 5gva -> 5GVA

        # Distance (m lowercase for meter)
        r'\d+[kmgt]m\b': lambda s: f"{s[:-1]}{s[-1].lower()}",  # 5KM -> 5km

        # Imperial/British units (naturally lowercase after digits)
        # Length: ft, in, mi
        # Volume: oz, qt, gal
        # Weight: lb, oz
        # Temperature: F (handled above with other temperature units)

        # Speed units
        # Metric (lowercase m for meter)
        r'\d+[kmgt]m/h\b': lambda s: f"{s[:-3]}{s[-3].lower()}m{R['/']}h",  # 80KM/h -> 80km⧸h
        r'\d+[kmgt]m/hr\b': lambda s: f"{s[:-4]}{s[-4].lower()}m{R['/']}hr",  # 80KM/hr -> 80km⧸hr
        # Imperial speed (naturally lowercase)
        # mph, mi⧸h, mi⧸hr
    }

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
        'as', 'if', 'how', 'than', 'v', 'vs', 'vs.',  # v/vs/vs. for versus

        # Common Words in Media Titles
        'part', 'vol', 'feat', 'ft', 'remix',

        # Be Verbs (when not first/last)
        'am', 'are', 'is', 'was', 'were', 'be', 'been', 'being'
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
            if len(original_char) != 1 and original_char not in cls.MULTI_CHAR_REPLACEMENTS:
                raise ValueError(
                    f"Invalid original character in CHAR_REPLACEMENTS: {original_char}. "
                    "Original character must be a single character or one of the allowed multi-character sequences."
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

    @classmethod
    def _validate_abbreviations(cls):
        """
        Validate and clean the ABBREVIATIONS set according to our rules.
        Modifies ABBREVIATIONS in place.
        """
        cleaned = set()
        for abbr in cls.ABBREVIATIONS:
            cleaned.add(cls._clean_abbreviation(abbr))
        cls.ABBREVIATIONS = cleaned

    def __init__(self, directory: str = '.', dry_run: bool = False):
        """
        Initialize the FileRenamer.

        Args:
            directory (str): Directory to process files in
            dry_run (bool): If True, only show what would be renamed without making changes
        """
        # Validate and clean abbreviations first
        self._validate_abbreviations()

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

        # Handle fractions (digit/digit with optional spaces)
        name = re.sub(r'(\d)\s*/\s*(\d)', r'\1⧸\2', name)

        # Handle other special characters
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if original_char == '...':
                # Handle ellipsis separately to avoid over-replacement
                self.debug_print(f"Before ellipsis replacement:    {name!r}")
                name = re.sub(r'\.{3,}', replacement_char, name)
                self.debug_print(f"After ellipsis replacement:     {name!r}")
            elif original_char != '/':
                # Replace multiple occurrences with single replacement
                # Skip the regular slash replacement since we handle it specially for fractions
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
            for i, part in enumerate(parts):
                if not part:  # Skip empty parts
                    continue

                # Convert to title case, handling special cases
                word = part.lower()  # First convert to lowercase

                self.debug_print(f"\nProcessing word: {word!r}")
                self.debug_print(f"Previous part: {prev_part!r}")
                self.debug_print(f"Is contraction: {word in self.CONTRACTIONS}")
                self.debug_print(f"Titled parts so far: {titled_parts}")

                # Handle numbers followed by words (e.g., "10web" -> "10Web")
                # But don't handle units or time (e.g., "5minutes", "9am")
                number_word_match = re.match(r'^(\d+)([a-z]+)$', word)
                if (number_word_match and
                    not re.match(r'^\d+(?:k?m|k?b|[kmgt]?hz|[ap]m|min)s?$', word.lower())):
                    self.debug_print(f"Found number-word pattern: {word!r}")
                    number, text = number_word_match.groups()
                    word = f"{number}{text.capitalize()}"
                    self.debug_print(f"After number-word handling: {word!r}")
                    titled_parts.append(word)
                    prev_part = part
                    continue

                # Skip empty parts
                if not word:
                    continue

                # Keep separators as is
                if len(part) == 1 and part in self.WORD_BOUNDARY_CHARS:
                    self.debug_print(f"Keeping separator: {part!r}")
                    titled_parts.append(part)
                    prev_part = part
                    continue

                # Special case: AM/PM after numbers (including when joined like "9am")
                if re.match(r'\d+[ap]m\b', word, re.IGNORECASE):
                    self.debug_print(f"Found time with AM/PM: {word!r}")
                    num = re.search(r'\d+', word, re.IGNORECASE).group()
                    ampm = word[len(num):].upper()
                    titled_parts.append(f"{num}{ampm}")
                    prev_part = part
                    continue

                # Check for special case words (Wi-Fi, etc.)
                word_lower = word.lower()
                if word_lower == 'wifi':  # Convert all variants to Wi-Fi
                    titled_parts.append('Wi-Fi')
                    prev_part = part
                    continue
                for special_word in self.SPECIAL_CASE_WORDS:
                    if word_lower == special_word.lower():
                        titled_parts.append(special_word)
                        prev_part = part
                        continue

                # Handle common unit patterns (GB, MHz, etc.)
                found_unit = False
                word_lower = word.lower()

                # Only try unit patterns if the word looks like it could be a unit
                # (starts with number and is followed by known unit characters)
                self.debug_print(f"Checking for unit pattern in: {word_lower!r}")
                if re.match(r'^\d+[kmgtw]?[wvajnlhzbf]', word_lower):
                    self.debug_print(f"  Potential unit pattern found")
                    for pattern, formatter in sorted(self.UNIT_PATTERNS.items(), key=lambda x: len(x[0]), reverse=True):
                        if re.match(f'^{pattern}$', word_lower, re.IGNORECASE):  # Case-insensitive exact match
                            self.debug_print(f"  Found exact unit pattern: {pattern!r}")
                            titled_parts.append(formatter(word_lower))
                            prev_part = part
                            found_unit = True
                            break
                    if not found_unit:
                        self.debug_print(f"  No exact unit pattern match found")

                if found_unit:
                    continue

                # Handle abbreviations with the following steps:
                # 1. If at end of text, try adding period when testing against ABBREVIATIONS
                # 2. Check if word is in ABBREVIATIONS set as-is
                # 3. Check if word is in ABBREVIATIONS set without periods
                # 4. If found, preserve the format from ABBREVIATIONS set

                # Build the word to test, handling period-separated parts
                test_word = word
                j = i
                if i + 1 < len(parts) and parts[i+1].strip() == '.':
                    word_parts = [word]
                    j = i + 1
                    while j < len(parts) - 1 and parts[j].strip() == '.':
                        next_part = parts[j+1].strip()
                        if not next_part:  # Skip empty parts
                            j += 1
                            continue
                        word_parts.extend(['.', next_part])
                        j += 2
                    test_word = ''.join(word_parts)

                # Step 1: If at end of text, try with trailing period
                is_end_of_text = j >= len(parts) - 1
                test_variants = [test_word.upper()]
                if is_end_of_text:
                    test_variants.insert(0, test_word.upper() + '.')
                self.debug_print(f"Testing for abbreviation: {test_word!r}")
                self.debug_print(f"Is end of text: {is_end_of_text}")
                self.debug_print(f"Test variants: {test_variants}")

                # Step 2 & 3: Check variants against ABBREVIATIONS
                found_abbrev = None
                for test_variant in test_variants:
                    # Try exact match
                    self.debug_print(f"  Trying exact match: {test_variant!r}")
                    if test_variant in self.ABBREVIATIONS:
                        found_abbrev = test_variant
                        self.debug_print(f"    Found exact match: {found_abbrev!r}")
                        break
                    # Try without periods
                    no_periods = re.sub(r'\.', '', test_variant)
                    self.debug_print(f"  Testing for abbreviation: {test_word!r}")
                    self.debug_print(f"  Is end of text: {is_end_of_text}")
                    self.debug_print(f"  Test variants: {test_variants}")
                    for abbr in self.ABBREVIATIONS:
                        abbr_no_periods = re.sub(r'\.', '', abbr)
                        if no_periods.upper() == abbr_no_periods.upper():
                            found_abbrev = abbr
                            self.debug_print(f"    Found match: {abbr!r}")
                            break
                    if found_abbrev:
                        break
                if not found_abbrev:
                    self.debug_print("  No abbreviation match found")
                else:
                    # Handle found abbreviation
                    if '.' in found_abbrev:
                        # Split into parts to preserve periods
                        parts_to_add = re.split(r'([.])', found_abbrev)
                        titled_parts.extend(parts_to_add)
                        prev_part = '.'  # Last character will be a period
                    else:
                        titled_parts.append(found_abbrev)
                        prev_part = found_abbrev[-1]
                    i = j
                    continue

                # Finally check for contractions
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

                # Check if we're between spaces or after punctuation
                # Word should be lowercase if:
                # 1. It's in our lowercase word list AND
                # 2. It's not the first word AND
                # 3. It's not after a period/ellipsis AND
                # 4. It's not the last word
                # 5. It's between spaces (not after special chars)

                is_between_spaces = prev_part == ' '

                # Always capitalize after a period/ellipsis or if it's the first/last word
                should_capitalize = (
                    not titled_parts or  # First word
                    prev_part in {'.', self.CHAR_REPLACEMENTS['...']} or  # After period or ellipsis
                    prev_part in self.OPENING_BRACKETS or  # After any opening bracket
                    word == last_real_word  # Last word
                )
                self.debug_print(f"Should capitalize:    {should_capitalize}")
                if should_capitalize:
                    self.debug_print(f"  Reason: {'First word' if not titled_parts else 'Last word' if word == last_real_word else 'After period/ellipsis' if prev_part in {'.', self.CHAR_REPLACEMENTS['...']} else 'After opening bracket'}")
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

            # Join parts and normalize periods
            name = ''.join(titled_parts)

            # First pass: look for and protect known abbreviations
            def handle_periods(match):
                full_str = name  # Capture the full string for context
                pos = match.start()
                before_char = full_str[pos-1] if pos > 0 else ''
                after_char = match.group(1)  # The letter after the period

                # Look ahead for potential abbreviation pattern (e.g., M.D)
                next_period_pos = full_str.find('.', pos + 1)
                if next_period_pos != -1 and next_period_pos - pos <= 2:
                    potential_abbrev = (before_char + '.' + after_char).upper()
                    if potential_abbrev in self.ABBREVIATIONS:
                        return f'.{after_char.upper()}'

                # Check other cases
                if before_char.isdigit() or after_char.upper() in self.ABBREVIATIONS:
                    return f'.{after_char}'

                # Not an abbreviation, add space
                return f'. {after_char}'

            name = re.sub(r'\.([a-zA-Z])', handle_periods, name)
            # Clean up any double spaces
            name = re.sub(r'\s+', ' ', name)

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
