#!/usr/bin/env python3
"""
File Renamer - Convert filenames from Ext4 (should also work with OS/X format), to NTFS-compatible format. Use English capitalization and punctuation rules for titles. Replace special characters (including characters illegal in NTFS) with similar Unicode characters.

Ideal for small business professionals seeking efficient file management solutions and enhanced workflow organization.

This script safely renames files to be compatible with NTFS filesystem while preserving
UTF-8/UTF-16 characters and applying title case formatting rules.

Note on character encoding:
- Input filenames must be valid UTF-8 or UTF-16
- NTFS internally uses UTF-16 LE for filenames
- Maximum path length on NTFS is 255 UTF-16 characters
- All replacement characters are validated to be valid UTF-16

Future possible improvements:
- Add option to convert to ASCII-only filenames (if needed for legacy systems)
- Current implementation preserves UTF-8/UTF-16 which works well with modern systems, including media files from sources like YouTube. Consider exploring how to use other character mappings.
- Designed for English-speaking users. Limited foreign language support currently included, with potential for future enhancements through community contributions.

Author: George Lerner with Cascade AI
Date: 2025-01-27
"""

import os
import re
import sys
import errno
from typing import Dict, List, Tuple
from pathlib import Path
import unicodedata
import logging
from colorama import init, Fore, Style

# Initialize colorama for cross-platform color support
init()

