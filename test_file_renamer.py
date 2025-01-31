#!/usr/bin/env python3
"""
Unit tests for the file renamer script.

Author: Cascade AI
Date: 2025-01-27
"""

import unittest
import tempfile
from pathlib import Path
from file_renamer import FileRenamer

class TestFileRenamer(unittest.TestCase):
    """Test cases for FileRenamer class."""

    def setUp(self):
        """Set up a temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.renamer = FileRenamer(self.temp_dir, dry_run=True)

    def test_special_character_replacement(self):
        """Test replacement of special characters.

        Special characters are replaced with similar Unicode characters.
        Words after special characters are always capitalized, even if they're
        in LOWERCASE_WORDS, because only spaces (not special characters) trigger
        the lowercase word rules. For example:
        - 'file\\with' -> 'File⧵With'  # 'with' capitalized after backslash or other special characters
        - 'file with' -> 'File with'  # 'with' lowercase between spaces
        """
        # Use CHAR_REPLACEMENTS from FileRenamer to ensure we test with exact same characters
        R = FileRenamer.CHAR_REPLACEMENTS  # Shorthand for readability

        # Store special characters to avoid f-string syntax issues
        backslash = R['\\']
        pipe = R['|']
        quote = R['"']
        lt = R['<']
        gt = R['>']
        qmark = R['?']
        asterisk = R['*']
        colon = R[':']

        test_cases = [
            (r'file\with*special:chars?.txt', f'File{backslash}With{asterisk}Special{colon}Chars{qmark}.txt'),
            (f'file|with"pipes<and>symbols.txt', f'File{pipe}With{quote}Pipes{lt}And{gt}Symbols.txt'),
            ('file\nwith\ttabs', 'File with Tabs'),  # Whitespace normalization
            ('question???marks', f'Question{qmark}Marks'),  # Multiple ? collapses to one (and spaces preserved)
            ('exclaim!!!point', 'Exclaim!Point'),  # Multiple ! collapses to one
            ('What??? Really???.txt', f'What{qmark} Really{qmark}.txt'),  # Real-world multiple ? example
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_title_case_rules(self):
        """Test title case formatting rules."""
        test_cases = [
            ('THE QUICK BROWN FOX.txt', 'The Quick Brown Fox.txt'),
            ('a tale of two cities.txt', 'A Tale of Two Cities.txt'),
            ('THIS is THE story.txt', 'This is the Story.txt'),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected)

    def test_whitespace_normalization(self):
        """Test that whitespace is properly normalized.

        - Multiple spaces collapse to single space
        - Newlines and tabs convert to single space
        - Leading/trailing spaces are removed
        """
        test_cases = [
            ('multiple   spaces.txt', 'Multiple Spaces.txt'),
            ('trailing spaces  .txt', 'Trailing Spaces.txt'),
            # Use actual newline in string
            ('Future Coach 2023-09-08 Eben\n2024-08-22_07-59-48.mkv'.replace('\\n', '\n'),
             'Future Coach 2023-09-08 Eben 2024-08-22_07-59-48.mkv'),
            ('file\twith\ttabs', 'File with Tabs'),  # Real tabs
            ('spaces   and\ttabs  mixed', 'Spaces and Tabs Mixed'),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_multiple_spaces_and_punctuation(self):
        """Test handling of multiple spaces and punctuation.

        Internal periods are preserved exactly as they appear, including:
        - Abbreviations (e.g., 'Min.')
        - Numbered items (e.g., '26.')
        - Ellipsis (...)
        - Stylized text ('EVERY. SINGLE. MONTH.')
        Multiple exclamation marks are collapsed to one.
        Only trailing periods are removed.
        Multiple question marks are replaced with one ⁇.
        Ampersands (&) are replaced with 'and'.
        Three or more periods are replaced with ellipsis character.
        """
        R = FileRenamer.CHAR_REPLACEMENTS  # Shorthand for readability

        # Debug the specific case
        test_input = 'trailing.periods....txt'
        result = self.renamer._clean_filename(test_input)
        print(f"\nDebug specific case:\nInput:  {test_input!r}\nOutput: {result!r}\n")

        test_cases = [
            ('multiple!!!!! Exclamation Marks.txt', 'Multiple! Exclamation Marks.txt'),
            ('10 Min. Exercise Routine.txt', '10 Min. Exercise Routine.txt'),
            ('26. Greatest — Story.txt', '26. Greatest — Story.txt'),
            ('Tips For Success... Never Give Up.txt', f'Tips for Success{R["..."]} Never Give Up.txt'),
            ('trailing.periods....txt', 'Trailing.Periods.txt'),  # Multiple periods before extension get removed
            ('EVERY. SINGLE. MONTH..txt', 'Every. Single. Month.txt'),
            ('mixed!!!...!!!.txt', f'Mixed!{R["..."]}!.txt'),
            ('What??? Really???.txt', f'What{R["?"]} Really{R["?"]}.txt'),
            ('Fish & Chips.txt', 'Fish and Chips.txt'),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_special_character_replacement(self):
        """Test that special characters are properly replaced."""
        # Store special characters to avoid f-string syntax issues
        R = FileRenamer.CHAR_REPLACEMENTS
        backslash = R['\\']
        asterisk = R['*']
        colon = R[':']
        qmark = R['?']
        pipe = R['|']
        quote = R['"']
        lt = R['<']
        gt = R['>']

        test_cases = [
            (r'file\with*special:chars?.txt',
             f'File{backslash}With{asterisk}Special{colon}Chars{qmark}.txt'),
            (f'file|with"pipes<and>symbols.txt',
             f'File{pipe}With{quote}Pipes{lt}And{gt}Symbols.txt'),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_multiple_special_chars(self):
        """Test handling of multiple special characters.

        - Multiple question marks collapse to one
        - Multiple exclamation marks collapse to one
        - Three or more dots become ellipsis
        - Spaces around special characters are preserved if in original
        """
        # Store special characters to avoid f-string syntax issues
        R = FileRenamer.CHAR_REPLACEMENTS
        qmark = R['?']
        ellipsis = R['...']

        test_cases = [
            ('What??? Really???.txt', f'What{qmark} Really{qmark}.txt'),
            ('Hello!!! World!!!.txt', 'Hello! World!.txt'),
            ('Multiple.....Dots...Here.txt', f'Multiple{ellipsis}Dots{ellipsis}Here.txt'),
            ('Multiple... Dots... With Spaces.txt', f'Multiple{ellipsis} Dots{ellipsis} With Spaces.txt'),
            ('file... middle text', f'File{ellipsis} Middle Text'),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_real_world_examples(self):
        """Test with real-world example filenames.

        For filenames with spaces, the original spacing around special characters is preserved.
        For example:
        - 'Title: Subtitle' -> 'Titleː Subtitle'  # original spacing preserved (colon replaced with look-alike)
        - 'Path\to\file' -> 'Path⧵to⧵file'  # no spaces added (backslashes replaced with look-alike)
        Ampersands are replaced with 'and'.
        """
        # Store special characters to avoid f-string syntax issues
        R = FileRenamer.CHAR_REPLACEMENTS
        colon = R[':']
        pipe = R['|']

        test_cases = [
            (
                'Law of Attraction Secrets: How to Manifest Anything You Want Faster Than Ever!.mp4',
                f'Law of Attraction Secrets{colon} How to Manifest Anything You Want Faster Than Ever!.mp4'
            ),
            (
                'Make So Much Money You Question It! - Get Ahead of 99% of People & Win at Anything | Alex Hormozi.mp4',
                f'Make So Much Money You Question It! - Get Ahead of 99% of People and Win at Anything {pipe} Alex Hormozi.mp4'
            ),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_trailing_characters(self):
        """Test handling of trailing characters.

        - Trailing periods are removed
        - Trailing ellipsis is removed
        - Only specific special characters are preserved at the end:
          * Closing brackets (), [], {}, etc (replacements from CHAR_REPLACEMENTS)
          * Exclamation marks !
          * Full-width dollar sign ＄
          * Right double quotation mark "
        - Spaces revealed by removing trailing periods are also removed
        """
        # Store special characters to avoid f-string syntax issues
        R = FileRenamer.CHAR_REPLACEMENTS
        quote = R['"']
        dollar = R['$']
        ellipsis = R['...']

        test_cases = [
            ('file....', 'File'),  # Remove trailing periods
            ('file... middle text', f'File{ellipsis} Middle Text'),  # Keep ellipsis in middle
            ('file(1).', 'File(1)'),  # Remove trailing period but keep parentheses
            ('price$.', f'Price{dollar}'),  # Keep full-width dollar sign but remove period
            ('file[1].txt....', 'File[1].txt'),  # Keep brackets, remove trailing periods. That leaves a new file extension '.txt'
            ('script."unknown"...', f'Script.{quote}Unknown{quote}'),  # Keep quote but remove trailing periods
            ('script.py"...', f'script.py'),  # Remove quote and remove trailing periods, recognize new file extension '.py'
            ('log|...', 'Log'),  # Remove vertical line or other special character and trailing periods
            ('test<...', 'Test'),  # Remove angle bracket and trailing periods
            ('test\\...', 'Test'),  # Remove backslash and trailing periods
            ('test...', 'Test'),  # Remove backslash and trailing periods
            ('test!', 'Test!'),  # Keep exclamation mark at end
            ('Clark Gable in "Gone with the Wind".png', f'Clark Gable in {quote}Gone with the Wind{quote}.png'),  # Keep quotes even at the end
            ('script.py', 'script.py'),  # Don't change casing of known file extensions
            ('data.json}...', 'Data.json'),  # Remove closing brace, remove trailing periods
            ('data.json', 'data.json'),  # Don't change casing of known file extensions
            ('Dylan Wright - Tiny Dancer (Elton John) - Australian Idol 2024 - Grand Final.mp4',
             'Dylan Wright - Tiny Dancer (Elton John) - Australian Idol 2024 - Grand Final.mp4'),  # Keep capitalization after parentheses
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_file_extensions(self):
        """Test handling of file extensions.

        For files with known extensions (py, js, css, etc):
        - Keep original filename case (no title casing)
        - Always use lowercase for extension

        For files with unknown extensions:
        - Apply title case to filename
        - Always use lowercase for extension
        """
        test_cases = [
            # Programming files - keep original name case
            ('test.PY', 'test.py'),      # Keep lowercase name
            ('TEST.py', 'TEST.py'),      # Keep uppercase name
            ('mixedCase.PHP', 'mixedCase.php'),  # Keep mixed case
            # Web files - keep original name case
            ('styles.CSS', 'styles.css'),  # Keep lowercase name
            ('LAYOUT.HTML', 'LAYOUT.html'),  # Keep uppercase name
            ('myScript.JS', 'myScript.js'),  # Keep mixed case
            # Documentation - keep original name case
            ('README.MD', 'README.md'),  # Keep uppercase name
            ('debug.LOG', 'debug.log'),  # Keep lowercase name
            # Unknown extensions - apply title case to name
            ('test.FOO', 'Test.foo'),    # Title case name, lowercase ext
            ('WEIRD.BAR', 'Weird.bar'),  # Title case name, lowercase ext
            ('mixed.CASE', 'Mixed.case'),  # Title case name, lowercase ext
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

if __name__ == '__main__':
    unittest.main()
