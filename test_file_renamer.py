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
        """Test replacement of special characters."""
        test_cases = [
            (r'file\with:special*chars?.txt', 'File⧵withːSpecial✱Chars❓.txt'),
            ('file|with"pipes<and>symbols.txt', 'File│with"Pipes❬and❭Symbols.txt'),
            ('file\nwith\ttabs.txt', 'File with Tabs.txt'),
        ]
        
        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected)

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

    def test_multiple_spaces_and_punctuation(self):
        """Test handling of multiple spaces and punctuation."""
        test_cases = [
            ('multiple   spaces.txt', 'Multiple Spaces.txt'),
            ('trailing spaces  .txt', 'Trailing Spaces.txt'),
            ('multiple!!!!!.txt', 'Multiple.txt'),
            ('trailing.periods....txt', 'Trailing Periods.txt'),
            ('mixed!!!...!!!...txt', 'Mixed.txt'),
        ]
        
        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected)

    def test_real_world_examples(self):
        """Test with real-world example filenames."""
        test_cases = [
            (
                'Future Coach 2023-09-08 Eben\n 2024-08-22_07-59-48.mkv',
                'Future Coach 2023-09-08 Eben 2024-08-22_07-59-48.mkv'
            ),
            (
                'Law of Attraction Secrets: How to Manifest Anything You Want Faster Than Ever!.mp4',
                'Law of Attraction SecretsːHow to Manifest Anything You Want Faster than Ever.mp4'
            ),
            (
                'Make So Much Money You Question It! - Get Ahead Of 99% Of People & Win At Anything | Alex Hormozi.mp4',
                'Make so Much Money You Question It - Get Ahead of 99% of People and Win at Anything │ Alex Hormozi.mp4'
            ),
        ]
        
        for original, expected in test_cases:
            result = self.renamer._clean_filename(original)
            self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
