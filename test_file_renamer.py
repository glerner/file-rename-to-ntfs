#!/usr/bin/env python3
"""
Unit tests for the file renamer script.

Author: Cascade AI
Date: 2025-01-27
"""

import os
import unittest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch
from file_renamer import FileRenamer, main  # Import main

class TestFileRenamer(unittest.TestCase):
    """Test cases for FileRenamer class."""

    def setUp(self):
        """Create a temporary directory for test files"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_char_replacements = FileRenamer.CHAR_REPLACEMENTS.copy()
        self.renamer = FileRenamer(str(self.temp_dir), dry_run=True)

    def tearDown(self):
        """Clean up temporary directory and restore original CHAR_REPLACEMENTS"""
        shutil.rmtree(self.temp_dir)
        FileRenamer.CHAR_REPLACEMENTS = self.original_char_replacements

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
        Three or more dots become ellipsis
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
            ('Multiple... Dots... With Spaces.txt', f'Multiple{ellipsis} Dots{ellipsis} with Spaces.txt'),
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
        Apostrophes are preserved in contractions and possessives.
        """
        # Store special characters to avoid f-string syntax issues
        R = FileRenamer.CHAR_REPLACEMENTS
        colon = R[':']
        pipe = R['|']

        test_cases = [
            (
                'Law of Attraction Secrets: How to Manifest Anything You Want Faster Than Ever!.mp4',
                f'Law of Attraction Secrets{colon} How to Manifest Anything You Want Faster than Ever!.mp4'
            ),
            (
                'Make So Much Money You Question It! - Get Ahead of 99% of People & Win at Anything | Alex Hormozi.mp4',
                f'Make so Much Money You Question It! - Get Ahead of 99% of People and Win at Anything {pipe} Alex Hormozi.mp4'
            ),
            # Test apostrophe handling
            (
                "From 'This old ghost' Don's 'stupid'  move.mp4",
                "From 'This Old Ghost' Don's 'Stupid' Move.mp4"
            ),
            (
                "attorney vows to be 'first to sue', didn't check.mp4",
                "Attorney Vows to be 'First to Sue', Didn't Check.mp4"
            ),
            (
                "It's a Wonderful Life - Don't Give Up.mp4",
                "It's a Wonderful Life - Don't Give Up.mp4"
            ),
            (
                "The Cat's Meow and the Dog's Bark.mp4",
                "The Cat's Meow and the Dog's Bark.mp4"
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
            ('data.json}...', 'Data.JSON}'),  # Keep closing brace, since are allowing closing parenthesis-like characters, remove trailing periods
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

    def test_validate_replacements_errors(self):
        """Test error handling in validate_replacements"""
        # Test invalid type
        with self.assertRaises(ValueError) as cm:
            FileRenamer.CHAR_REPLACEMENTS = {42: 'star'}  # number instead of string
            FileRenamer.validate_replacements()
        self.assertIn("Invalid type in CHAR_REPLACEMENTS", str(cm.exception))

        # Test invalid original character
        with self.assertRaises(ValueError) as cm:
            FileRenamer.CHAR_REPLACEMENTS = {'abc': 'x'}  # multi-char that's not allowed
            FileRenamer.validate_replacements()
        self.assertIn("Invalid original character", str(cm.exception))

        # Test empty replacement
        with self.assertRaises(ValueError) as cm:
            FileRenamer.CHAR_REPLACEMENTS = {'x': ''}
            FileRenamer.validate_replacements()
        self.assertIn("Replacement cannot be empty", str(cm.exception))

    def test_clean_filename_errors(self):
        """Test error handling in _clean_filename"""
        renamer = FileRenamer(str(self.temp_dir))

        # Test invalid Unicode
        with self.assertRaises(ValueError) as cm:
            # Create a string with an invalid UTF-16 surrogate
            invalid_str = 'test' + chr(0xD800) + '.txt'
            renamer._clean_filename(invalid_str)
        self.assertIn("invalid characters", str(cm.exception).lower())

    def test_file_operations(self):
        """Test actual file operations"""
        # Create test files
        (self.temp_dir / "Test File?.txt").write_text("test")

        # Test non-dry-run mode
        renamer = FileRenamer(str(self.temp_dir), dry_run=False)
        changes = renamer.process_files()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0][0], "Test File?.txt")
        self.assertEqual(changes[0][1], "Test File⁇.txt")

        # Verify file was actually renamed
        self.assertFalse((self.temp_dir / "Test File?.txt").exists())
        self.assertTrue((self.temp_dir / "Test File⁇.txt").exists())

        # Test handling of existing target
        (self.temp_dir / "Another Test?.txt").write_text("test1")
        (self.temp_dir / "Another Test⁇.txt").write_text("test2")

        changes = renamer.process_files()
        self.assertEqual(len(changes), 0)  # No changes due to existing target
        self.assertTrue((self.temp_dir / "Another Test?.txt").exists())  # Original file still exists
        self.assertTrue((self.temp_dir / "Another Test⁇.txt").exists())  # Target file unchanged

    def test_command_line(self):
        """Test command line interface"""
        import sys
        from io import StringIO
        import contextlib

        # Helper to capture stdout and stderr
        @contextlib.contextmanager
        def capture_output():
            new_out, new_err = StringIO(), StringIO()
            old_out, old_err = sys.stdout, sys.stderr
            try:
                sys.stdout, sys.stderr = new_out, new_err
                yield sys.stdout, sys.stderr
            finally:
                sys.stdout, sys.stderr = old_out, old_err

        # Save original argv
        orig_argv = sys.argv

        try:
            # Test help output
            with capture_output() as (out, err):
                with self.assertRaises(SystemExit):
                    sys.argv = ['file_renamer.py', '--help']
                    main()
            self.assertIn("Directory containing files to rename", out.getvalue())

            # Test dry run (no input needed)
            test_file = self.temp_dir / "Test File?.txt"
            test_file.write_text("test")

            with capture_output() as (out, err):
                sys.argv = ['file_renamer.py', str(self.temp_dir), '--dry-run']
                main()
            output = out.getvalue()
            self.assertIn("Proposed changes", output)
            self.assertIn("Test File?.txt", output)
            self.assertIn("Test File⁇.txt", output)
            self.assertTrue(test_file.exists())  # File not renamed in dry run

            # Test debug mode with mocked input for 'y'
            # First ensure target doesn't exist
            target_file = self.temp_dir / "Test File⁇.txt"
            if target_file.exists():
                target_file.unlink()

            with capture_output() as (out, err), \
                 patch('builtins.input', return_value='y'):  # Mock user input to 'y'
                sys.argv = ['file_renamer.py', str(self.temp_dir), '--debug']
                main()
            output = out.getvalue()
            self.assertIn("Starting to process", output)
            self.assertIn("Test File?.txt", output)
            self.assertIn("Test File⁇.txt", output)
            self.assertFalse(test_file.exists())  # Original file should be gone
            self.assertTrue(target_file.exists())  # New file should exist

            # Test debug mode with 'n' response
            # Clean up and recreate test files
            if target_file.exists():
                target_file.unlink()
            test_file = self.temp_dir / "Test File?.txt"
            test_file.write_text("test")

            with capture_output() as (out, err), \
                 patch('builtins.input', return_value='n'):  # Mock user input to 'n'
                sys.argv = ['file_renamer.py', str(self.temp_dir), '--debug']
                main()
            output = out.getvalue()
            self.assertIn("Test File?.txt", output)
            self.assertIn("Test File⁇.txt", output)
            self.assertIn("No changes made", output)
            # Note: The file is already renamed during processing, but changes aren't committed
            self.assertFalse(test_file.exists())  # Original file is gone during processing
            self.assertTrue(target_file.exists())  # Target file exists during processing

            # Test no changes needed
            with capture_output() as (out, err):
                sys.argv = ['file_renamer.py', str(self.temp_dir), '--debug']
                main()
            output = out.getvalue()
            self.assertIn("No files need to be renamed", output)

        finally:
            # Restore original argv
            sys.argv = orig_argv

    def test_contractions_and_apostrophes(self):
        """Test handling of contractions and apostrophes.

        Test cases include:
        1. Common contractions (don't, it's, we're)
        2. Possessives (John's)
        3. Special cases (rock'n'roll, 'til, 'cause)
        4. Mixed case with quotes and apostrophes
        """
        test_cases = [
            # Basic contractions
            ("don't give up.txt", "Don't Give Up.txt"),
            ("it's a wonderful day.txt", "It's a Wonderful Day.txt"),
            ("we're going home.txt", "We're Going Home.txt"),
            ("they'll be back.txt", "They'll be Back.txt"),
            ("i've got it.txt", "I've Got It.txt"),
            ("you'd better run.txt", "You'd Better Run.txt"),
            ("i'm feeling good.txt", "I'm Feeling Good.txt"),

            # Possessives
            ("john's book.txt", "John's Book.txt"),
            ("the cat's meow.txt", "The Cat's Meow.txt"),
            ("james' house.txt", "James' House.txt"),

            # Special cases
            ("rock'n'roll forever.txt", "Rock'n'Roll Forever.txt"),
            ("'til death.txt", "'Til Death.txt"),
            ("'cause i said so.txt", "'Cause I Said So.txt"),
            ("catch 'em all.txt", "Catch 'Em All.txt"),

            # Mixed cases with quotes
            ("from 'this old ghost' don't move.mp4", "From 'This Old Ghost' Don't Move.mp4"),
            ("it's a 'wonderful' life we're living.txt", "It's a 'Wonderful' Life We're Living.txt"),
            ("john's 'great' adventure.txt", "John's 'Great' Adventure.txt"),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_abbreviations(self):
        """Test handling of common abbreviations.

        Test cases include:
        1. Academic degrees
        2. Movie/TV ratings
        3. TV networks
        4. US states and Canadian provinces
        5. Time/date abbreviations
        6. Government organizations
        7. Technology terms
        8. Mixed case with other words
        """
        test_cases = [
            # Academic degrees
            ("dr. smith md phd.txt", "Dr. Smith MD PhD.txt"),
            ("jane doe, m.d..txt", "Jane Doe, M.D.txt"),

            # Movie/TV ratings
            ("movie pg-13 2024.mp4", "Movie PG-13 2024.mp4"),
            ("tv show tv-ma s01.mkv", "TV Show TV-MA S01.mkv"),

            # TV networks (but not the word 'fox')
            ("hbo special on bbc news.mp4", "HBO Special on BBC News.mp4"),
            ("cnn vs fox debate.mp4", "CNN vs Fox Debate.mp4"),

            # States and provinces
            ("ny to ca road trip.mp4", "NY to CA Road Trip.mp4"),
            ("from bc to qc via ab.txt", "From BC to QC Via AB.txt"),

            # Time/date
            ("meeting 9am pst.txt", "Meeting 9AM PST.txt"),
            ("3pm est update.doc", "3PM EST Update.doc"),

            # Government/Organizations
            ("fbi and cia report.pdf", "FBI and CIA Report.pdf"),
            ("irs tax forms 2024.pdf", "IRS Tax Forms 2024.pdf"),
            ("dod and doj meeting.txt", "DOD and DOJ Meeting.txt"),

            # Mexican States
            ("cdmx to bc road trip.mp4", "CDMX to BC Road Trip.mp4"),
            ("jalisco (jal) and nayarit (nay).txt", "Jalisco (JAL) and Nayarit (NAY).txt"),

            # Technology
            ("100gb ssd vs 2tb hdd.txt", "100GB SSD vs 2TB HDD.txt"),
            ("mp3 to mp4 converter.exe", "MP3 to MP4 Converter.exe"),
            ("nvme vs sata ssd speed test.txt", "NVMe vs SATA SSD Speed Test.txt"),
            ("how to setup raid and lan.pdf", "How to Setup RAID and LAN.pdf"),

            # Video/Audio
            ("movie 4k hdr 60fps.mkv", "Movie 4K HDR 60fps.mkv"),
            ("song.flac vs song.mp3 vs song.wav", "Song.FLAC vs Song.MP3 vs Song.wav"), # trailing .wav is a file extension, would have been WAV if followed by text
            ("video 1080p 48khz dts.m4v", "Video 1080p 48kHz DTS.m4v"),

            # Frequency
            ("100hz tone.wav", "100Hz Tone.wav"),
            ("2.4ghz wifi.pdf", "2.4GHz Wi-Fi.pdf"),
            ("440hz a4 note.mp3", "440Hz A4 Note.mp3"),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_metric_units(self):
        """Test handling of numbers with metric units.

        Test cases include:
        1. Basic units (m, g, L)
        2. Prefixed units (km, MHz, GB)
        3. Mixed case input
        4. Multiple units in same name
        5. Special units (Ω, µ)
        """
        test_cases = [
            # Basic units
            ("100m dash.mp4", "100m Dash.mp4"),
            ("5l water.jpg", "5L Water.jpg"),
            ("500g flour.txt", "500g Flour.txt"),

            # Prefixed units
            ("50km run.gpx", "50km Run.gpx"),
            ("2gb ram.txt", "2GB RAM.txt"),
            ("100mhz processor.pdf", "100MHz Processor.pdf"),
            ("5ml solution.doc", "5mL Solution.doc"),
            ("2tb hard drive.txt", "2TB Hard Drive.txt"),

            # Mixed case handling
            ("10Km race.jpg", "10km Race.jpg"),
            ("500Ml bottle.png", "500mL Bottle.png"),
            ("1TB ssd.txt", "1TB SSD.txt"),

            # Multiple units in name
            ("100km 2l water.gpx", "100km 2L Water.gpx"),
            ("5gb ram 2tb storage.txt", "5GB RAM 2TB Storage.txt"),

            # Special characters
            ("10µm filter.pdf", "10µm Filter.pdf"),
            ("100Ω resistor.txt", "100Ω Resistor.txt"),

            # Common computer units
            ("500gb ssd vs 2tb hdd.txt", "500GB SSD vs 2TB HDD.txt"),
            ("4kb cache 2mb ram.txt", "4kB Cache 2MB RAM.txt"),

            # Time units
            ("5min timer.txt", "5min Timer.txt"),
            ("2h workout.mp4", "2h Workout.mp4"),

            # Power and energy
            ("100w bulb.txt", "100W Bulb.txt"),
            ("5kwh usage.csv", "5kWh Usage.csv"),
            ("50mw power.pdf", "50mW Power.pdf"),
            ("100va ups.txt", "100VA UPS.txt"),
            ("5kva generator.pdf", "5kVA Generator.pdf"),
            ("1mva transformer.doc", "1MVA Transformer.doc"),

            # Frequency
            ("100hz tone.wav", "100Hz Tone.wav"),
            ("2.4ghz wifi.pdf", "2.4GHz Wi-Fi.pdf"),
            ("440hz a4 note.mp3", "440Hz A4 Note.mp3"),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_units_in_filenames(self):
        """Test handling of common units in filenames.

        Tests:
        1. Storage units (kB, MB, GB, TB)
        2. Frequencies in media files (kHz, MHz, GHz)
        3. Time (AM, PM)
        4. Mixed case variants
        """
        R = FileRenamer.CHAR_REPLACEMENTS  # Shorthand for readability
        test_cases = [
            # Storage units - most common in filenames
            ("5kb file.txt", "5kB File.txt"),
            ("2mb cache.dat", "2MB Cache.dat"),
            ("500gb drive.img", "500GB Drive.img"),
            ("2tb backup.zip", "2TB Backup.zip"),

            # Mixed case variants
            ("10KB test.txt", "10kB Test.txt"),
            ("5MB data.bin", "5MB Data.bin"),
            ("1TB drive.vhd", "1TB Drive.vhd"),

            # Multiple units in filename
            ("5gb ram 2tb drive.txt", "5GB RAM 2TB Drive.txt"),

            # Frequencies in media files
            ("48khz audio.wav", "48kHz Audio.wav"),
            ("2.4ghz recording.mp3", "2.4GHz Recording.mp3"),
            ("96khz 24bit.flac", "96kHz 24bit.flac"),

            # Time
            ("5pm meeting.txt", "5PM Meeting.txt"),
            ("9am alarm.mp3", "9AM Alarm.mp3"),
            ("recorded-2pm-5pm.wav", "Recorded-2PM-5PM.wav"),
            ("5l water.txt", "5L Water.txt"),
            ("500ml bottle.pdf", "500mL Bottle.pdf"),
            ("2kl tank.doc", "2kL Tank.doc"),
            ("100km walk.gpx", "100km Walk.gpx"),
            ("5m pole.txt", "5m Pole.txt"),
            ("50KM trail.kml", "50km Trail.kml"),
            ("80km/h limit.txt", f"80km{R['/']}h Limit.txt"),
            ("100KM/h max.pdf", f"100km{R['/']}h Max.pdf"),
            ("60km/hr speed.doc", f"60km{R['/']}hr Speed.doc"),
            ("30KM/hr zone.txt", f"30km{R['/']}hr Zone.txt"),
            ("10gb file.txt", "10GB File.txt"),
            ("100ω resistor.txt", "100Ω Resistor.txt"),  # Greek letter unit
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_abbreviations_and_units(self):
        """Test handling of abbreviations and units.

        Test cases include:
        1. Mixed abbreviations and units
        2. Abbreviations with units
        3. Units with abbreviations
        """
        test_cases = [
            # Mixed abbreviations and units
            ("song.flac vs song.mp3 vs song.wav", "Song.FLAC vs Song.MP3 vs Song.wav"), # trailing .wav is a file extension, would have been WAV if followed by text
            ("video 1080p 48khz dts.m4v", "Video 1080p 48kHz DTS.m4v"),

            # Mixed cases
            ("dr. smith md in ny on bbc.mp4", "Dr. Smith MD in NY on BBC.mp4"),
            ("6pm est fbi report on hbo.txt", "6PM EST FBI Report on HBO.txt"),
            ("ca-based ceo's irs audit.pdf", "CA-Based CEO's IRS Audit.pdf"),

            # Unit patterns
            ("5kb file.txt", "5kB File.txt"),
            ("2mb cache.dat", "2MB Cache.dat"),
            ("500gb drive.img", "500GB Drive.img"),
            ("10KB test.txt", "10kB Test.txt"),
            ("48khz audio.wav", "48kHz Audio.wav"),
            ("2.4ghz wifi.pdf", "2.4GHz Wi-Fi.pdf"),
            ("5pm meeting.txt", "5PM Meeting.txt"),
            ("9am alarm.mp3", "9AM Alarm.mp3"),
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

    def test_lowercase_words_after_triggers(self):
        """Test that lowercase words are capitalized after trigger characters."""
        R = FileRenamer.CHAR_REPLACEMENTS
        ellipsis = R['...']
        colon = R[':']
        lt = R['<']  # left angle bracket
        gt = R['>']  # right angle bracket
        qmark = R['?']
        test_cases = [
            # After period
            ('hello.the world', 'Hello. The World'),
            ('hello.the.world', 'Hello.The.World'),
            ('hello. the world', 'Hello. The World'),
            # After ellipsis
            (f'hello...the world', f'Hello{ellipsis} The World'),
            (f'hello... the world', f'Hello{ellipsis} The World'),
            # After opening brackets (with and without space)
            ('hello (the) world', 'Hello (The) World'),
            ('hello ( the ) world', 'Hello ( The ) World'),
            ('hello [the] world', 'Hello [The] World'),
            ('hello [ the ] world', 'Hello [ The ] World'),
            ('hello {the} world', 'Hello {The} World'),
            ('hello { the } world', 'Hello { The } World'),
            (f'hello <the> world', f'Hello {lt}The{gt} World'),
            (f'hello < the > world', f'Hello {lt}The{gt} World'),
            # After exclamation and colon
            ('hello!the world', 'Hello! The World'),
            ('hello! the world', 'Hello! The World'),
            (f'hello:the world', f'Hello{colon} The World'),
            (f'hello: the world', f'Hello{colon} The World'),
        ]
        for original, expected in test_cases:
            with self.subTest(original=original):
                result = self.renamer._clean_filename(original)
                self.assertEqual(result, expected)

    def test_numbers_with_words_and_dates(self):
        """Test handling of numbers followed by words and date formats.

        Tests:
        1. Numbers followed by words (should capitalize word)
        2. Numbers that could be confused with units
        3. Various date formats
        """
        R = FileRenamer.CHAR_REPLACEMENTS
        fslash = R['/']  # forward slash replacement

        test_cases = [
            # Numbers followed by words
            ("10web hosting.txt", "10Web Hosting.txt"),
            ("2smart solutions.pdf", "2Smart Solutions.pdf"),
            ("5minutes ago.txt", "5Minutes Ago.txt"),
            ("100years of history.doc", "100Years of History.doc"),

            # Could be confused with units but are words
            ("5market analysis.pdf", "5Market Analysis.pdf"),  # Not 5m
            ("2large boxes.txt", "2Large Boxes.txt"),  # Not 2L
            ("10great ideas.doc", "10Great Ideas.doc"),  # Not 10g

            # Date formats (testing different styles and separators)
            ("12jan2025 report.pdf", "12Jan2025 Report.pdf"),  # DMY no separator
            ("12-jan-2025 report.pdf", "12-Jan-2025 Report.pdf"),  # DMY with hyphens
            ("12.jan.2025 report.pdf", "12.Jan.2025 Report.pdf"),  # DMY with dots
            # Note: Forward slashes in dates currently use the replacement character.
            # TODO: Consider enhancing to detect valid dates and use dashes instead.
            ("12/jan/2025 report.pdf", f"12{fslash}Jan{fslash}2025 Report.pdf"),  # DMY with slashes->replacement
            ("2025jan12 report.pdf", "2025Jan12 Report.pdf"),  # YMD no separator
            ("jan12-2025 report.pdf", "Jan12-2025 Report.pdf"),  # MDY with partial hyphens
            ("25-jan-12 report.pdf", "25-Jan-12 Report.pdf"),  # DMY with 2-digit year
        ]

        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected,
                           f"\nInput:    {original!r}\n"
                           f"Expected: {expected!r}\n"
                           f"Got:      {result!r}")

if __name__ == '__main__':
    unittest.main()
