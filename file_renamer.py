#!/usr/bin/env python3
"""
File Renamer - Improve filenames with capitalization and punctuation rules for titles.
Replace special characters (including characters illegal in NTFS) with similar Unicode characters.
Maintain contractions, possessives, and quoted phrases
Handle common abbreviations, including dates, professional degrees, military ranks, and scientific units
Specify your own abbreviations and acronyms, in a simple text file

Ideal for small business professionals seeking efficient file renaming.

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
Version: 0.9.0 (Beta)
"""
__version__ = "0.9.0"  # Beta - Close to first stable release

import os
import re
import sys
import errno
import traceback
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path
import unicodedata
import logging
import argparse
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

    # Can't put apostrophe in CHAR_REPLACEMENTS, since might replace with Single Right Quote or with Full Width Quotation Mark or Modifier Letter Apostrophe
    # Unicode characters for quote handling
    MODIFIER_LETTER_APOSTROPHE = '\u02BC'  # (looks better for contractions)
    LEFT_SINGLE_QUOTE = '\u2018'       # Left single quote (preserve originals)
    RIGHT_SINGLE_QUOTE = '\u2019'      # Right single quote (looks better for ending a quotation or phrase)
    ASCII_APOSTROPHE = "'"             # ASCII apostrophe (will be converted)
    APOSTROPHE_REPLACEMENT = MODIFIER_LETTER_APOSTROPHE  # Or ASCII_APOSTROPHE if no replacement desired

    QUOTE_LIKE_CHARS = {
        ASCII_APOSTROPHE,              # Will be converted based on context
        LEFT_SINGLE_QUOTE,             # Will be preserved
        RIGHT_SINGLE_QUOTE,            # Will be preserved if from original text
        APOSTROPHE_REPLACEMENT,        # Used for contractions/possessives
    }

    # All forms of slashes to be replaced with full width solidus
    FULLWIDTH_SOLIDUS_OPERATOR = '\uFF0F'
    SLASHES = {
        '\\',           # ASCII backslash
        '/',           # ASCII forward slash
        '\u2044',      # FRACTION SLASH
        '\u2215',      # DIVISION SLASH
        '\u29F5',  # Better spacing than DIVISION_SLASH
    }
    SLASH_REPLACEMENT = FULLWIDTH_SOLIDUS_OPERATOR  # will replace all forward slashes, and ASCII backslash, with Full Width Solidus Operator

    # Date format separators to preserve in date patterns
    DATE_SEPARATORS = {
        '.',           # period
        '-',           # hyphen
        SLASH_REPLACEMENT,  # for any slash in original
    }

    # Characters to collapse when repeated (not illegal, but often repeated for emphasis)
    # Format: 'character': (min_repeats, replacement)
    # If replacement is None, collapse to a single instance of the original character
    CHARS_TO_COLLAPSE = {
        '-': (2, '—'),           # 2+ dashes become em dash (common typographic convention)
        '_': (2, None),          # 2+ underscores collapse to single underscore
        '=': (2, None),          # 2+ equals signs collapse to single equals
        '+': (2, None),          # 2+ plus signs collapse to single plus
        '#': (2, None),          # 2+ hash signs collapse to single hash
        '*': (2, None),          # 2+ asterisks collapse to single asterisk
        '~': (2, None),          # 2+ tildes collapse to single tilde
        '!': (2, None),          # 2+ exclamation marks collapse to single exclamation
    }

    # Character substitution mappings
    CHAR_REPLACEMENTS = {
        '"': '\uFF02',   # ASCII double quote replaced with Full-Width Quotation Mark
        '`': '\uFF02',   # Backtick replaced with Full-Width Quotation Mark
        # don't replace Single Right Quote, since might use Single Right Quote or replace with Full Width Quotation Mark
        '\u201C': '\uFF02',   # Left double quote replaced with Full-Width Quotation Mark
        '\u201D': '\uFF02',   # Right double quote replaced with Full-Width Quotation Mark
        '\u201E': '\uFF02',   # Double Low-9 Quotation Mark replaced with Full Width Quotation Mark
        '\u201F': '\uFF02',   # Double High-9 Quotation Mark replaced with Full Width Quotation Mark
        '\u2039': '\uFF02',   # Single Left-Pointing Angle Quotation Mark replaced with Full Width Quotation Mark
        '\u203A': '\uFF02',   # Single Right-Pointing Angle Quotation Mark replaced with Full Width Quotation Mark

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
        # Ampersand replacements - all to Full-Width Ampersand
        '&': '＆',   # ASCII ampersand replaced with Full-Width Ampersand
        # Additional ampersand-like characters
        '⅋': '＆',  # Turned Ampersand replaced with Full-Width Ampersand
        '⁐': '＆',  # Close Up replaced with Full-Width Ampersand
        '﹠': '＆',  # Small Ampersand replaced with Full-Width Ampersand
        '﹢': '＆',  # Small And replaced with Full-Width Ampersand
        '$': '＄',  # Full Width Dollar Sign
        '...': '…',  # Replace three or more periods with ellipsis character
    }

    # Add slash replacements after main mappings
    for slash in SLASHES:
        CHAR_REPLACEMENTS[slash] = SLASH_REPLACEMENT

    # Shorthand for readability
    R = CHAR_REPLACEMENTS

    # List of terms with specific capitalization and punctuation to preserve exactly
    # These built-in terms can be supplemented with user-defined terms from settings.ini
    PRESERVED_TERMS = [
        # TV/Movie ratings (okay if some do not need special handling)
        'TV-MA', 'TV-PG', 'TV-Y', 'TV-14', 'PG-13', 'NC-17',
        # Movie Title with colon (a character forbidden in NTFS filenames) and double quotes (a character not forbidden in NTFS filenames but we're replacing with Full Width Quotation Mark)
        '"Star Trek: The Next Generation"'
    ]

    # User settings loaded from settings.ini
    USER_ABBREVIATIONS = set()
    USER_PRESERVED_TERMS = set()

    # Common abbreviations to preserve case
    ABBREVIATIONS = {
        # Academic Degrees (use periods just for testing the clean_abbreviation function)
        'B.A', 'B.S', 'M.A', 'M.B.A', 'M.D', 'M.S', 'Ph.D', 'J.D', 'BSc', 'MSc', 'MPhil',

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
        'USMC', 'USN', 'USAF',  # Service branches
        'WW1', 'WW2',

        # Movie/TV Ratings (no periods)
        'TV', 'G', 'PG', 'PG-13', 'R', 'NC-17', 'TV-14', 'TV-MA', 'TV-PG', 'TV-Y',
        # not handled properly, gets broken up at hyphen into parts

        # TV Networks
        'ABC', 'BBC', 'CBS', 'CNN', 'CW', 'HBO', 'NBC', 'PBS', 'CNBC', 'MSNBC',
        'TBS', 'TNT', 'USA', 'ESPN', 'MTV', 'TLC', 'AMC', 'O\'Donnell', 'O\'Reilly',

        # US States (excluding those that conflict with common words, see KEEP_CAPITALIZED_IF_ALLCAPS)
        'AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'FL',
        'GA', 'ID', 'IL', 'KS', 'KY', 'MD', 'MI',
        'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV',
        'NY', 'OK', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT',
        'VA', 'VT', 'WI', 'WV', 'WY',
        'NYC', 'SF',
        # 'DE' Delaware conflicts with common Spanish word 'de'
        # 'HI', 'LA', 'MA', 'ME', 'OH', 'OR', 'PA' conflict with English words

        # Canadian Provinces (excluding ON, a lowercase word)
        'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'PE', 'QC', 'SK', 'YT',

        # Countries and Regions
        'UK', 'USA', 'EU', 'UAE', 'USSR',  # 'US' moved to KEEP_CAPITALIZED_IF_ALLCAPS

        # Time/Date (AM and PM handled special case)
        'EST', 'EDT', 'CST', 'CDT', 'MST', 'MDT', 'PST', 'PDT', 'GMT', 'UTC',

        # Government/Organizations
        'CIA', 'DEA', 'DHS', 'DMV', 'DOD', 'DOJ', 'FBI', 'FCC',
        'FDA', 'FEMA', 'FTC', 'IRS', 'NASA', 'NOAA', 'NSA', 'TSA', 'USDA',
        'EPA', 'SSA', 'UN', 'USPS',
        # not 'SEC', 'sec' is a numbered unit,
        # 'ICE' in KEEP_CAPITALIZED_IF_ALLCAPS

        # Mexican States (official abbreviations)
        'AGS',  # Aguascalientes
        'BC',   # Baja California
        'BCS',  # Baja California Sur
        'CAMP', # Campeche
        'CHIS', # Chiapas
        'CHIH', # Chihuahua
        'COAH', # Coahuila
        # 'COL',  # Colima also Col Colonel
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

        # Time/Date
        'UTC', 'UTC+', 'UTC-', 'EST', 'EDT', 'CST', 'CDT', 'MST', 'MDT', 'PST', 'PDT', 'GMT',
        'AKST', 'AKDT', 'HST', 'HDT', 'AST', 'ADT', 'NST', 'NDT',
        'BST', 'BDT', 'CST', 'CDT', 'EST', 'EDT', 'GMT', 'HAT', 'HNT', 'IST', 'JST',
        'KST', 'MDT', 'MESZ', 'MET', 'MST', 'MDT', 'PDT', 'PST', 'SST', 'UTC', 'WET',
        'WST', 'YST', 'YST', 'ZST',

        # Media Formats
        # Images
        'JPEG', 'JPG', 'PNG', 'GIF', 'BMP', 'TIF', 'TIFF', 'SVG', 'WebP',
        # Video
        'AVI', 'MP4', 'MKV', 'MOV', 'WMV', 'FLV', 'WebM', 'M4V', 'VOB',
        # Audio
        'MP3', 'WAV', 'AAC', 'OGG', 'FLAC', 'WMA', 'M4A',
        # Quality/Standards
        '4K', '8K', 'HDR', 'DTS', 'IMAX', 'UHD',

        # Business/Organizations
        'CEO', 'CFO', 'CIO', 'COO', 'CTO', 'LLC', 'LLP',
        'VP',
        # Note: removed VS, conflicts with 'vs' versus
        # removed HR (human resources) since conflicts with hr (hour)

        # Other Common
        'ID', 'OK', 'PC', 'PIN', 'PO', 'ps', 'RIP', 'UFO', 'VIP', 'ZIP',
        'DIY', 'FAQ', 'ASAP', 'IMAX', 'AGT', 'BGT',

        # Software/Platforms
        'WordPress', 'SEO', 'iOS', 'macOS', 'SQL', 'NoSQL', 'MySQL', 'NoSQL', 'PostgreSQL', 'JavaScript', 'TypeScript', 'ChatGPT', 'GPT',

        # Apple products and special case words (merged from SPECIAL_CASE_WORDS)
        'iPad', 'iPhone', 'iPod', 'iTunes', 'iMac',
        'macOS', 'iOS',  # Operating systems
    }

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
            lambda m: f"{m.group(1)}{R['/']}", s),  # 30/hr -> 30⧸hr, /hr -> ⧸hr
        r'\b\d*\s*/\s*h\b': lambda s: re.sub(r'(\d*)\s*/\s*h',
            lambda m: f"{m.group(1)}{R['/']}", s),   # 30/h -> 30⧸h, /h -> ⧸h

        # Minutes
        r'\b\d*\s*min\b': lambda s: f"{s}",  # 15min -> 15min, min -> min
        r'\b\d*\s*/\s*min\b': lambda s: re.sub(r'(\d*)\s*/\s*min',
            lambda m: f"{m.group(1)}{R['/']}", s),  # 30/min -> 30⧸min, /min -> ⧸min

        # Seconds
        r'\b\d*\s*sec\b': lambda s: f"{s}",  # 30sec -> 30sec, sec -> sec
        r'\b\d*\s*s\b': lambda s: f"{s}",    # 30s -> 30s, s -> s
        r'\b\d*\s*/\s*sec\b': lambda s: re.sub(r'(\d*)\s*/\s*sec',
            lambda m: f"{m.group(1)}{R['/']}", s),  # 30/sec -> 30⧸sec, /sec -> ⧸sec
        r'\b\d*\s*/\s*s\b': lambda s: re.sub(r'(\d*)\s*/\s*s',
            lambda m: f"{m.group(1)}{R['/']}", s),    # 30/s -> 30⧸s, /s -> ⧸s

        # Days, Weeks, Months, Years
        r'\b\d*\s*d\b': lambda s: f"{s}",    # 30d -> 30d, d -> d
        r'\b\d*\s*wk\b': lambda s: f"{s}",  # 52wk -> 52wk, wk -> wk
        r'\b\d*\s*mo\b': lambda s: f"{s}",  # 12mo -> 12mo, mo -> mo
        r'\b\d*\s*yr\b': lambda s: f"{s}",  # 10yr -> 10yr, yr -> yr

        r'\b\d*\s*/\s*d\b': lambda s: re.sub(r'(\d*)\s*/\s*d',
            lambda m: f"{m.group(1)}{R['/']}", s),    # 30/d -> 30⧸d, /d -> ⧸d
        r'\b\d*\s*/\s*wk\b': lambda s: re.sub(r'(\d*)\s*/\s*wk',
            lambda m: f"{m.group(1)}{R['/']}", s),  # 52/wk -> 52⧸wk, /wk -> ⧸wk
        r'\b\d*\s*/\s*mo\b': lambda s: re.sub(r'(\d*)\s*/\s*mo',
            lambda m: f"{m.group(1)}{R['/']}", s),  # 12/mo -> 12⧸mo, /mo -> ⧸mo
        r'\b\d*\s*/\s*yr\b': lambda s: re.sub(r'(\d*)\s*/\s*yr',
            lambda m: f"{m.group(1)}{R['/']}", s),  # 10/yr -> 10⧸yr, /yr -> ⧸yr
    }

    # Month names and abbreviations with proper capitalization
    # In __init__, MONTH_FORMATS values get added to:
    # 1. ABBREVIATIONS - to handle dates with separators like 25-Jan-12
    # 2. UNIT_PATTERNS - to handle dates without separators like 2025jan12
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
        'as', 'if', 'how', 'than', 'v', 'vs',   # v/vs for versus

        # Common Words in Media Titles
        'part', 'vol', 'feat', 'ft', 'remix',

        # Be Verbs (when not first/last)
        'am', 'are', 'is', 'was', 'were', 'be', 'been',

        # Spanish
        'a', 'con', 'de', 'del', 'el', 'la', 'las', 'lo', 'los',
        'para', 'por', 'que', 'su', 'una', 'unas', 'unos', 'y'
    }

    # Dictionary for words that should only be kept capitalized if they appear in all caps
    # Otherwise they should be converted to lowercase
    KEEP_CAPITALIZED_IF_ALLCAPS = {
        # Alphabetically sorted by key
        'AS': 'as',   # American Samoa - 'as' conjunction/adverb
        'BY': 'by',   # Belarus - 'by' preposition
        'CAMP': 'camp', # Campeche (Mexican state) - 'camp' English word
        'COL': 'Col',  # Colima - 'Col' Colonel
        'DE': 'de',  # Delaware - 'de' Spanish (of/from)
        'DO': 'do',   # Dominican Republic - 'do' verb
        'DOE': 'doe', # Department of Energy - 'doe' female deer
        'FDR': 'FDR', # Franklin D. Roosevelt - 'FDR' initials
        'HE': 'he',   # Hesse, Germany - 'he' pronoun
        'HI': 'hi',  # Hawaii - 'hi' English exclamation
        'HR': 'hr',   # Human Resources - 'hr' hour
        'ICE': 'ice', # Immigration and Customs Enforcement - 'ice' frozen water
        'IN': 'in',  # Indiana - 'in' English preposition
        'IS': 'is',   # Information Systems - 'is' verb
        'IT': 'it',   # Information Technology - 'it' pronoun
        'JFK': 'JFK', # John F. Kennedy - 'JFK' initials
        'LA': 'la',  # Louisiana - 'la' English exclamation
        'MA': 'ma',  # Massachusetts - 'ma' mother
        'ME': 'me',  # Maine - 'me' English pronoun
        'MS': 'Ms',   # Mississippi - 'Ms' title
        'NAY': 'nay', # Nayarit (Mexican state) - 'nay' English word
        'NO': 'no',   # Norway - 'no' negative
        'NOR': 'nor', # Norway - 'nor' conjunction
        'OH': 'oh',  # Ohio - 'oh' English exclamation
        'ON': 'on',  # Ontario - 'on' English preposition
        'OR': 'or',  # Oregon - 'or' English conjunction
        'PA': 'pa',  # Pennsylvania - 'pa' Spanish/father in several languages
        'PC': 'pc',   # Personal Computer - 'pc' piece
        'PST': 'pst', # Pacific Standard Time - 'pst' exclamation
        'RAM': 'ram', # Random Access Memory - 'ram' male sheep
        # NOT 'SEC': 'sec', # Securities and Exchange Commission - 'sec' second
        'SIN': 'sin',  # Sinaloa - 'sin' English word
        'SO': 'so',   # Somalia - 'so' adverb
        'SON': 'son',  # Sonora - 'son' English word
        'STEM': 'stem',  # Science, Technology, Engineering, Math - 'stem' plant part
        'TAB': 'tab',  # Tabasco - 'tab' word
        'TO': 'to',   # Toronto - 'to' preposition

        'UP': 'up',   # Uttar Pradesh, India - 'up' preposition
        'US': 'us',  # United States - 'us' English word
        'VER': 'ver', # Veracruz (Mexican state) - 'ver' version abbreviation
        'WA': 'wa',  # Washington - 'wa' Spanish dialect word
    }

    # All opening bracket characters (ASCII and replacements)
    OPENING_BRACKETS = {
        # ASCII opening brackets
        '(', '[', '{', '<',
        # Replacement opening brackets
        R['<'],   # Left Black Lenticular Bracket
        R['<<'],  # Left Double Angle Bracket
        R['[['],  # Mathematical Left White Square Bracket
        R['{{'],  # Left White Curly Bracket
        # Additional Unicode opening brackets
        '（',     # Full Width Left Parenthesis
        '［',     # Full Width Left Square Bracket
        '｛',     # Full Width Left Curly Bracket
        '⦅',     # Left White Parenthesis
        '〔',     # Left Tortoise Shell Bracket
        '〈',     # Left Angle Bracket
        '「',     # Left Corner Bracket
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
        # Additional Unicode closing brackets
        '）',     # Full Width Right Parenthesis
        '］',     # Full Width Right Square Bracket
        '｝',     # Full Width Right Curly Bracket
        '⦆',     # Right White Parenthesis
        '〕',     # Right Tortoise Shell Bracket
        '〉',     # Right Angle Bracket
        '」',     # Right Corner Bracket
    }

    # Characters that trigger capitalization of the next word
    CAPITALIZATION_TRIGGERS = {
        '.',  # Period
        '-',  # Dash/Hyphen
        R['...'],  # Ellipsis
        R[':'],    # Colon
        R['|'],    # Pipe/Vertical bar
        '¿',   # Spanish inverted question mark
        '¡',   # Spanish inverted exclamation mark
        *OPENING_BRACKETS  # All opening brackets
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
        '.', ' ', ',', ';', '-', '+', "'", '\u02bc',  # Standard word boundaries, including ASCII Apostrophe and Modifier Letter Apostrophe
        R['<'], R['>'],                  # Angle brackets
        R['...'],                        # Ellipsis
        '(', '[', '{', '<',              # ASCII opening brackets
        ')', ']', '}', '>',              # ASCII closing brackets
        R['<'], R['<<'], R['[['], R['{{'],  # Replacement opening brackets
        R['>'], R['>>'], R[']]'], R['}}'],  # Replacement closing brackets
        '¿', '¡',                    # Spanish inverted punctuation marks
    }

    # File extensions where we want to preserve the original case of the base name
    # Only includes extensions that might be included/imported/required by code
    # Should be all lowercase, no periods
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

    # Common abbreviations to preserve
    @classmethod
    def _clean_abbreviation(cls, abbr: str) -> str:
        """
        Clean abbreviations for filename use:
        1. For known abbreviations and units in our list, remove all periods and preserve case (we want PhD not Ph.D.)
        2. Remove leading and trailing whitespace
        """
        # Remove leading and trailing whitespace
        cleaned = abbr.strip()

        # First remove periods for comparison with our abbreviations list
        abbr_without_periods = re.sub(r'\.', '', cleaned)

        # Check if it's in our known abbreviations list or standalone units list (case-insensitive)
        if (abbr_without_periods.upper() in [a.upper() for a in cls.ABBREVIATIONS] or
            abbr_without_periods.upper() in [u.upper() for u in cls.STANDALONE_UNITS]):
            return abbr_without_periods  # Return version without periods
        else:
            # For regular words, just preserve them as is (periods will be handled elsewhere)
            return cleaned

    def _clean_common_abbreviation_patterns(self, text):
        """
        Detect and clean common abbreviation patterns with periods.
        Examples: "M.D.", "Ph.D.", "Lt.Col."

        This preprocessing step handles abbreviations with periods before
        the text is split into tokens for further processing.
        """

        # Patterns for letter-based abbreviations with periods
        # We'll use multiple patterns to handle different cases

        # Pattern 1: Multi-letter abbreviations with periods (M.D., Ph.D., B.Sc., M.Phil.)
        pattern1 = r'(?:^|(?<=\W))([A-Za-z]+(?:\.[A-Za-z]+)+\.?)(?=\W|$)'

        # Pattern 2: Abbreviations with periods and internal spaces (e.g. 'Lt. Col.', 'Prof. Dr.')
        # Process this BEFORE pattern 3 to catch multi-part abbreviations
        pattern2 = r'(?:^|(?<=\W))([A-Za-z][A-Za-z]*\. [A-Za-z][A-Za-z0-9]*\.)(?=\W|$)'

        # Pattern 3: Common abbreviations with trailing period (Dr., Mr., Ms., etc.)
        # Only match short words (1-3 letters) to avoid matching regular words with periods
        pattern3 = r'(?:^|(?<=\W))([A-Za-z]{1,3}\.)(?=\s|$)'

        # Initialize result with the original text
        result = text

        # Process each pattern in sequence
        for i, pattern in enumerate([pattern1, pattern2, pattern3]):
            # Find all matches for this pattern
            pattern_matches = list(re.finditer(pattern, result, flags=re.IGNORECASE))

            if pattern_matches:
                self.debug_print(f"[ABBREV] Pattern {i+1} matches ({len(pattern_matches)}):", level='verbose')

                # Process each match
                for match in pattern_matches:
                    match_text = match.group(1)
                    # self.debug_print(f"  Match: {match_text!r} at position {match.start()}-{match.end()}", level='verbose')

                    # Skip if match is None (shouldn't happen, but just to be safe)
                    if match is None:
                        self.debug_print("[ABBREV] WARNING: Match is None before substitution!", level='verbose')
                        continue

                    # Clean the abbreviation
                    cleaned_abbr = self._clean_abbreviation(match_text)
                    self.debug_print(f"[ABBREV] Original abbreviation: {match_text!r}, cleaned: {cleaned_abbr!r}", level='verbose')

                    # Skip if cleaning returned None
                    if cleaned_abbr is None:
                        self.debug_print("[ABBREV] WARNING: cleaned_abbr is None before substitution!", level='verbose')
                        continue

                    # Substitute the cleaned abbreviation in the text
                    try:
                        # Use re.escape to handle special regex characters in the match text
                        escaped_pattern = re.escape(match_text)
                        result, num_subs = re.subn(escaped_pattern, cleaned_abbr, result, count=1, flags=re.IGNORECASE)
                    except Exception as e:
                        self.debug_print(f"[ABBREV] Error in regex substitution: {e}", level='verbose')
                        self.debug_print(f"[ABBREV] match: {match!r}", level='verbose')
                        self.debug_print(f"[ABBREV] match_text: {match_text!r}", level='verbose')
                        self.debug_print(f"[ABBREV] cleaned_abbr: {cleaned_abbr!r}", level='verbose')
            # else:
                # self.debug_print(f"[ABBREV] Pattern {i+1}: No matches found", level='verbose')

        # Show if any changes were made
        if result != text:
            self.debug_print(f"[ABBREV] Changed: {text!r} -> {result!r}", level='verbose')
        # else:
            # self.debug_print(f"[ABBREV] No changes made to text", level='verbose')

        self.debug_print(f"[ABBREV] Preprocessing complete, result: {result!r}", level='verbose')
        return result

    def _replace_special_chars(self, text):
        """
        Replace special characters with NTFS-compatible alternatives.

        Args:
            text: Text to process

        Returns:
            Text with special characters replaced
        """
        # Function to colorize replacement chars for debug output
        def colorize(char):
            return f"{Fore.CYAN}{char}{Style.RESET_ALL}"

        # Handle fractions first (digit/digit with optional spaces)
        text = re.sub(r'(\d)\s*/\s*(\d)', fr'\1{self.R["/"]}\2', text)

        # Handle multi-char sequences (like ellipsis, brackets)
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if len(original_char) > 1:  # Multi-char replacement
                if original_char in text:
                    self.debug_print(f"  Replace: '{original_char}' → '{colorize(replacement_char)}'", level='detail')
                    if original_char == '...':
                        # Handle ellipsis specially to match 3 or more dots
                        text = re.sub(r'\.{3,}', replacement_char, text)
                    else:
                        text = text.replace(original_char, replacement_char)

        # Handle single-char replacements
        for original_char, replacement_char in self.CHAR_REPLACEMENTS.items():
            if len(original_char) == 1:  # Single-char replacements
                if original_char in text:
                    self.debug_print(f"  Replace: '{original_char}' → '{colorize(replacement_char)}'", level='detail')
                    text = re.sub(f'{re.escape(original_char)}+', replacement_char, text)

        # Handle repeated characters that aren't illegal but should be collapsed
        text = self._collapse_repeated_characters(text)

        return text

    def _collapse_repeated_characters(self, text):
        """
        Replace sequences of repeated characters with appropriate replacements.

        Handles:
        - Repeated dashes (replaced with em dash)
        - Repeated underscores (collapsed to single underscore)
        - Other repeated characters defined in CHARS_TO_COLLAPSE
        - Repeated emojis (collapsed to single emoji)

        Args:
            text: Text to process

        Returns:
            Modified text with repeated characters handled
        """
        # Handle characters with specific replacements
        for char, (min_repeats, replacement) in self.CHARS_TO_COLLAPSE.items():
            pattern = f'{re.escape(char)}{{{min_repeats},}}'
            if replacement is None:
                # Collapse to a single instance of the original character
                if re.search(pattern, text):
                    self.debug_print(f"  Collapse: '{char * min_repeats}+' → '{char}'", level='detail')
                    text = re.sub(pattern, char, text)
            else:
                # Replace with the specified replacement
                if re.search(pattern, text):
                    self.debug_print(f"  Replace: '{char * min_repeats}+' → '{self.colorize(replacement)}'", level='detail')
                    text = re.sub(pattern, replacement, text)

        # Handle emojis (more complex pattern)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "]"
        )

        # Find all emoji sequences in the text
        for match in re.finditer(r'((' + emoji_pattern.pattern + r')\2+)', text):
            full_match = match.group(1)
            single_emoji = match.group(2)
            if full_match != single_emoji:  # Only replace if there are actually repeats
                self.debug_print(f"  Collapse emoji: '{full_match}' → '{single_emoji}'", level='detail')
                text = text.replace(full_match, single_emoji)

        return text

    def _preserve_special_terms(self, text):
        """
        Preserve terms with specific capitalization and punctuation by replacing them with
        temporary markers before text splitting. This ensures terms like TV-MA, AT&T, etc.
        are treated as single tokens rather than being split at punctuation characters.

        The preserved terms are first processed with the same character replacements
        as the filename, so users can specify terms with original characters.

        Args:
            text: Text to process (already processed with character replacements)

        Returns:
            Text with preserved terms replaced by markers
        """
        # Create a unique marker for each term
        self._preserved_term_markers = {}
        self._preserved_term_originals = {}
        self._normalized_terms = {}
        self._cleaned_terms = {}  # New dictionary for cleaned terms

        # Create a regex pattern for characters to remove during normalization
        # Based on WORD_BOUNDARY_CHARS
        chars_to_escape = [re.escape(char) for char in self.WORD_BOUNDARY_CHARS]
        self._normalization_pattern = re.compile(f"[{''.join(chars_to_escape)}]")

        # Process each preserved term with character replacements
        for i, term in enumerate(self.PRESERVED_TERMS):
            # Validate the term
            if not self._validate_preserved_term(term):
                self.debug_print(f"[PRESERVED] Warning: Invalid term skipped: {term!r}", level='normal')
                continue

            # Clean the term using the same replacement rules as filenames
            cleaned_term = self._replace_special_chars(term)

            # Create a marker without trailing space
            marker = f"__PRESERVED_TERM_{i}__"
            self._preserved_term_markers[cleaned_term] = marker
            self._preserved_term_originals[marker] = cleaned_term  # Store cleaned version

            # Create normalized version (lowercase, no spaces or punctuation)
            normalized = re.sub(r'[\s\-.,;:"&!?()]', '', cleaned_term.lower())
            self._normalized_terms[normalized] = (cleaned_term, marker)

            # Store mapping between original and cleaned terms
            self._cleaned_terms[term] = cleaned_term

            # Debug: Show normalized versions
            self.debug_print(f"[PRESERVED] Original: {term!r} → Cleaned: {cleaned_term!r} → Normalized: {normalized!r}", level='detail')

        # Debug: Show the complete dictionaries
        self.debug_print("\n[PRESERVED] _preserved_term_markers dictionary:", level='detail')
        for term, marker in self._preserved_term_markers.items():
            self.debug_print(f"  {term!r} → {marker!r}", level='detail')

        self.debug_print("\n[PRESERVED] _preserved_term_originals dictionary:", level='detail')
        for marker, term in self._preserved_term_originals.items():
            self.debug_print(f"  {marker!r} → {term!r}", level='detail')

        self.debug_print("\n[PRESERVED] _normalized_terms dictionary:", level='detail')
        for norm, (term, marker) in self._normalized_terms.items():
            self.debug_print(f"  {norm!r} → ({term!r}, {marker!r})", level='detail')

        self.debug_print("\n[PRESERVED] _cleaned_terms dictionary:", level='detail')
        for orig, cleaned in self._cleaned_terms.items():
            self.debug_print(f"  {orig!r} → {cleaned!r}", level='detail')

        # First try exact matches (case-insensitive)
        for term in self._cleaned_terms.values():  # Use cleaned terms for matching
            # Replace the term with its marker
            new_text = re.sub(rf'\b{re.escape(term)}\b', self._preserved_term_markers[term], text, flags=re.IGNORECASE)
            if new_text != text:
                self.debug_print(f"[PRESERVED] Exact match: {term!r} in text", level='verbose')
                text = new_text

        # Then try flexible matching for each preserved term
        # This handles variations in spacing, punctuation, and capitalization
        for orig_term, term in self._cleaned_terms.items():
            # Skip single-word terms as they're already handled by exact matching
            # Check for any word boundary characters using WORD_BOUNDARY_CHARS
            if not any(char in term for char in self.WORD_BOUNDARY_CHARS):
                continue

            # Get the normalized form of the term (lowercase, no spaces or punctuation)
            # Use the consistent normalization pattern based on WORD_BOUNDARY_CHARS
            normalized_term = self._normalization_pattern.sub('', term.lower())

            # Create a pattern that allows flexible spacing and punctuation between words
            # Split the term into words using WORD_BOUNDARY_CHARS as delimiters
            # Create a regex pattern for splitting based on WORD_BOUNDARY_CHARS
            split_pattern = f"[{''.join(re.escape(char) for char in self.WORD_BOUNDARY_CHARS)}]+"
            words = re.split(split_pattern, term)
            # Filter out empty strings from the split result
            words = [word for word in words if word]

            if len(words) > 1:
                # For multi-word terms, create a pattern that allows flexible spacing/punctuation
                # This matches each word with optional punctuation/spacing between them
                pattern = r''
                for i, word in enumerate(words):
                    if i > 0:
                        # Allow any combination of spaces and punctuation between words
                        pattern += r'[\s\-.,;:"&!?()]*'
                    pattern += re.escape(word)

                # Allow optional trailing punctuation
                pattern += r'[\s\-.,;:"&!?()]*'

                # Find all matches of this pattern
                matches = re.findall(pattern, text, flags=re.IGNORECASE)

                for match in matches:
                    # Normalize the match for comparison using the consistent pattern
                    normalized_match = self._normalization_pattern.sub('', match.lower())

                    # Check if the normalized match is exactly the normalized term
                    if normalized_match == normalized_term:
                        # Replace with the preserved term marker
                        text = text.replace(match, self._preserved_term_markers[term])
                        self.debug_print(f"[PRESERVED] Flexible match: {match!r} → {term!r}", level='verbose')

        # General approach for all terms - check for normalized matches in word groups
        # Use a pattern that captures word groups more effectively
        # This pattern handles words at the beginning/end of text and with special characters
        # Create a pattern based on WORD_BOUNDARY_CHARS that captures word groups
        boundary_chars = ''.join(re.escape(char) for char in self.WORD_BOUNDARY_CHARS)
        word_pattern = f"(?:^|[{boundary_chars}])([^{boundary_chars}]+)(?:[{boundary_chars}]|$)"
        words = re.findall(word_pattern, text)
        self.debug_print(f"[PRESERVED] Found {len(words)} word groups to check", level='detail')

        for word_group in words:
            # Normalize the word group using the consistent normalization pattern
            normalized_group = self._normalization_pattern.sub('', word_group.lower())
            self.debug_print(f"[PRESERVED] Checking: {word_group!r} → Normalized: {normalized_group!r}", level='detail')

            # Check if this normalized group exactly matches any of our terms
            if normalized_group in self._normalized_terms and len(normalized_group) > 2:  # Minimum length check
                original_term, marker = self._normalized_terms[normalized_group]
                # Replace this specific instance with the marker
                text = text.replace(word_group, marker, 1)
                self.debug_print(f"[PRESERVED] Normalized match: {word_group!r} → {original_term!r}", level='verbose')

        return text

    def _validate_preserved_term(self, term):
        """
        Validate a preserved term to ensure it meets requirements.

        Args:
            term: The term to validate

        Returns:
            bool: True if the term is valid, False otherwise
        """
        # Length validation
        if len(term) < 2:
            self.debug_print(f"[PRESERVED] Term too short: {term!r}", level='detail')
            return False

        if len(term) > 200:
            self.debug_print(f"[PRESERVED] Term too long: {term!r}", level='detail')
            return False

        # Check for control characters or other problematic characters
        if any(ord(c) < 32 or ord(c) == 127 for c in term):
            self.debug_print(f"[PRESERVED] Term contains control characters: {term!r}", level='detail')
            return False

        # Additional security checks could be added here if needed

        return True

    def _restore_preserved_terms(self, parts):
        """
        Restore preserved terms from their temporary markers after text splitting.
        Handles cases where markers may be adjacent or embedded in other text.

        Args:
            parts: List of parts to process

        Returns:
            List of parts with markers replaced by original preserved terms
        """
        try:
            # self.debug_print(f"\n[RESTORATION] Starting restoration of preserved terms from parts: {parts!r}", level='normal')

            if not hasattr(self, '_preserved_term_originals'):  # Dictionary of preserved terms with their original capitalization
                self.debug_print("[RESTORATION] No preserved terms found", level='normal')
                return parts

            # Get all markers from the dictionary
            markers = list(self._preserved_term_originals.keys())

            # Process each part individually to maintain part structure
            restored_parts = []
            for i, part in enumerate(parts):
                try:
                    # Process this part
                    processed_part = part
                    self.debug_print(f"[RESTORATION] Processing part {i}: {part!r}", level='detail')

                    # Check if this part contains any markers
                    for marker in markers:
                        if marker in processed_part:
                            original = self._preserved_term_originals[marker]
                            # Replace the marker with the original term
                            processed_part = processed_part.replace(marker, original)

                    # Add the processed part to the result
                    restored_parts.append(processed_part)
                except Exception as e:
                    self.debug_print(f"[RESTORATION] Error processing part {i}: {part!r} - {str(e)}", level='error')
                    # Add the original part to maintain structure
                    restored_parts.append(part)

            return restored_parts
        except Exception as e:
            self.debug_print(f"[RESTORATION] Critical error in restoration: {str(e)}", level='error')
            # Return original parts if there's an error
            return parts


    def _clean_date_patterns_with_periods(self, text):
        """
        Detect and clean date patterns with periods.
        Examples: "12.Jan.2025", "Jan.2025", "12.Jan", "2025.Jan", "Jan.12.2025", "2025.12.Jan"

        This preprocessing step handles date patterns with periods before
        the text is split into tokens for further processing.
        """
        # Pattern 1: number.month.number (12.Jan.2025)
        pattern1 = r'\b(\d{1,4})\.([A-Za-z]{3,})\.?(\d{1,4})?\b'
        # Pattern 2: month.number (Jan.2025) or month.number.number (Jan.12.2025)
        pattern2 = r'\b([A-Za-z]{3,})\.?(\d{1,4})(\.\d{1,4})?\b'
        # Pattern 3: number.number.month (2025.12.Jan)
        pattern3 = r'\b(\d{1,4})\.(\d{1,4})\.([A-Za-z]{3,})\b'
        # Pattern 4: month.month.year (Jan.Feb.2025) - for date ranges
        pattern4 = r'\b([A-Za-z]{3,})\.([A-Za-z]{3,})\.?(\d{1,4})?\b'

        def replace_date(match, format_type):
            if format_type == 1:  # number.month.number or number.month
                day_or_year = match.group(1)
                month = match.group(2)
                year_or_day = match.group(3) if match.group(3) else ''

                # Check if month part looks like a month
                month_lower = month.lower()
                if month_lower in self.MONTH_FORMATS:
                    # Use proper case from MONTH_FORMATS
                    proper_month = self.MONTH_FORMATS[month_lower]
                    return f"{day_or_year}{proper_month}{year_or_day}"

            elif format_type == 2:  # month.number or month.number.number
                month = match.group(1)
                number1 = match.group(2)
                number2 = match.group(3)[1:] if match.group(3) else ''

                month_lower = month.lower()
                if month_lower in self.MONTH_FORMATS:
                    proper_month = self.MONTH_FORMATS[month_lower]
                    return f"{proper_month}{number1}{number2}"

            elif format_type == 3:  # number.number.month
                number1 = match.group(1)
                number2 = match.group(2)
                month = match.group(3)

                month_lower = month.lower()
                if month_lower in self.MONTH_FORMATS:
                    proper_month = self.MONTH_FORMATS[month_lower]
                    return f"{number1}{number2}{proper_month}"

            elif format_type == 4:  # month.month.year (date ranges)
                month1 = match.group(1)
                month2 = match.group(2)
                year = match.group(3) if match.group(3) else ''

                month1_lower = month1.lower()
                month2_lower = month2.lower()

                if month1_lower in self.MONTH_FORMATS and month2_lower in self.MONTH_FORMATS:
                    proper_month1 = self.MONTH_FORMATS[month1_lower]
                    proper_month2 = self.MONTH_FORMATS[month2_lower]
                    return f"{proper_month1}{proper_month2}{year}"

            # If not a valid month pattern or format, return unchanged
            return match.group(0)

        # Apply each pattern
        text = re.sub(pattern1, lambda m: replace_date(m, 1), text)
        text = re.sub(pattern2, lambda m: replace_date(m, 2), text)
        text = re.sub(pattern3, lambda m: replace_date(m, 3), text)
        text = re.sub(pattern4, lambda m: replace_date(m, 4), text)

        return text


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

        This method directly cleans each abbreviation by:
        1. Removing leading and trailing whitespace
        2. Removing all periods
        3. Preserving the original case
        """
        cleaned = set()
        for abbr in cls.ABBREVIATIONS:
            # Remove leading and trailing whitespace
            abbr_stripped = abbr.strip()

            # Remove all periods
            cleaned_abbr = re.sub(r'\.', '', abbr_stripped)

            # Debug output
            if abbr != cleaned_abbr:
                cls.debug_print(f"    Cleaned abbreviation: {abbr!r} -> {cleaned_abbr!r}", level='verbose')

            # Add to cleaned set
            cleaned.add(cleaned_abbr)

        # Replace the original set with the cleaned set
        cls.ABBREVIATIONS = cleaned

    def __init__(self, directory: str = '.', dry_run: bool = False, settings_path: Optional[str] = None):
        """
        Initialize the FileRenamer.

        Args:
            directory (str): Directory to process files in
            dry_run (bool): If True, only show what would be renamed without making changes
            settings_path (str, optional): Path to settings file
        """
        # Validate and clean abbreviations first
        self._validate_abbreviations()

        # Load user settings
        self.user_abbreviations, self.user_preserved_terms = self.load_user_settings(settings_path)

        # Store class variables
        self.__class__.USER_ABBREVIATIONS = self.user_abbreviations
        self.__class__.USER_PRESERVED_TERMS = self.user_preserved_terms

        # Add user settings to the existing arrays
        if self.user_abbreviations:
            # self.debug_print(f"Adding {len(self.user_abbreviations)} user abbreviations", level='normal')
            self.ABBREVIATIONS.update(self.user_abbreviations)

        if self.user_preserved_terms:
            # self.debug_print(f"Adding {len(self.user_preserved_terms)} user preserved terms", level='normal')
            self.PRESERVED_TERMS.extend(self.user_preserved_terms)

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
        self.debug_print(f"Entered check_abbreviation_with_context (SINGLE ABBREV PATH), titled_parts={titled_parts!r}")

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
                    # Remove the period
                    titled_parts.pop(-1)
                    self.debug_print(f"    ✓ Found compound abbreviation IN CONTEXT METHOD: {first_abbrev!r} + '.' + {abbr!r} -> {titled_parts[-2]!r}")
                else:
                    # Store as individual abbreviation
                    titled_parts[-len(prev_parts):] = []
                    titled_parts.append(abbr)
                    self.debug_print(f"    ✓ Found abbreviation: {abbr!r} (titled_parts={titled_parts!r})")
                return True
        return False

    def final_quote_processing(self, filename):
        """Process remaining quote-like characters after contraction handling.

        Preserves:
        - Left single quotes
        - Modifier Letter Apostrophes from original text or our processing

        Converts to APOSTROPHE_REPLACEMENT:
        - ASCII apostrophes
        - Any other quote-like characters (except preserved ones)

        Note: Currently all remaining quotes default to APOSTROPHE_REPLACEMENT for
        consistent spacing. More sophisticated left/right quote handling may be added later.
        """
        # Convert ASCII apostrophes to APOSTROPHE_REPLACEMENT
        filename = filename.replace(self.ASCII_APOSTROPHE, self.APOSTROPHE_REPLACEMENT)

        # Convert any other quote-like chars (except preserved ones)
        preserved_chars = {
            self.LEFT_SINGLE_QUOTE,      # Keep original left quotes
            self.MODIFIER_LETTER_APOSTROPHE,  # Keep existing apostrophes (original or from contractions)
        }

        # Any remaining quote-like chars become APOSTROPHE_REPLACEMENT
        for char in self.QUOTE_LIKE_CHARS - preserved_chars:
            filename = filename.replace(char, self.APOSTROPHE_REPLACEMENT)

        return filename

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

        # Initialize titled_parts at the beginning to ensure it's always defined
        titled_parts = [filename]

        # Normalize whitespace in the original filename
        original_filename = filename
        filename = re.sub(r'[\n\r\t\f\v]+', ' ', filename)  # Convert newlines and other whitespace to spaces
        filename = re.sub(r' {2,}', ' ', filename)  # Collapse multiple spaces
        if filename != original_filename:
            self.debug_print(f"Normalized whitespace: {filename!r}", level='normal')

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

        # Get reference to replacements dict for cleaner code
        R = FileRenamer.CHAR_REPLACEMENTS

        # First normalize all whitespace to single spaces
        # Debug processing steps
        self.debug_print(f"Splitting name: {name!r} (extension: {extension!r})", level='detail')

        # Whitespace already normalized at the beginning
        # Just collapse any multiple spaces that might have been introduced during processing
        name = re.sub(r' {2,}', ' ', name)  # Collapse multiple spaces

        try:
            # First replace special characters
            self.debug_print(f"Before replacements: {name!r}", level='normal')
            name = self._replace_special_chars(name)
            self.debug_print(f"After special char replacements: {name!r}", level='normal')

            # Then preserve hyphenated abbreviations and company names
            # This now happens AFTER special character replacements
            # The preserved terms will also have been processed with the same replacements
            name = self._preserve_special_terms(name)
            self.debug_print(f"After preserving special terms: {name!r}", level='normal')
        except Exception as e:
            import traceback
            self.debug_print(f"\nEXCEPTION in clean_filename: {type(e).__name__}: {e}", level='normal')
            self.debug_print("\nDetailed traceback:", level='normal')
            self.debug_print(traceback.format_exc(), level='normal')
            raise

        # Show replaced characters in color in the final output
        colored_parts = []
        for c in name:
            if any(c == repl for repl in R.values()):
                colored_parts.append(FileRenamer.colorize(c))
            else:
                colored_parts.append(c)
        colored_name = ''.join(colored_parts)
        # Don't use !r here as it escapes the color codes
        # self.debug_print(f"After replacements: '{colored_name}'", level='normal')

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
        # For files with extensions such as programming files (.c, .py, .js),
        # preserve the original name case (only basic character replacements and whitespace normalization)
        # Extensions are always lowercased
        is_programming_ext = extension.lower() in self.PRESERVE_CASE_EXTENSIONS
        if is_programming_ext:
            self.debug_print(f"Programming file extension detected: .{extension.lower()}, preserving original name case", level='normal')

        if not is_programming_ext:
            # Apply special pattern cleaning for abbreviations and dates with periods
            # Only process the name part, not the extension
            name = self._clean_common_abbreviation_patterns(name)
            name = self._clean_date_patterns_with_periods(name)

            # Pre-processing: Add spaces between adjacent preserved term markers
            # This ensures they'll be properly split into separate parts
            adjacent_markers_found = False
            while re.search(r'(__PRESERVED_TERM_\d+__)(__PRESERVED_TERM_\d+__)', name):
                if not adjacent_markers_found:
                    adjacent_markers_found = True
                name = re.sub(r'(__PRESERVED_TERM_\d+__)(__PRESERVED_TERM_\d+__)', r'\1 \2', name)

            if adjacent_markers_found:
                self.debug_print(f"[SPLIT] After adding spaces between adjacent markers: {name}", level='normal')

            # Build pattern that matches our word boundaries
            word_boundary_pattern = '([' + ''.join(re.escape(c) for c in self.WORD_BOUNDARY_CHARS) + '])'

            # Use the word boundary pattern for splitting
            split_pattern = word_boundary_pattern
            # self.debug_print(f"Split pattern: {split_pattern}")

            # First do a quick validation of how many parts we might get
            test_parts = re.split(split_pattern, name)
            self.debug_print(f"[SPLIT] Initial parts after splitting: {test_parts[:10]}... (total: {len(test_parts)})", level='normal')
            if len(test_parts) > 200:  # Very generous limit, normal files have 30-90 parts
                self.debug_print(f"Filename too complex: {len(test_parts)} parts exceeds limit of 200")
                return name  # Return original name if too complex

            # Filter out empty parts
            parts = [p for p in test_parts if p != '']

            titled_parts = []
            prev_part = ''
            prev_was_abbrev = False
            prior_abbreviation = None
            prior_date_part = None  # Track date parts like prior_abbreviation

            # Initialize processed_parts to track which parts have been processed
            processed_parts = [None] * len(parts)

            last_real_word = None
            for part in parts:
                if part and len(part) > 1 and not any(c in self.WORD_BOUNDARY_CHARS for c in part):
                    last_real_word = part.lower()

            # Now process each part with error trapping
            try:
                for i, part in enumerate(parts):
                    self.debug_print(f"\nProcessing part {i}: {part!r} (len={len(part)}, has_boundary={[c for c in part if c in self.WORD_BOUNDARY_CHARS]})")

                    # Check if this part contains a preserved term marker
                    if any(marker_prefix in part.upper() for marker_prefix in ["__PRESERVED_TERM_"]):
                        # Find which original term this marker corresponds to
                        original_term = "unknown"
                        for marker, term in self._preserved_term_originals.items():
                            if marker.strip() in part:
                                original_term = term
                                break

                        titled_parts.append(part)
                        self.debug_print(f"  Preserving marker as-is (original: {original_term!r})")
                        prev_part = part
                        continue

                    # Check if this part is in the PRESERVED_TERMS list - if so, add it as-is and skip processing
                    if part in self.PRESERVED_TERMS:
                        titled_parts.append(part)
                        self.debug_print(f"  Preserving term as-is: {part!r}")
                        prev_part = part
                        continue


                    # Convert to title case, handling special cases
                    word = part.lower()  # First convert to lowercase
                    # self.debug_print(f"  After case conversion: {part!r} -> {word!r}")

                    # Process parts in this order:
                    # 1. Abbreviation check (e.g. M.D., Lt.Col)
                    # 2. Contraction/possessive check (e.g. CEO's, we'd)
                    # 3. Unit check (e.g. 5kb, 10s)
                    # important since abbreviations and units can be contractions/possessives ("I'd" vs "M. D." vs "5 d" or "John's" vs "10 s"). Contractions/possessives must be immediately preceded by an apostrophe-like character.

                    self.debug_print(f"⮑ Word: {word!r} (prev_part={prev_part!r}, Found Abbrev: {titled_parts[-1] if titled_parts and titled_parts[-1] in self.ABBREVIATIONS else None}, PriorDatePart: {prior_date_part})")
                    # Check for contractions/possessives first (before unit check)
                    if word in self.CONTRACTIONS and len(titled_parts) >= 2:
                        # Get the full contraction (e.g., 'Didn't' from ['Didn', "'", 't'])
                        base_word = titled_parts[-2] if len(titled_parts) >= 2 else ''
                        if prev_part in self.QUOTE_LIKE_CHARS and not base_word.isspace():
                            # Remove the previous apostrophe and base word
                            titled_parts.pop()  # Remove apostrophe
                            base = titled_parts.pop()  # Remove base word

                            # Add all parts of the contraction back to titled_parts
                            titled_parts.extend([base, self.APOSTROPHE_REPLACEMENT, word])

                            self.debug_print(f"  Contraction check: {word} (base={base})")
                            self.debug_print(f"    ✓ Accepted: {base}{self.APOSTROPHE_REPLACEMENT}{word}")

                            # Keep the full contraction as prev_part (like compound abbreviations)
                            prev_part = f"{base}{self.APOSTROPHE_REPLACEMENT}{word}"
                            continue
                        # self.debug_print(f"    ✗ Rejected: not after word + apostrophe")

                    # Skip empty parts
                    # if not word:
                    #     continue

                    # Handle periods after abbreviations or dates
                    if part == '.' and (prior_abbreviation or prior_date_part):
                        self.debug_print(f"  ⮑ Period handling state:    Current part: {part!r} (prev={prev_part!r})")
                        self.debug_print(f"    Prior state: abbrev={prior_abbreviation}, date={prior_date_part}")
                        self.debug_print(f"    Titled parts so far: {titled_parts}")
                        self.debug_print(f"    Last titled part: {titled_parts[-1]!r}")
                        self.debug_print(f"    Next parts: {parts[i+1:i+3]!r}")
                        self.debug_print(f"    Is month format: {titled_parts[-1] in self.MONTH_FORMATS}")
                        self.debug_print(f"    Skipping period: reason={'month format' if titled_parts[-1] in self.MONTH_FORMATS else 'prior date part' if prior_date_part else 'abbreviation' if prior_abbreviation else 'unknown'}")
                        # If we already added this period, remove it since it follows an abbreviation
                        if titled_parts and titled_parts[-1] == '.':
                            titled_parts.pop()
                            self.debug_print(f"    Removed period from titled_parts")
                        prev_part = part
                        continue

                    # Handle other word boundary characters
                    if len(part) == 1 and part in self.WORD_BOUNDARY_CHARS:
                        # self.debug_print(f"Keeping separator: {part!r}")
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
                    # Only debug abbreviation check if this might be an abbreviation
                    if part.isalpha() or (len(part) > 1 and any(c.isalpha() for c in part)):
                        self.debug_print(f"  Checking abbreviation: part={part!r} isalpha={part.isalpha()!r}")
                        try:
                            self.debug_print(f"    titled_parts[-2]={titled_parts[-2]!r}   titled_parts[-1]={titled_parts[-1]!r}")
                        except IndexError:
                            pass

                    if part.isalpha():
                        # Check for compound abbreviation pattern (e.g. Lt.Col) or date pattern (e.g. 12.Jan)
                        if prev_part == '.' and titled_parts:
                            self.debug_print(f"  Compound check: prev={titled_parts[-2]!r}, current={part!r}")
                        if prev_part == '.':
                            try:
                                if (titled_parts[-2] in self.ABBREVIATIONS or
                                   (titled_parts[-2].isdigit() and part.upper() in self.MONTH_FORMATS.upper())):
                                    self.debug_print(f"  ✓ Found compound pattern match: {titled_parts[-2]!r}.{part}")
                            except IndexError:
                                # Skip this block if titled_parts[-2] doesn't exist
                                self.debug_print(f"    Skipping compound check: insufficient parts")

                            try:
                                # Get first abbreviation before loop
                                first_abbrev = titled_parts[-2]    # e.g. "Lt"
                                second_abbrev = None  # Initialize to None

                                # Check if first part is an abbreviation
                                first_abbrev_upper = first_abbrev.upper()
                                is_first_part_abbrev = any(a.upper() == first_abbrev_upper for a in self.ABBREVIATIONS)
                                if is_first_part_abbrev:
                                    self.debug_print(f"    First part {first_abbrev!r} is an abbreviation")

                                if is_first_part_abbrev:
                                    # Only check second part if first part is an abbreviation
                                    for abbr in self.ABBREVIATIONS:
                                        if part.upper() == abbr.upper():
                                            # Found abbreviation-period-abbreviation pattern
                                            second_abbrev = abbr  # Use case from ABBREVIATIONS

                                            # Combine abbreviations
                                            try:
                                                titled_parts[-2] = first_abbrev + second_abbrev
                                                self.debug_print(f"  ✓ Combined: {first_abbrev!r}.{second_abbrev!r} → {titled_parts[-2]!r}")
                                                # Remove the period
                                                titled_parts.pop(-1)
                                            except Exception as e:
                                                self.debug_print(f"    ERROR in combine: {e}")

                                            # Update tracking variables
                                            if titled_parts:
                                                prev_part = titled_parts[-1]  # Now points to the combined abbreviation after period removal
                                                prev_was_abbrev = True
                                                prior_abbreviation = titled_parts[-1]  # Track compound as prior_abbreviation
                                            else:
                                                self.debug_print(f"    WARNING: titled_parts is empty after combine operation")
                                            break

                                if not is_first_part_abbrev and part.upper() in [a.upper() for a in self.ABBREVIATIONS]:
                                    self.debug_print(f"    Not combined: {first_abbrev!r} is not an abbreviation, but {part!r} is")
                                self.debug_print(f"    Result: {''.join(titled_parts)!r}")

                                if second_abbrev is not None:
                                    continue
                            except IndexError:
                                # Skip this block if titled_parts[-2] doesn't exist
                                self.debug_print(f"    Skipping compound abbreviation check due to insufficient titled_parts")

                        # Otherwise check for normal abbreviation
                        elif titled_parts and prev_part == '.':
                            self.debug_print(f"  ✓ Found potential SINGLE abbreviation part")
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

                    # Check for frequent mis-typed words (Wi-Fi, etc.)
                    word_lower = word.lower()
                    if word_lower == 'wifi':  # Convert all variants to Wi-Fi
                        titled_parts.append('Wi-Fi')
                        prev_part = part
                        prior_abbreviation = None  # Reset for non-abbreviation
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
                        word_lower in self.STANDALONE_UNITS or                # Standalone units
                        word_lower.isdigit()):                               # Standalone digits for space-separated units
                        self.debug_print(f"⮑ Unit check for: {part!r} (lower={word_lower!r})")
                        self.debug_print(f"  Context: parts[{i}] in {parts[max(0,i-1):min(len(parts),i+3)]!r}")

                        # Initialize unit tracking
                        unit_end_index = i  # Index of the last part of this unit (initially just the current part)
                        unit_parts = [part]  # Track all parts of the unit
                        test_word = word_lower
                        original_parts = [part]

                        # Check for space-separated units (e.g. "5 kb" or "5 g")
                        if parts[i].strip().isdigit() and i + 2 < len(parts) and parts[i+1].strip() == ' ':
                            self.debug_print(f"  Checking for space-separated unit at index {i}: {parts[i:i+3]!r}")
                            # Check if the part after the space is a valid unit
                            next_part = parts[i+2].strip().lower()
                            if re.match(r'^[kmgtw]?[wvajnlhzbfg]', next_part) or next_part in self.STANDALONE_UNITS:
                                # Include space and unit part
                                unit_parts.extend([parts[i+1], parts[i+2]])
                                original_parts.extend([parts[i+1], parts[i+2]])
                                test_word = word_lower + next_part
                                unit_end_index = i + 2  # Update to include the space and unit part
                                self.debug_print(f"  Found space-separated unit: {unit_parts!r}")

                        self.debug_print(f"  Testing unit pattern: {test_word!r}  Original parts: {original_parts!r}")

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
                                    # Apply normal unit formatting
                                    formatted = formatter(test_word)

                                unit_debug = f"✓ Unit: {formatted!r} (from={original_parts!r}, pattern={pattern!r})"
                                self.debug_print(f"    Applied formatter: {test_word!r} -> {formatted!r}")

                                # Mark all parts that make up this unit as processed
                                unit_start_index = i  # Start index of the unit (current part)
                                self.debug_print(f"  Marking parts from unit_start_index={unit_start_index} to unit_end_index={unit_end_index} as processed")
                                for idx in range(unit_start_index, unit_end_index+1):
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
                                # Don't modify loop counter directly, we'll use processed_parts to skip
                                # already processed parts in the next iterations
                                self.debug_print(f"  Found unit at index {i}, marked parts {i} to {unit_end_index} as processed")
                                self.debug_print(f"  Next parts to process: {parts[unit_end_index+1:]!r}" if unit_end_index+1 < len(parts) else "  No more parts to process")
                                self.debug_print(f"  titled_parts after unit found: {titled_parts!r}")
                                # Important: Continue with the main loop after processing this unit
                                # This only breaks out of the inner loop that was checking for unit patterns
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

                    # Skip this part if it's already been processed as part of a unit
                    # This replaces the previous 'if found_unit: continue' approach
                    # try:
                    if processed_parts[i] and processed_parts[i].startswith('part of'):
                        self.debug_print(f"  Skipping already processed part: {parts[i]!r} at index {i}")
                        continue
                    # except Exception as e:
                        # self.debug_print(f"  ERROR checking processed_parts[{i}]: {e}")

                    try:
                        if found_unit:
                            self.debug_print(f"  After unit processing: titled_parts={titled_parts!r}")
                            self.debug_print(f"  Remaining parts to process: {parts[i+1:]!r}")
                        else:
                            self.debug_print(f"  No unit found, for {word!r}")
                    except Exception as e:
                        self.debug_print(f"  ERROR in found_unit check: {e}")

                    # Handle abbreviations - check if this word is an abbreviation
                    # If the previous word was also an abbreviation, we'll handle this
                    # one separately rather than trying to join them
                    #
                    # FUTURE ENHANCEMENT: Support user-provided file for custom abbreviations that overrules
                    # the default processing. This would allow users to specify their own abbreviation handling
                    # after all the standard abbreviation and unit processing is done. # Suggestion: instead of putting 'ON' in the file as initials,
                    # overruling the common word, users could specify 'Mr.ON' or 'Ms.ON' in
                    # their custom file to ensure it's treated as a proper noun.
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

                    # Check if it's in our special dictionary of words that should only be kept capitalized if all caps
                    # Only run this if we haven't already found an abbreviation through other methods
                    if not found_abbrev:
                        abbrev_upper = word.upper()
                        if abbrev_upper in self.KEEP_CAPITALIZED_IF_ALLCAPS:
                            # For special abbreviations, keep capitalized only if original was all caps
                            if part.isupper():
                                # Original was all caps, treat as abbreviation
                                found_abbrev = abbrev_upper
                                abbrev_debug = f"✓ {found_abbrev!r} (special case - kept uppercase)"
                            else:
                                # Original wasn't all caps, don't treat as abbreviation
                                # Let it fall through to normal capitalization rules
                                self.debug_print(f"  Not treating {word!r} as abbreviation (not all caps)")

                    # As much as would like to handle initials (FDR, JFK), can't distinguish from all-uppercase common words (THE, FOX, BUT)

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
                            # Check if we're in a date pattern (number.month)
                            self.debug_print(f"  checking for date pattern: {titled_parts}, Found Abbrev: {found_abbrev}, PrevPart: {prev_part}, PriorDatePart:{prior_date_part} ")
                            if (titled_parts and
                                prev_part == '.' and
                                len(titled_parts) >= 2 and
                                titled_parts[-2].isdigit() and
                                found_abbrev.upper() in self.MONTH_FORMATS):
                                prior_date_part = True
                                self.debug_print(f"  Found date pattern: {titled_parts[-2]}.{found_abbrev}")

                            titled_parts.append(found_abbrev)
                            prev_part = found_abbrev  # Keep the full abbreviation as previous part
                            prev_was_abbrev = True  # Mark that we found a valid abbreviation
                        continue

                    # Not an abbreviation, let it fall through to normal word handling
                    self.debug_print("  No abbreviation match found")

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
                    # self.debug_print(f"  Title case check: first={not titled_parts}, last={word == last_real_word}, after_trigger={last_non_space in self.CAPITALIZATION_TRIGGERS}")
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
                        processed_word = word
                        titled_parts.append(processed_word)
                    else:
                        processed_word = word.capitalize()
                        self.debug_print(f"  Adding to titled_parts: {processed_word!r} (capitalized)")
                        titled_parts.append(processed_word)
                    prev_part = processed_word  # Store the processed version, not the original
                    prior_abbreviation = None  # Reset for non-abbreviation word
            except Exception as e:
                import traceback
                self.debug_print(f"\nEXCEPTION in processing parts: {type(e).__name__}: {e}", level='normal')
                part_str = repr(part) if 'part' in locals() else 'unknown'
                self.debug_print(f"Current part index = {i if 'i' in locals() else 'unknown'}, part = {part_str}", level='normal')
                self.debug_print(f"parts = {parts!r}", level='normal')
                # Check if titled_parts exists before trying to use it
                if 'titled_parts' in locals() and titled_parts:
                    self.debug_print(f"titled_parts = {titled_parts!r}", level='normal')
                else:
                    self.debug_print("titled_parts is not defined or empty", level='normal')
                    # Initialize titled_parts if it doesn't exist
                    titled_parts = []
                self.debug_print("\nDetailed traceback:", level='normal')
                self.debug_print(traceback.format_exc(), level='normal')
                # Use the original name as a fallback
                titled_parts = [name]

        # Convert any remaining full-width ampersands to ' and ' for better readability
        # This happens before restoring preserved terms so that special terms keep their ampersands
        for i, part in enumerate(titled_parts):
            if '\uff06' in part:  # Full-width ampersand
                titled_parts[i] = part.replace('\uff06', ' and ')
                self.debug_print(f"Converted full-width ampersand to ' and ' in part: {titled_parts[i]!r}", level='normal')

        # Restore Preserved Terms that were replaced with markers
        try:
            # Ensure titled_parts is defined before using it
            if not 'titled_parts' in locals() or titled_parts is None:
                self.debug_print("titled_parts was not defined before restore attempt, initializing to [name]", level='normal')
                titled_parts = [name]

            self.debug_print(f"titled_parts before restore = {titled_parts!r}", level='normal')
            titled_parts = self._restore_preserved_terms(titled_parts)
            self.debug_print(f"[RESTORE] titled_parts after restoring preserved terms: {titled_parts!r}", level='normal')
        except Exception as e:
            import traceback
            self.debug_print(f"\nEXCEPTION in _restore_preserved_terms: {type(e).__name__}: {e}", level='normal')
            # Check if titled_parts exists before trying to use it
            if 'titled_parts' in locals() and titled_parts is not None:
                self.debug_print(f"titled_parts before restore = {titled_parts!r}", level='normal')
            else:
                self.debug_print("titled_parts was not defined or is None", level='normal')
                # Initialize titled_parts if it doesn't exist
                titled_parts = [name]
            self.debug_print("\nDetailed traceback:", level='normal')
            self.debug_print(traceback.format_exc(), level='normal')
            # Continue with the unmodified titled_parts as a fallback

        # Handle periods in preserved terms by replacing with a placeholder
        PRESERVED_PERIOD_PLACEHOLDER = '__PRESERVED_TERM_PERIOD__'
        preserved_terms_with_periods = [term for term in self.PRESERVED_TERMS if '.' in term]

        for term in preserved_terms_with_periods:
            # Create a version of the term with the placeholder instead of periods
            term_with_placeholder = term.replace('.', PRESERVED_PERIOD_PLACEHOLDER)

            # Replace the term in the parts list
            for i, part in enumerate(titled_parts):
                # self.debug_print(f"[PRESERVED_PERIODS] Checking part vs term: {part!r} == {term!r} -> {part == term}", level='normal')
                if part == term:
                    titled_parts[i] = term_with_placeholder

        # Process periods in each part individually (excluding Preserved Terms)
        processed_parts = []
        try:
            for part in titled_parts:
                # Skip empty parts
                if not part:
                    continue

                # Define period handling function for this part
                def handle_periods(match):
                    full_str = part  # Capture the full part for context
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
                    result = f'. {after_char}'
                    self.debug_print(f"[PERIODS] Adding space after period: '.{after_char}' -> '{result}' (before_char={before_char!r})", level='normal')
                    return result

                # Process periods in this part
                processed_part = re.sub(r'\.([a-zA-Z])', handle_periods, part)

                # Restore periods from PRESERVED_PERIOD_PLACEHOLDER in this part
                placeholder_count = processed_part.count(PRESERVED_PERIOD_PLACEHOLDER)
                if placeholder_count > 0:
                    # self.debug_print(f"[PERIODS] Found {placeholder_count} period placeholders to restore in part: {processed_part!r}", level='normal')
                    processed_part = processed_part.replace(PRESERVED_PERIOD_PLACEHOLDER, '.')
                    self.debug_print(f"[PERIODS] After restoring period placeholders in part: {processed_part!r}", level='normal')

                processed_parts.append(processed_part)
        except Exception as e:
                import traceback
                self.debug_print(f"\nEXCEPTION in processing periods: {type(e).__name__}: {e}", level='normal')
                self.debug_print(f"Current part = {part!r}", level='normal')
                self.debug_print(f"titled_parts = {titled_parts!r}", level='normal')
                self.debug_print("\nDetailed traceback:", level='normal')
                self.debug_print(traceback.format_exc(), level='normal')
                # Add the unprocessed parts to processed_parts as a fallback
                processed_parts = titled_parts

        # Join the processed parts with error trapping
        try:
            if not processed_parts:
                self.debug_print(f"WARNING: processed_parts is empty, this may indicate a processing error", level='normal')
                # Return the original name as a fallback
                name = name
            else:
                name = ''.join(processed_parts)
                self.debug_print(f"[PERIODS] After joining processed parts: {name!r}", level='normal')

                # Clean up any double spaces
                name = re.sub(r'\s+', ' ', name)

                # Do one final check for trailing special characters
                name = self._clean_trailing_chars(name)
        except Exception as e:
            import traceback
            self.debug_print(f"\nEXCEPTION in joining processed parts: {type(e).__name__}: {e}", level='normal')
            self.debug_print(f"processed_parts = {processed_parts!r}", level='normal')
            self.debug_print("\nDetailed traceback:", level='normal')
            self.debug_print(traceback.format_exc(), level='normal')
            # Return the original name as a fallback
            name = name

        # If original had no spaces, remove all spaces from the result
        if ' ' not in filename:
            name = name.replace(' ', '')

        # Always use lowercase for extensions, whether known or unknown
        if extension:
            result = f"{name}.{extension.lower()}"
        else:
            result = name

        # Process any remaining quotes
        result = self.final_quote_processing(result)

        return result

    def process_files(self, batch_size=100) -> List[Tuple[str, str]]:
        """
        Process all files in the directory.

        Args:
            batch_size: Number of files to process before displaying progress

        Returns:
            List[Tuple[str, str]]: List of (original_name, new_name) pairs

        Note:
            Some filesystems may not allow certain ASCII special characters in filenames.
            In such cases, we detect this and report it, then proceed with the Unicode
            replacement character anyway since that's our goal.
        """
        self.debug_print("Starting to process files in directory: {}".format(self.directory), level='normal')
        changes = []
        processed_count = 0

        for item in self.directory.iterdir():
            if item.is_file():
                original_name = item.name
                self.debug_print(f"\n\nBefore clean_filename: {original_name!r}", level='normal')
                new_name = self._clean_filename(original_name)
                processed_count += 1
                self.debug_print(f"After clean_filename: {original_name!r} -> {new_name!r}", level='normal')

                # Display progress in batches
                if processed_count % batch_size == 0:
                    print(f"Processed {processed_count} files so far")

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
    parser.add_argument('--settings', dest='settings_path',
                      help='Path to custom settings file')
    parser.add_argument('--batch-size', type=int, default=100,
                      help='Display progress after processing this many files (default: 100)')

    # Add a custom -? help option
    parser.add_argument('-?', action='help',
                      help='Show this help message and exit')

    args = parser.parse_args()

    # Update debug mode based on command line flag
    if args.debug:
        FileRenamer._debug = True
        os.environ['RENAMER_DEBUG'] = 'detail'  # Enable detailed debug output

    # Check if user is trying to run in the program's directory
    directory_path = Path(args.directory).resolve()
    program_dir = Path(__file__).parent.resolve()

    if directory_path == program_dir:
        print("WARNING: You are attempting to run this program on its own directory.")
        print("This is not recommended as it could modify the program's own files.")
        print("Please specify a different directory to process.")
        print("Example: python file_renamer.py ~/Videos --dry-run")
        return 1

    # Check if directory exists before proceeding
    if not directory_path.exists():
        print(f"Error: Directory '{directory_path}' does not exist.")
        print("Please provide a valid directory path.")
        return 1
    elif not directory_path.is_dir():
        print(f"Error: '{directory_path}' is not a directory.")
        print("Please provide a valid directory path.")
        return 1

    renamer = FileRenamer(args.directory, dry_run=args.dry_run, settings_path=args.settings_path)
    changes = renamer.process_files(batch_size=args.batch_size)

    if args.dry_run:
        print("\nProposed changes (dry run):\n")
    else:
        print("\nExecuted changes: (showing special character replacements in cyan)\n")

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
            print(f"   {old}\n-> {colored_new}\n")

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

@classmethod
def load_user_settings(cls, settings_path: Optional[str] = None) -> Tuple[Set[str], Set[str]]:
    """Load user settings from settings.ini file.

    Args:
        settings_path: Optional path to settings file. If None, will search in standard locations.

    Returns:
        Tuple of (user_abbreviations, user_preserved_terms)
    """
    # Initialize empty sets for user settings
    user_abbreviations = set()
    user_preserved_terms = set()

    # Find settings file
    settings_file = cls._find_settings_file(settings_path)
    if not settings_file:
        # No settings file found, return empty sets
        cls.debug_print(f"No settings file found", level='normal')
        return user_abbreviations, user_preserved_terms

    # Parse settings file
    try:
        current_section = None
        with open(settings_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Remove comments and strip whitespace
                line = line.split('#', 1)[0].strip()

                if not line:  # Skip empty lines
                    continue

                # Check for section header
                if line.startswith('[') and line.endswith(']'):
                    section_name = line[1:-1].strip().lower()
                    if section_name in ('abbreviations', 'preserved_terms'):
                        current_section = section_name
                    else:
                        cls.debug_print(f"Warning: Unknown section '{section_name}' at line {line_num}", level='normal')
                        current_section = None
                elif current_section:
                    # Validate entry
                    if cls._is_valid_settings_entry(line):
                        # Add entry to current section
                        if current_section == 'abbreviations':
                            user_abbreviations.add(line)
                        else:  # preserved_terms
                            user_preserved_terms.add(line)
                    else:
                        cls.debug_print(f"Warning: Invalid entry '{line}' at line {line_num}", level='normal')
                else:
                    cls.debug_print(f"Warning: Entry '{line}' at line {line_num} not in any section", level='normal')
    except Exception as e:
        cls.debug_print(f"Error reading settings file: {e}", level='normal')
        # Return empty sets on error
        return set(), set()

    # Log the loaded settings
    if user_abbreviations:
        cls.debug_print(f"Loaded {len(user_abbreviations)} user abbreviations from {settings_file}", level='normal')
    if user_preserved_terms:
        cls.debug_print(f"Loaded {len(user_preserved_terms)} user preserved terms from {settings_file}", level='normal')

    return user_abbreviations, user_preserved_terms

@staticmethod
def _is_valid_settings_entry(entry: str) -> bool:
    """Validate a settings entry.

    Args:
        entry: The entry to validate

    Returns:
        True if valid, False otherwise
    """
    # Check for control characters
    if any(unicodedata.category(c).startswith('C') for c in entry):
        return False

    # Check length in UTF-16 encoding (NTFS limit)
    if len(entry.encode('utf-16-le')) // 2 > 255:
        return False

    return True

@staticmethod
def _find_settings_file(settings_path: Optional[str] = None) -> Optional[str]:
    """Find the settings file in standard locations.

    Args:
        settings_path: Optional path to settings file

    Returns:
        Path to settings file if found, None otherwise
    """
    # Check locations in order of priority
    locations = []

    # 1. Command-line specified path
    if settings_path:
        locations.append(settings_path)

    # 2. Current directory
    locations.append(os.path.join(os.getcwd(), 'settings.ini'))

    # 3. User's home directory
    home_dir = os.path.expanduser('~')
    locations.append(os.path.join(home_dir, '.config', 'file_renamer', 'settings.ini'))

    # Check each location
    for location in locations:
        if os.path.isfile(location):
            return location

    return None

# Attach the methods to the FileRenamer class
FileRenamer.load_user_settings = load_user_settings
FileRenamer._is_valid_settings_entry = _is_valid_settings_entry
FileRenamer._find_settings_file = _find_settings_file

# Define a custom exception handler that will only be installed when this file is run directly (not when run with pytest)
def global_exception_handler(exc_type, exc_value, exc_traceback):
    # Get the most recent frame from the traceback for location information
    tb_frame = traceback.extract_tb(exc_traceback)[-1] if exc_traceback else None

    # Extract file, line, and function information if available
    file_info = f" in {tb_frame.filename}:{tb_frame.lineno} (function: {tb_frame.name})" if tb_frame else ""

    # Create error message with location information
    error_msg = f"Unhandled exception: {exc_type.__name__}: {exc_value}{file_info}\n"

    # Always write to both stdout and stderr to maximize visibility
    sys.stdout.write(f"\n==== GLOBAL EXCEPTION HANDLER ====\n")
    sys.stdout.write(error_msg)
    sys.stdout.write("\nDetailed traceback:\n")
    sys.stdout.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    sys.stdout.write("\nPlease report this error with the above information.\n")
    sys.stdout.write("==== END EXCEPTION HANDLER ====\n")
    sys.stdout.flush()

    # Also write to stderr which pytest will capture even with --capture=no
    sys.stderr.write(f"\n==== GLOBAL EXCEPTION HANDLER ====\n")
    sys.stderr.write(error_msg)
    sys.stderr.write("\nDetailed traceback:\n")
    sys.stderr.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    sys.stderr.write("\nPlease report this error with the above information.\n")
    sys.stderr.write("==== END EXCEPTION HANDLER ====\n")
    sys.stderr.flush()

if __name__ == '__main__':
    # Only install the exception handler when running this file directly
    # This prevents it from interfering with pytest's exception handling
    sys.excepthook = global_exception_handler

    logging.basicConfig(level=logging.DEBUG)
    try:
        main()
    except Exception as e:
        print(f"\nUnhandled exception: {type(e).__name__}: {e}")
        print("\nDetailed traceback:")
        print(traceback.format_exc())
        print("\nPlease report this error with the above information.")
