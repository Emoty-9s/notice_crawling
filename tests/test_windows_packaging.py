"""Packaging adapter path behavior; existing local-client contracts unchanged."""

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.windows_entry import launch_arguments, entry


class WindowsPackagingTests(unittest.TestCase):
    def test_normal_launch_keeps_offline_ui_entry(self):
        with patch('tools.windows_entry.main', return_value=0) as main, patch('tools.windows_entry.smoke_check') as smoke:
            self.assertEqual(entry(['--cache', 'existing.json']), 0)
        main.assert_called_once_with(['--cache', 'existing.json'])
        smoke.assert_not_called()

    def test_smoke_mode_requires_explicit_feed_and_report(self):
        with patch('tools.windows_entry.smoke_check', return_value=0) as smoke, patch('tools.windows_entry.main') as main:
            self.assertEqual(entry(['--smoke-report', 'report.json', '--feed-url', 'https://example.test/']), 0)
        smoke.assert_called_once_with('report.json', 'https://example.test/')
        main.assert_not_called()

    def test_development_arguments_unchanged(self):
        args = ['--cache', 'relative.json', '--top-n', '1']
        with patch('sys.frozen', False, create=True):
            self.assertEqual(launch_arguments(args), args)

    def test_frozen_defaults_outside_bundle_without_creating_user_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='packaging-test-') as folder, patch('sys.frozen', True, create=True), patch.dict('os.environ', {'LOCALAPPDATA': folder}):
            args = launch_arguments([])
            home = Path(folder) / 'NoticeCrawling'
            self.assertEqual(args, ['--cache', str(home / 'cache' / 'snapshot.json'), '--db', str(home / 'performance.db')])
            self.assertFalse(home.exists())

    def test_explicit_paths_override_frozen_defaults_and_stay_relative(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--cache')
        parser.add_argument('--db')
        with patch('sys.frozen', True, create=True):
            result = parser.parse_args(launch_arguments(['--cache', 'existing.json', '--db', 'existing.db']))
        self.assertEqual((result.cache, result.db), ('existing.json', 'existing.db'))

    def test_fallback_uses_user_home_without_meipass_dependency(self):
        with patch('sys.frozen', True, create=True), patch.dict('os.environ', {}, clear=True), patch('pathlib.Path.home', return_value=Path('synthetic-home')):
            args = launch_arguments([])
        self.assertEqual(args[1], str(Path('synthetic-home') / 'AppData' / 'Local' / 'NoticeCrawling' / 'cache' / 'snapshot.json'))