def get_debug_level() -> str:
    """
    Get the debug level from environment. Returns one of:
    - 'detail': Show all processing steps (RENAMER_DEBUG=detail)
    - 'normal': Show key transformations only (RENAMER_DEBUG=1 or running tests)
    - 'off': No debug output (default)
    """
    debug_env = os.environ.get('RENAMER_DEBUG')
    if debug_env == 'detail':
        return 'detail'
    if 'unittest' in sys.modules or '--debug' in sys.argv or debug_env:
        return 'normal'
    return 'off'

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

    # Can't put apostrophe in CHAR_REPLACEMENTS, since might replace with Single Right Quote or with Full Width Quotation Mark
    APOSTROPHE_REPLACEMENT = '\u2019'  # Right Single Quote

    QUOTE_LIKE_CHARS = {
        "'",    # ASCII apostrophe
        '\u2018',  # Left single quote
        '\u2019',  # Right single quote
    }

    # Character substitution mappings
    CHAR_REPLACEMENTS = {
        '\\': '\u29F5',  # ASCII backslash (has to be escaped) with Reverse Solidus Operator
        # / U+002F SOLIDUS ⁄ U+2044 FRACTION SLASH ∕ U+2215 DIVISION SLASH ／ U+FF0F FULLWIDTH SOLIDUS
        '/': '\u2215', # U+2215 DIVISION SLASH
        '\u2044': '\u2215',  # Fraction slash replaced with Division Slash, for readability
        '\uFF0F': '\u2215',  # Full-width slash replaced with Division Slash, for readability
        '"': '\uFF02',   # ASCII double quote replaced with Full-Width Quotation Mark
        '`': '\uFF02',   # Backtick replaced with Full-Width Quotation Mark
        '\u2018': '\uFF02',   # Single Left Quote replaced with Full-Width Quotation Mark
        # don't replace Single Right Quote, since might use Single Right Quote or replace with Full Width Quotation Mark
        '\u201C': '\uFF02',   # Left double quote replaced with Full-Width Quotation Mark
        '\u201D': '\uFF02',   # Right double quote replaced with Full-Width Quotation Mark
        '\u201E': '\uFF02',   # Double Low-9 Quotation Mark replaced with Full Width Quotation Mark
        '\u201F': '\uFF02',   # Double High-9 Quotation Mark replaced with Full Width Quotation Mark
        '\u2020': '\uFF02',   # Left Double Angle Quotation Mark replaced with Full Width Quotation Mark
        '\u2021': '\uFF02',   # Right Double Angle Quotation Mark replaced with Full Width Quotation Mark

        # Commented out fraction mappings - keeping for reference, more common use in filenames is 1of2 than one half
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
        '"': '\uFF02',  # Full Width Quotation Mark
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

    # Shorthand for readability
    R = CHAR_REPLACEMENTS

    # All opening bracket characters (ASCII and replacements)
    OPENING_BRACKETS = {
        # ASCII opening brackets
        '(', '[', '{', '<',
        # Replacement opening brackets
        R['<'],   # Left Black Lenticular Bracket
        R['<<'],  # Left Double Angle Bracket
        R['[['],  # Mathematical Left White Square Bracket
        R['{{'],  # Left White Curly Bracket
    }

    # All closing bracket characters (ASCII and replacements)
    CLOSING_BRACKETS = {
        # ASCII closing brackets
        ')', ']', '}', '>',
        # Replacement closing brackets
        R['>'],   # Right Black Lenticular Bracket
        R['>>'],  # Right Double Angle Bracket
        R[']]'],  # Mathematical Right White Square Bracket
        R['}}'],  # Right White Curly Bracket
    }

    # Characters that are allowed at the end of a filename
    ALLOWED_TRAILING_CHARS = CLOSING_BRACKETS | {
        '!',            # Exclamation mark
        R['$'],         # Full Width Dollar Sign
        R['"'],        # Full Width Quotation Mark
        R['?'],         # Double Question Mark
    }

    # Only include special characters that should act as word boundaries
    WORD_BOUNDARY_CHARS = {
        R['\\'], R[':'], R['*'], R['?'], R['|'], R['"'], R['/'],  # Special character replacements
        '.', ' ', '-', "'",              # Standard word boundaries (not yet replacing apostrophe)
        R['<'], R['>'],                  # Angle brackets
        R['...'],                        # Ellipsis
        '(', '[', '{', '<',              # ASCII opening brackets
        ')', ']', '}', '>',              # ASCII closing brackets
        R['<'], R['<<'], R['[['], R['{{'],  # Replacement opening brackets
        R['>'], R['>>'], R[']]'], R['}}'],  # Replacement closing brackets
    }

    # File extensions where we want to preserve the original case of the base name
    # Only includes extensions that might be included/imported/required by code
    PRESERVE_CASE_EXTENSIONS = {
        # Web
        'html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'vue', 'php',
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
        # Academic Degrees (use periods just for testing the clean_abbreviation function)
        'B.A', 'B.S', 'M.A', 'M.B.A', 'M.D', 'M.S', 'Ph.D', 'J.D',

        # Professional Titles (multi-letter, no periods)
        'Dr', 'Mr', 'Mrs', 'Ms', 'Prof', 'Rev',
        'Hon',  # Honorable (Judge)
        'Sr', 'Sra', 'Srta',  # Señor, Señora, Señorita
        'Asst',              # Assistant
        'VP', 'EVP', 'SVP',  # Vice President variants

        # Name Suffixes (no periods)
        'Jr', 'Sr', 'II', 'III', 'IV',  # Note: V excluded as it conflicts with 'versus'

        # Military Ranks (no periods)
        'Cpl', 'Sgt', 'Lt', 'Capt', 'Col', 'Gen',  # Common ranks
        'Maj', 'Adm', 'Cmdr', 'Brig', # More ranks
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
        'EPA', 'ICE', 'SSA', 'UN', 'USPS',
        # not 'SEC', 'sec' is a numbered unit

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
        'IDE', 'GUI', 'CLI', 'CSS', 'RSS', 'UPC', 'UPS','QR', 'AI', 'ML',

        # Media Formats
        # Images
        'JPEG', 'JPG', 'PNG', 'GIF', 'BMP', 'TIF', 'TIFF', 'SVG', 'WebP',
        # Video
        'AVI', 'MP4', 'MKV', 'MOV', 'WMV', 'FLV', 'WebM', 'M4V', 'VOB',
        # Audio
        'MP3', 'WAV', 'AAC', 'OGG', 'FLAC', 'WMA', 'M4A',
        # Quality/Standards
        '4K', '8K', 'HDR', 'DTS', 'IMAX', 'UHD',

        # Medical/Scientific
        'DNA', 'RNA', 'CRISPR', 'CPAP', 'BiPAP', 'HIV', 'AIDS', 'CDC',
        'MRI', 'CT', 'EKG', 'ECG', 'X-Ray', 'ICU', 'ER',

        # Business/Organizations
        'CEO', 'CFO', 'CIO', 'COO', 'CTO', 'LLC', 'LLP',
        'VP', 'vs',
        # Note: removed VS to avoid confusion,
        # removed HR (human resources) since conflicts with hr (hour)

        # Other Common
        'ID', 'OK', 'PC', 'PIN', 'PO', 'PS', 'RIP', 'UFO', 'VIP', 'ZIP',
        'DIY', 'FAQ', 'ASAP', 'IMAX', 'STEM',

        # Software/Platforms
        'WordPress', 'iOS', 'macOS', 'SQL', 'NoSQL', 'MySQL',
    }

    # Month names and abbreviations with proper capitalization
    # In __init__, MONTH_FORMATS values get added to:
    # 1. ABBREVIATIONS - to handle dates with separators like 25-Jan-12
    # 2. UNIT_PATTERNS - to handle dates without separators like 2025jan12
    # Units that can appear standalone without numbers
    STANDALONE_UNITS = {
        'hr', 'h',    # hour
        'min',       # minute (but not 'm' which is meters)
        's', 'sec',  # second
        'd',         # day
        'wk',        # week
        'mo',        # month
        'yr',        # year
        'sq',        # square
        'sqm'        # square meters
    }

    MONTH_FORMATS = {
        # English full names
        'january': 'January', 'february': 'February', 'march': 'March',
        'april': 'April', 'may': 'May', 'june': 'June', 'july': 'July',
        'august': 'August', 'september': 'September', 'october': 'October',
        'november': 'November', 'december': 'December',
        # English abbreviations
        'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
        'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
        'sep': 'Sep', 'sept': 'Sept', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec',
        # Spanish full names
        'enero': 'Enero', 'febrero': 'Febrero', 'marzo': 'Marzo',
        'abril': 'Abril', 'mayo': 'Mayo', 'junio': 'Junio', 'julio': 'Julio',
        'agosto': 'Agosto', 'septiembre': 'Septiembre', 'octubre': 'Octubre',
        'noviembre': 'Noviembre', 'diciembre': 'Diciembre',
        # Spanish abbreviations
        'ene': 'Ene', 'abr': 'Abr', 'ago': 'Ago', 'dic': 'Dic'
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
        # Weight units (no space, preserve case)
        r'\d+mg\b': lambda s: f"{s}",  # 5mg -> 5mg
        r'\d+g\b': lambda s: f"{s}",   # 5g -> 5g
        r'\d+kg\b': lambda s: f"{s}",  # 5kg -> 5kg

        # Data units (preserve original case)
        r'\d+kb\b': lambda s: f"{s}",  # 5kb -> 5kb
        r'\d+KB\b': lambda s: f"{s}",  # 5KB -> 5KB
        r'\d+[mgt]b\b': lambda s: f"{s}",  # Keep original case
        r'\d+[MGT]B\b': lambda s: f"{s}",  # Keep original case

        # Network speed (preserve case)
        r'\d+kbps\b': lambda s: f"{s}",  # 5kbps -> 5kbps
        r'\d+[mgt]bps\b': lambda s: f"{s}",  # 5mbps -> 5mbps

        # Frequency (k lowercase, M/G/T uppercase + Hz)
        r'\d+hz\b': lambda s: f"{s[:-2]}Hz",  # 100hz -> 100Hz
        r'\d+khz': lambda s: f"{s[:-3]}kHz",  # 100khz -> 100kHz
        r'\d+[mgt]hz': lambda s: f"{s[:-3]}{s[-3].upper()}Hz",  # 100mhz -> 100MHz

        # Time (always uppercase)
        r'\d+[ap]m': lambda s: f"{s[:-2]}{s[-2:].upper()}",  # 5pm -> 5PM

        # Liters (L always uppercase)
        r'\d+l\b': lambda s: f"{s[:-1]}L",  # 5l -> 5L
        r'\d+[kmgt]l\b': lambda s: f"{s[:-2]}{s[-2].lower()}L",  # 5ml -> 5mL

        # Video resolutions (p/i lowercase, number preserved)
        r'\d+[pi]\b': lambda s: f"{s}",  # 1080p -> 1080p, 1080i -> 1080i
        r'\d+k\b': lambda s: f"{s}",  # 4k -> 4k
        r'\d+K\b': lambda s: f"{s}",  # 4K -> 4K

        # Greek letter units (always uppercase)
        r'\d+ω\b': lambda s: f"{s[:-1]}Ω",  # 100ω -> 100Ω

        # Square measurements
        r'\d+sq\b': lambda s: f"{s}",  # 50sq -> 50sq
        r'\d+sqm\b': lambda s: f"{s}",  # 100sqm -> 100sqm

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

        # Digital units (preserve lowercase)
        r'\d+bit\b': lambda s: f"{s}",  # 24bit
        r'\d+fps\b': lambda s: f"{s}",  # 30fps
        r'\d+rpm\b': lambda s: f"{s}",  # 33rpm
        r'\d+mph\b': lambda s: f"{s}",  # 60mph
        r'\d+mpg\b': lambda s: f"{s}",  # 35mpg (miles per gallon)
        r'\d+lkm\b': lambda s: f"{s}",  # 7lkm (liters per kilometer)
        r'\d+deg\b': lambda s: f"{s}",  # 68deg

        # Ordinal numbers
        r'\b1[1-9]th\b': lambda s: f"{s.lower()}",  # special cases 11th through 19th
        r'\b\d*1st\b': lambda s: f"{s.lower()}",    # 1ST -> 1st, 21ST -> 21st, 101ST -> 101st
        r'\b\d*2nd\b': lambda s: f"{s.lower()}",    # 2ND -> 2nd, 32ND -> 32nd, 442ND -> 442nd
        r'\b\d*3rd\b': lambda s: f"{s.lower()}",    # 3RD -> 3rd, 43RD -> 43rd, 333RD -> 333rd
        r'\b\d*[4-9]th\b': lambda s: f"{s.lower()}", # 4TH -> 4th, 75TH -> 75th, 999TH -> 999th

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
        r'\d+m\b': lambda s: f"{s[:-1]}m",  # 5M -> 5m (bare meters)
        r'\d+[kmgt]m\b': lambda s: f"{s[:-1]}{s[-1].lower()}",  # 5KM -> 5km

        # Imperial/British units (naturally lowercase after digits)
        # Length: ft, in, mi
        # Volume: oz, qt, gal
        # Weight: lb, oz
        # Temperature: F (handled above with other temperature units)

        # Time units (with or without numbers)
        # Hours
        r'\b\d*\s*hr\b': lambda s: f"{s}",  # 24hr -> 24hr, hr -> hr
        r'\b\d*\s*h\b': lambda s: f"{s}",   # 24h -> 24h, h -> h
        r'\b\d*\s*/\s*hr\b': lambda s: re.sub(r'(\d*)\s*/\s*hr',
            lambda m: f"{m.group(1)}{R['/']}hr", s),  # 30/hr -> 30⧸hr, /hr -> ⧸hr
        r'\b\d*\s*/\s*h\b': lambda s: re.sub(r'(\d*)\s*/\s*h',
            lambda m: f"{m.group(1)}{R['/']}h", s),   # 30/h -> 30⧸h, /h -> ⧸h

        # Minutes
        r'\b\d*\s*min\b': lambda s: f"{s}",  # 15min -> 15min, min -> min
        r'\b\d*\s*/\s*min\b': lambda s: re.sub(r'(\d*)\s*/\s*min',
            lambda m: f"{m.group(1)}{R['/']}min", s),  # 30/min -> 30⧸min, /min -> ⧸min

        # Seconds
        r'\b\d*\s*sec\b': lambda s: f"{s}",  # 30sec -> 30sec, sec -> sec
        r'\b\d*\s*s\b': lambda s: f"{s}",    # 30s -> 30s, s -> s
        r'\b\d*\s*/\s*sec\b': lambda s: re.sub(r'(\d*)\s*/\s*sec',
            lambda m: f"{m.group(1)}{R['/']}sec", s),  # 30/sec -> 30⧸sec, /sec -> ⧸sec
        r'\b\d*\s*/\s*s\b': lambda s: re.sub(r'(\d*)\s*/\s*s',
            lambda m: f"{m.group(1)}{R['/']}s", s),    # 30/s -> 30⧸s, /s -> ⧸s

        # Days, Weeks, Months, Years
        r'\b\d*\s*d\b': lambda s: f"{s}",    # 30d -> 30d, d -> d
        r'\b\d*\s*wk\b': lambda s: f"{s}",  # 52wk -> 52wk, wk -> wk
        r'\b\d*\s*mo\b': lambda s: f"{s}",  # 12mo -> 12mo, mo -> mo
        r'\b\d*\s*yr\b': lambda s: f"{s}",  # 10yr -> 10yr, yr -> yr

        r'\b\d*\s*/\s*d\b': lambda s: re.sub(r'(\d*)\s*/\s*d',
            lambda m: f"{m.group(1)}{R['/']}d", s),    # 30/d -> 30⧸d, /d -> ⧸d
        r'\b\d*\s*/\s*wk\b': lambda s: re.sub(r'(\d*)\s*/\s*wk',
            lambda m: f"{m.group(1)}{R['/']}wk", s),  # 52/wk -> 52⧸wk, /wk -> ⧸wk
        r'\b\d*\s*/\s*mo\b': lambda s: re.sub(r'(\d*)\s*/\s*mo',
            lambda m: f"{m.group(1)}{R['/']}mo", s),  # 12/mo -> 12⧸mo, /mo -> ⧸mo
        r'\b\d*\s*/\s*yr\b': lambda s: re.sub(r'(\d*)\s*/\s*yr',
            lambda m: f"{m.group(1)}{R['/']}yr", s),  # 10/yr -> 10⧸yr, /yr -> ⧸yr
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

    # Characters that trigger capitalization of the next word
    CAPITALIZATION_TRIGGERS = {
        '.',  # Period
        '-',  # Dash/Hyphen
        R['...'],  # Ellipsis
        R[':'],    # Colon
        R['|'],    # Pipe/Vertical bar
        *OPENING_BRACKETS  # All opening brackets
    }

    # Debug mode flag
    _debug_level = get_debug_level()
    _debug = False  # Initialize debug flag for command line use

    @classmethod
    def colorize(cls, char):
        """Colorize characters:
        - Cyan for characters in CHAR_REPLACEMENTS
        - Green for non-ASCII characters not in CHAR_REPLACEMENTS
        - no coloring for ASCII characters
        """
        if char in cls.CHAR_REPLACEMENTS.values():
            return f"{Fore.CYAN}{char}{Style.RESET_ALL}"
        elif ord(char) > 127:  # Non-ASCII character
            return f"{Fore.GREEN}{char}{Style.RESET_ALL}"
        return char

    @classmethod
    def debug_print(cls, *args, level='normal', **kwargs):
        """Print debug message if level matches current debug level

        Args:
            level: Required debug level ('normal' or 'detail')
        """
        if cls._debug_level == 'off':
            return
        if level == 'detail' and cls._debug_level != 'detail':
            return
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

        # Month names and abbreviations must be in ABBREVIATIONS to handle dates with separators:
        #   25-Jan-12 -> split into ['25', '-', 'jan', '-', '12'] and 'jan' -> 'Jan'
        #   25.Jan.12 -> split into ['25', '.', 'jan', '.', '12'] and 'jan' -> 'Jan'
        # Cannot move these to UNIT_PATTERNS because separators break the pattern matching
        self.ABBREVIATIONS.update(proper for _, proper in self.MONTH_FORMATS.items())

        # Add month patterns to UNIT_PATTERNS for dates without separators:
        #   2025jan12 -> stays as one word, need pattern to find/replace 'jan' -> 'Jan'
        # Cannot use ABBREVIATIONS because it only matches whole words, not parts
        # Must handle these like other unit patterns (e.g. 5k -> 5K) to find/replace
        # the month part while preserving the surrounding numbers
        # Handle both formats: numbers before (2025jan12) and after (jan2025)
        month_patterns = {}
        for month, proper in self.MONTH_FORMATS.items():
            # Pattern for numbers before month (2025jan12)
            month_patterns[f'\\d+{month}\\d*\\b'] = \
                lambda s, m=month, p=proper: re.sub(m, p, s, flags=re.IGNORECASE)
            # Pattern for month before numbers (jan2025)
            month_patterns[f'\\b{month}\\d+\\b'] = \
                lambda s, m=month, p=proper: re.sub(m, p, s, flags=re.IGNORECASE)
        self.UNIT_PATTERNS.update(month_patterns)

    def _check_abbreviation_with_context(self, current_part, titled_parts, is_last_part):
        """Check if current part and previous parts form an abbreviation.

        Args:
            current_part: Current part being processed
            titled_parts: List of already processed parts
            is_last_part: True if this is the last part of the filename (extension already stripped)

        Examples:
            "M.D" -> current="D", titled=["M", "."] -> "MD"
            "LT.COL" -> current="COL", titled=["LT", "."] -> "Lt.Col"

        Boundary cases (at end of filename):
            "m.d" -> current="d", titled=["M", "."], is_last_part=True -> "MD"
        """
        self.debug_print(f"Entered check_abbreviation_with_context, titled_parts={titled_parts!r}")

        if not titled_parts:
            return False

        # Get previous parts until we hit a space or comma
        # This allows periods and other chars to be part of abbreviation
        # But spaces/commas separate different abbreviations
        prev_parts = []
        for part in titled_parts[::-1]:
            if part in {' ', ','}:
                break
            prev_parts.insert(0, part)
        self.debug_print(f"    prev_parts collected: {prev_parts!r}")

        # Try combining with current part
        combined = ''.join(prev_parts) + current_part
        cleaned = self._clean_abbreviation(combined)
        self.debug_print(f"    combined={combined!r} cleaned={cleaned!r}")

        # Check if it forms a known abbreviation (case-insensitive)
        for abbr in self.ABBREVIATIONS:
            if cleaned.upper() == abbr.upper():
                # Check if this should be a compound abbreviation
                if prev_parts == ['.'] and len(titled_parts) >= 2 and titled_parts[-2] in self.ABBREVIATIONS:
                    # Show state before combining
                    self.debug_print(f"    Compound check: prev_parts={prev_parts!r} titled_parts={titled_parts!r} current={current_part!r}")
                    # Combine with previous abbreviation
                    first_abbrev = titled_parts[-2]
                    titled_parts[-2] = first_abbrev + abbr
                    self.debug_print(f"    ✓ Found compound abbreviation: {first_abbrev!r} + '.' + {abbr!r} -> {titled_parts[-2]!r}")
                else:
                    # Store as individual abbreviation
                    titled_parts[-len(prev_parts):] = []
                    titled_parts.append(abbr)
                    self.debug_print(f"    ✓ Found abbreviation: {abbr!r} (titled_parts={titled_parts!r})")
                return True
        return False

    def _clean_trailing_chars(self, text: str, debug_prefix: str = '') -> str:
        """Clean trailing special characters from text.

        Args:
            text: Text to clean
            debug_prefix: Optional prefix for debug output

        Returns:
            Cleaned text with trailing special characters removed
        """
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

        return text

    def _clean_filename(self, filename: str) -> str:
        """Clean filename to be NTFS-compatible."""

        try:
            filename.encode('utf-16')
        except UnicodeEncodeError as e:
            raise ValueError(f"Input filename contains invalid characters: {e}")

        self.debug_print(f"\nProcessing: {filename!r}", level='normal')

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

        # Get reference to replacements dict for cleaner code
        R = FileRenamer.CHAR_REPLACEMENTS

        # First normalize all whitespace to single spaces
        # Debug processing steps
        self.debug_print(f"Splitting name: {name!r} (extension: {extension!r})", level='detail')

        # Normalize whitespace
        # self.debug_print(f"Before whitespace normalization: {name!r}", level='detail')  # Commented for easy re-enabling
        name = re.sub(r'[\n\r\t\f\v]+', ' ', name)  # Convert newlines and other whitespace to spaces
        name = re.sub(r' {2,}', ' ', name)  # Collapse multiple spaces
        # self.debug_print(f"After whitespace normalization:  {name!r}\n", level='detail')

        # Replace special characters
        self.debug_print(f"Before replacements: {name!r}", level='normal')

        # Function to colorize replacement chars
        def colorize(char):
            return f"{Fore.CYAN}{char}{Style.RESET_ALL}"

        # Handle fractions first (digit/digit with optional spaces)
        name = re.sub(r'(\d)\s*/\s*(\d)', fr'\1{R["/"]}\2', name)

        # Handle multi-char sequences (like ellipsis, brackets)
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if len(original_char) > 1:  # Multi-char replacement
                if original_char in name:
                    self.debug_print(f"  Replace: '{original_char}' → '{colorize(replacement_char)}'", level='detail')
                    if original_char == '...':
                        # Handle ellipsis specially to match 3 or more dots
                        name = re.sub(r'\.{3,}', replacement_char, name)
                    else:
                        name = name.replace(original_char, replacement_char)

        # Handle single-char replacements
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if len(original_char) == 1:  # Single-char replacements
                if original_char in name:
                    self.debug_print(f"  Replace: '{original_char}' → '{colorize(replacement_char)}'", level='detail')
                    name = re.sub(f'{re.escape(original_char)}+', replacement_char, name)

        # Show replaced characters in color in the final output
        colored_parts = []
        for c in name:
            if any(c == repl for repl in R.values()):
                colored_parts.append(colorize(c))
            else:
                colored_parts.append(c)
        colored_name = ''.join(colored_parts)
        # Don't use !r here as it escapes the color codes
        self.debug_print(f"After replacements: '{colored_name}'", level='normal')

        # Clean up whitespace
        name = name.strip()

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
        # For files with extensions such as programming files (.c, .py, .js), preserve the original name case
        # Extensions are always lowercased
        if not extension.lower() in self.PRESERVE_CASE_EXTENSIONS:
            # Build pattern that matches our word boundaries
            split_pattern = '([' + ''.join(re.escape(c) for c in self.WORD_BOUNDARY_CHARS) + '])'
            self.debug_print(f"\nSplit pattern: {split_pattern}")

            # First do a quick validation of how many parts we might get
            test_parts = re.split(split_pattern, name)
            if len(test_parts) > 200:  # Very generous limit, normal files have 30-90 parts
                self.debug_print(f"Filename too complex: {len(test_parts)} parts exceeds limit of 200")
                return name  # Return original name if too complex

            parts = test_parts
            self.debug_print(f"Parts after split: {parts!r}\n")

            titled_parts = []
            prev_part = ''
            prev_was_abbrev = False
            prior_abbreviation = None
            last_real_word = None
            for part in parts:
                if part and len(part) > 1 and not any(c in self.WORD_BOUNDARY_CHARS for c in part):
                    last_real_word = part.lower()

            # Track which parts we've processed and why
            processed_parts = {}

            # Now process each part
            for i, part in enumerate(parts):
                if i in processed_parts:
                    self.debug_print(f"\n[SKIP] Part {i}: {part!r} ({processed_parts[i]})")
                    continue
                if not part:  # Skip empty parts
                    continue

                self.debug_print(f"\nProcessing part {i}: {part!r} (len={len(part)}, has_boundary={[c for c in part if c in self.WORD_BOUNDARY_CHARS]})")

                # Convert to title case, handling special cases
                word = part.lower()  # First convert to lowercase
                self.debug_print(f"  After case conversion: {part!r} -> {word!r}")

                self.debug_print(f"\n⮑ Word: {word!r} (prev={prev_part!r}, contraction={word in self.CONTRACTIONS})")



                # Skip empty parts
                if not word:
                    continue

                # Keep separators as is
                if len(part) == 1 and part in self.WORD_BOUNDARY_CHARS:
                    # Skip adding period if it follows an abbreviation or compound
                    if part == '.' and ((titled_parts and titled_parts[-1] in self.ABBREVIATIONS) or prior_abbreviation):
                        self.debug_print(f"Skipping period after abbreviation: {prior_abbreviation or titled_parts[-1]!r}")
                        prev_part = part
                        continue

                    self.debug_print(f"Keeping separator: {part!r}")
                    titled_parts.append(part)
                    prev_part = part
                    # Only reset prev_was_abbrev for spaces and periods
                    if part in {' ', '.'}:
                        prev_was_abbrev = False
                    continue

                # First check if this part could be part of an abbreviation
                # This must come before unit/contraction checks to properly handle cases like:
                # - "m.d" -> "MD" (abbreviation)
                # - "10d" -> "10d" (unit)
                # - "I'd" -> "I'd" (contraction)
                # Debug abbreviation check
                self.debug_print(f"  Checking abbreviation: part={part!r} isalpha={part.isalpha()!r}")
                if titled_parts:
                    self.debug_print(f"    titled_parts[-1]={titled_parts[-1]!r}")
                    self.debug_print(f"    all titled_parts={titled_parts!r}")

                if part.isalpha():
                    # Check for compound abbreviation pattern (e.g. Lt.Col)
                    if (titled_parts and
                        prev_part == '.' and
                        titled_parts[-1] in self.ABBREVIATIONS):
                        self.debug_print(f"  Compound check state:")
                        self.debug_print(f"    part={part!r}")
                        self.debug_print(f"    prev_part={prev_part!r}")
                        self.debug_print(f"    titled_parts={titled_parts!r}")

                        # Get first abbreviation before loop
                        first_abbrev = titled_parts[-1]    # e.g. "Lt"
                        second_abbrev = None  # Initialize to None
                        self.debug_print(f"    first_abbrev={first_abbrev!r}")

                        # Check if second part matches an abbreviation
                        for abbr in self.ABBREVIATIONS:
                            if part.upper() == abbr.upper():
                                # Found abbreviation-period-abbreviation pattern
                                self.debug_print(f"    Match found: part.upper()={part.upper()!r} == abbr.upper()={abbr.upper()!r}")
                                second_abbrev = abbr  # Use case from ABBREVIATIONS
                                self.debug_print(f"    Set second_abbrev={second_abbrev!r}")

                                # Combine abbreviations (no need to remove period since it wasn't added)
                                self.debug_print(f"    Before combine: titled_parts[-1]={titled_parts[-1]!r}")
                                titled_parts[-1] = first_abbrev + second_abbrev
                                self.debug_print(f"    After combine: titled_parts[-1]={titled_parts[-1]!r}")

                                # Update tracking variables
                                prev_part = titled_parts[-1]
                                prev_was_abbrev = True
                                prior_abbreviation = titled_parts[-1]  # Track compound as prior_abbreviation
                                break

                        self.debug_print(f"    After loop:")
                        self.debug_print(f"      second_abbrev={second_abbrev!r}")
                        self.debug_print(f"      titled_parts={titled_parts!r}")
                        self.debug_print(f"      prev_part={prev_part!r}")

                        if second_abbrev is not None:
                            continue

                    # Otherwise check for normal abbreviation
                    elif titled_parts and prev_part == '.':
                        self.debug_print(f"  ✓ Found potential abbreviation part")
                        # Check if current part with previous parts forms an abbreviation
                        # For example: current='d', prev=['M', '.'] -> 'M.d' -> 'MD'
                        is_last = i == len(parts) - 1 or all(p in self.WORD_BOUNDARY_CHARS for p in parts[i+1:])

                        if self._check_abbreviation_with_context(word, titled_parts, is_last):
                            prev_part = word
                            prev_was_abbrev = True
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
                    prior_abbreviation = None  # Reset for non-abbreviation
                    continue
                for special_word in self.SPECIAL_CASE_WORDS:
                    if word_lower == special_word.lower():
                        titled_parts.append(special_word)
                        prev_part = part
                        continue

                # Handle common unit patterns (GB, MHz, etc.)
                found_unit = False
                word_lower = word.lower()

                # Try unit patterns for:
                # 1. Standard units (GB, MHz, Ω, etc.)
                # 2. Dates with month abbreviations (2025jan12, jan2025)
                # 3. Units after a slash (30km/hr)
                # This must come before abbreviation check to handle concatenated formats
                if (re.match(r'^\d+[kmgtw]?[wvajnlhzbfω][h]?', word_lower) or  # Standard units (including compound like wh)
                    re.match(r'^\d+[a-z]|^[a-z]+\d', word_lower) or      # Date formats
                    word_lower in self.STANDALONE_UNITS):                  # Standalone units
                    self.debug_print(f"\n⮑ Unit check for: {part!r} (lower={word_lower!r})")
                    self.debug_print(f"  Context: parts[{i}] in {parts!r}")

                    # Initialize unit tracking
                    j = i  # Current position
                    unit_parts = [part]  # Track all parts of the unit
                    test_word = word_lower
                    original_parts = [part]

                    # Check for space-separated units (e.g. "5 kb" or "5 g")
                    if i + 2 < len(parts) and parts[i+1].strip() == ' ':
                        next_part = parts[i+2].strip().lower()
                        if re.match(r'^[kmgtw]?[wvajnlhzbf]', next_part):
                            # Include space and unit part
                            unit_parts.extend([parts[i+1], parts[i+2]])
                            original_parts.extend([parts[i+1], parts[i+2]])
                            test_word = word_lower + next_part
                            j = i + 2
                            self.debug_print(f"  Found space-separated unit: {unit_parts!r}")

                    self.debug_print(f"  Testing unit pattern: {test_word!r}")
                    self.debug_print(f"  Original parts: {original_parts!r}")

                    # Try to match unit patterns
                    for pattern, formatter in sorted(self.UNIT_PATTERNS.items(), key=lambda x: len(x[0]), reverse=True):
                        match = re.match(f'^{pattern}$', test_word, re.IGNORECASE)
                        if match:  # Case-insensitive exact match
                            # For bits/bytes and bps units, enforce prefix case but preserve b/B
                            if re.search(r'\d+[kmgt]?b(?:ps)?\b', test_word, re.IGNORECASE):
                                # Find the unit part (kb, MB, bps, Bps etc)
                                unit_match = re.search(r'[kmgt]?b(?:ps)?\b', test_word, re.IGNORECASE)
                                if unit_match:
                                    # Get original case for just the b/B part
                                    orig_b_case = None
                                    for p in original_parts:
                                        if unit_match.group().lower() in p.lower():
                                            # Match the b/B and optional ps
                                            b_pattern = r'[bB](?:[pP][sS])?\b'
                                            b_search = re.search(b_pattern, p)
                                            if b_search:
                                                orig_b_case = b_search.group()
                                                break

                                    if orig_b_case:
                                        # Extract the prefix and number
                                        prefix_match = re.match(r'(\d+)([kmgt])?', test_word, re.IGNORECASE)
                                        if prefix_match:
                                            number = prefix_match.group(1)
                                            prefix = prefix_match.group(2)

                                            # Apply prefix case rules
                                            if prefix:
                                                if prefix.lower() == 'k':
                                                    prefix = 'k'  # Always lowercase
                                                else:
                                                    prefix = prefix.upper()  # M, G, T always uppercase

                                            # Combine with preserved b/B case
                                            formatted = f"{number}{prefix or ''}{orig_b_case}"
                                            self.debug_print(f"    Applied case rules: {test_word!r} -> {formatted!r}")
                                    else:
                                        formatted = formatter(test_word)
                                else:
                                    formatted = formatter(test_word)
                            else:
                                # Apply normal unit formatting
                                formatted = formatter(test_word)

                            unit_debug = f"✓ Unit: {formatted!r} (from={original_parts!r}, pattern={pattern!r})"
                            self.debug_print(f"    Applied formatter: {test_word!r} -> {formatted!r}")

                            # Mark all parts that make up this unit as processed
                            for idx in range(i, j+1):
                                processed_parts[idx] = f"part of {unit_debug}"

                            # Add the formatted unit preserving any spaces
                            # Replace the matched content with formatted version
                            parts_with_spaces = []
                            for p in original_parts:
                                if p.strip().lower() == test_word.lower():
                                    parts_with_spaces.append(formatted)
                                else:
                                    parts_with_spaces.append(p)

                            formatted_with_spaces = ''.join(parts_with_spaces)
                            titled_parts.append(formatted_with_spaces)
                            prev_part = formatted  # Store just the unit as prev_part

                            self.debug_print(f"  {unit_debug}")
                            found_unit = True
                            i = j  # Move to end of unit
                            break

                    if not found_unit:
                        # Only try number-word if no unit pattern matched
                        if re.match(r'^\d+[a-z]+$', word_lower):
                            self.debug_print(f"  Found number-word: {word!r}")
                            # Find where the numbers end and letters begin
                            match = re.match(r'^(\d+)([a-z]+)$', word_lower)
                            if match:
                                numbers, letters = match.groups()
                                word = numbers + letters[0].upper() + letters[1:]
                                titled_parts.append(word)
                                prev_part = word
                                processed_parts[i] = f"number-word: {word!r}"
                                continue
                        self.debug_print(f"  No unit pattern match found")

                if found_unit:
                    continue

                # Handle abbreviations - check if this word is an abbreviation
                # If the previous word was also an abbreviation, we'll handle this
                # one separately rather than trying to join them
                test_word = word.upper()
                j = i

                # Check if this word matches an abbreviation
                found_abbrev = None
                abbrev_debug = ""

                self.debug_print(f"  Abbrev check: {test_word!r} (end={j >= len(parts) - 1})")

                # Try exact match first (case-insensitive)
                for abbr in self.ABBREVIATIONS:
                    if test_word.upper() == abbr.upper():
                        found_abbrev = abbr  # Use case from ABBREVIATIONS
                        abbrev_debug = f"✓ {found_abbrev!r} (exact)"
                        break
                else:
                    # Try without periods
                    clean_word = self._clean_abbreviation(test_word)
                    for abbr in self.ABBREVIATIONS:
                        if clean_word.upper() == abbr.upper():
                            found_abbrev = abbr
                            abbrev_debug = f"✓ {found_abbrev!r} (no periods)"
                            break

                # If at end of text and no match, try with trailing period
                if not found_abbrev and j >= len(parts) - 1:
                    test_word_period = test_word + '.'
                    if test_word_period in self.ABBREVIATIONS:
                        found_abbrev = test_word_period
                        abbrev_debug = f"✓ {found_abbrev!r} (with period)"

                if found_abbrev:
                    # Found an abbreviation
                    processed_parts[i] = abbrev_debug
                    self.debug_print(abbrev_debug)

                    if '.' in found_abbrev:
                        # Split into parts to preserve periods
                        parts_to_add = re.split(r'([.])', found_abbrev)
                        titled_parts.extend(parts_to_add)
                        prev_part = found_abbrev  # Keep the full abbreviation as previous part
                        prev_was_abbrev = True  # Mark that we found a valid abbreviation
                    else:
                        titled_parts.append(found_abbrev)
                        prev_part = found_abbrev  # Keep the full abbreviation as previous part
                        prev_was_abbrev = True  # Mark that we found a valid abbreviation
                    continue

                # Not an abbreviation, let it fall through to normal word handling
                self.debug_print("  No abbreviation match found")

                # Finally check for contractions
                if word in self.CONTRACTIONS and len(titled_parts) >= 2:
                    # Get the full contraction (e.g., 'Didn't' from ['Didn', "'", 't'])
                    base_word = titled_parts[-2] if len(titled_parts) >= 2 else ''
                    full_contraction = f"{base_word}'{word}" if prev_part == "'" and not titled_parts[-2].isspace() else None

                    self.debug_print(f"  Contraction check: {word!r} (base={base_word!r})")
                    # Check if it follows a word + apostrophe (not space + apostrophe)
                    if full_contraction:
                        self.debug_print(f"    ✓ Accepted: {full_contraction!r}")
                        titled_parts.append(word)
                        prev_part = full_contraction  # Store the full contraction as prev_part
                        continue
                    self.debug_print(f"    ✗ Rejected: not after word + apostrophe")

                # Check if we're between spaces or after punctuation
                # Word should be lowercase if:
                # 1. It's in our lowercase word list AND
                # 2. It's not the first word AND
                # 3. It's not after a period/ellipsis AND
                # 4. It's not the last word
                # 5. It's between spaces (not after special chars)

                is_between_spaces = prev_part == ' '

                # Find the last non-space part for checking capitalization triggers
                last_non_space = next((p for p in reversed(titled_parts) if p.strip()), '') if titled_parts else ''

                # Always capitalize after certain punctuation or if it's the first/last word
                self.debug_print(f"  Title case check: first={not titled_parts}, last={word == last_real_word}, after_trigger={last_non_space in self.CAPITALIZATION_TRIGGERS}")
                should_capitalize = (
                    not titled_parts or  # First word
                    last_non_space in self.CAPITALIZATION_TRIGGERS or  # After trigger characters
                    word == last_real_word  # Last word
                )
                # First check if we should force capitalize
                reason = ('First word' if not titled_parts else
                         'Last word' if word == last_real_word else
                         'After punctuation' if last_non_space in self.CAPITALIZATION_TRIGGERS else
                         'Between special chars' if not is_between_spaces else
                         'Unknown')

                # Then check if we should force lowercase
                should_lowercase = (word in self.LOWERCASE_WORDS and
                                  titled_parts and  # Not first word
                                  not should_capitalize and  # Not after period/ellipsis
                                  word != last_real_word and  # Not the last word
                                  is_between_spaces)  # Between spaces, not after special char

                case_reason = f"capitalize ({reason})" if should_capitalize else \
                             f"lowercase (in list)" if should_lowercase else \
                             f"capitalize (not in lowercase list)"
                self.debug_print(f"  Case: {case_reason}")
                if (word in self.LOWERCASE_WORDS and
                    titled_parts and      # Not first word
                    not should_capitalize and  # Not after period/ellipsis
                    word != last_real_word and  # Not the last word
                    is_between_spaces):   # Between spaces, not after special char

                    self.debug_print(f"  Adding to titled_parts: {word!r} (lowercase)")
                    titled_parts.append(word)
                else:
                    self.debug_print(f"  Adding to titled_parts: {word.capitalize()!r} (capitalized)")
                    titled_parts.append(word.capitalize())
                prev_part = part
                prior_abbreviation = None  # Reset for non-abbreviation word

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

        return result

    def process_files(self) -> List[Tuple[str, str]]:
        """
        Process all files in the directory.

        Returns:
            List[Tuple[str, str]]: List of (original_name, new_name) pairs

        Note:
            Some filesystems may not allow certain ASCII special characters in filenames.
            In such cases, we detect this and report it, then proceed with the Unicode
            replacement character anyway since that's our goal.
        """
        self.debug_print("Starting to process files in directory: {}".format(self.directory), level='normal')
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
    if args.debug:
        FileRenamer._debug = True
        os.environ['RENAMER_DEBUG'] = 'detail'  # Enable detailed debug output

    renamer = FileRenamer(args.directory, dry_run=args.dry_run)
    changes = renamer.process_files()

    if args.dry_run:
        print("\nProposed changes (dry run):")
    else:
        print("\nExecuted changes: (showing special character replacements in cyan)")

    # Track if any files were changed
    any_changes = False
    for old, new in changes:
        if old == new:
            print(f"{old}\n  ->  unchanged\n")
        else:
            any_changes = True
            colored_parts = []
            for c in new:
                if any(c == repl for repl in FileRenamer.CHAR_REPLACEMENTS.values()):
                    colored_parts.append(FileRenamer.colorize(c))
                else:
                    colored_parts.append(c)
            colored_new = ''.join(colored_parts)
            print(f"{old}\n  -> {colored_new}\n")

    if not any_changes:
        print("\nNo files need to be renamed.")
        return

    if not args.dry_run:
        confirm = input("\nApply these changes? [y/N] ")
        if confirm.lower() != 'y':
            print("No changes made.")
            return  # This prevents further processing

        # Display folder information before renaming
        print(f"Renaming files in folder: {args.directory}")

        # Actually rename the files
        for old, new in changes:
            if not args.dry_run:
                try:
                    # Use full paths by joining the directory with the filenames
                    old_path = os.path.join(args.directory, old)
                    new_path = os.path.join(args.directory, new)
                    # print(f"Renaming '{old_path}' to '{new_path}'")
                    os.rename(old_path, new_path)
                except OSError as e:
                    if e.errno in (errno.EINVAL, errno.EACCES):
                        print(f"Note: Filesystem does not allow rename on filename with special characters.")
                        print(f"  Original name: '{old}'")
                        print(f"  Attempted new name: '{new}'")
                        print(f"  Error: {e}")
                        print("This is expected on some filesystems. \nAttempting making new file and copying contents")
                        # Create a new file with the Unicode replacement directly
                        try:
                            # First try to create the new file
                            Path(new).write_bytes(Path(old).read_bytes())
                            # If successful, remove the old file
                            os.unlink(old)
                        except OSError as e2:
                            print(f"Error: Could not create new file '{new}': {e2}")
                            raise
                    else:
                        raise

# Validate replacements when module is loaded
FileRenamer.validate_replacements()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
