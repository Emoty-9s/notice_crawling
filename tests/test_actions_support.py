"""M11 offline deployment boundary and JSON-syntax YAML workflow checks."""

import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from src.core.models import GeminiResult, Notice
from src.core.diff import DiffConflictError
from src.core.storage import JsonStorage, StorageFormatError
from src.renderer.feed import write_feed
from src.renderer.source_status import validate_source_status
from tools.actions_support import ActionsCheckError, diagnostics, main, preflight, stage_public, validate_state


ROOT = Path(__file__).resolve().parents[1]
STAMP = '2026-10-30T07:00:00Z'
SECRET = 'fake-secret-must-never-appear'


class ActionsSupportTests(unittest.TestCase):
    def setUp(self):
        tests_root = ROOT/'tests'
        temp = tempfile.TemporaryDirectory(dir=tests_root, prefix='actions-test-')
        self.root = Path(temp.name).resolve()
        if self.root.parent != tests_root or not self.root.name.startswith('actions-test-'):
            raise RuntimeError('unexpected cleanup target')
        self.addCleanup(temp.cleanup)
        self.store = JsonStorage(self.root/'data')
        self.public = self.root/'public'
        self.stage = self.root/'pages'
        self.config = self.root/'sites.yaml'
        self.settings = json.loads((ROOT/'config/sites.yaml').read_text(encoding='utf-8'))
        for site in self.settings['sites']:
            site['enabled'] = site['source_id'] == 'kipa_bid'
        self.config.write_text(json.dumps(self.settings), encoding='utf-8')
        self.env = {'GEMINI_API_KEY': SECRET, 'GEMINI_MODEL': 'explicit-model'}
        self.notice = Notice(
            notice_id='one', source_id='kipa_bid', institution='한국발명진흥회', title='특허 용역 입찰',
            url='https://example.test/1', content_text='본문 ' * 200, content_hash='hash',
            first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
            gemini=GeminiResult(status='SUCCESS', analysis_policy='patent-firm-participation-v2', relevant=True, category='IP', participation_type='입찰 참여자',
                                keywords=['특허'], reason='수행 주체 참여 가능', analyzed_content_hash='hash', analyzed_at=STAMP))

    def save(self, notices=None):
        notices = [self.notice] if notices is None else notices
        self.store.save_notices(notices)
        self.store.save_scraper_status({'kipa_bid': {'status': 'SUCCESS', 'notices_found': len(notices)}})
        write_feed(notices, generated_at=STAMP, output_dir=self.public)

    def test_preflight_only_supported_enabled_site_and_environment_presence(self):
        report = preflight(self.config, environ=self.env)
        self.assertEqual(report, {'enabled_sites': 1, 'configuration': 'READY'})
        self.assertNotIn(SECRET, repr(report))

    def test_disabled_configuration_is_actionable(self):
        for site in self.settings['sites']:
            site['enabled'] = False
        self.config.write_text(json.dumps(self.settings), encoding='utf-8')
        with self.assertRaisesRegex(ActionsCheckError, 'NO_ENABLED_SITES'):
            preflight(self.config, environ=self.env)

    def test_missing_or_invalid_secrets_are_not_echoed(self):
        for env in ({}, {**self.env, 'GEMINI_API_KEY': SECRET+'\n'},
                    {**self.env, 'GEMINI_MODEL': '../'+SECRET}):
            with self.subTest(env_fields=list(env)):
                report=preflight(self.config,environ=env)
                self.assertEqual(report['configuration'],'READY')
                self.assertNotIn(SECRET,repr(report))

    def test_stage_only_allowlisted_pair_and_minimal_health_matching_saved_snapshot(self):
        self.save()
        (self.public/'.env').write_text(SECRET, encoding='utf-8')
        (self.public/'private-state.json').write_text(SECRET, encoding='utf-8')
        metadata = stage_public(self.store.data_dir, self.public, self.stage)
        self.assertEqual(metadata['notice_count'], 1)
        self.assertEqual({p.name for p in self.stage.iterdir()}, {'index.html', 'notices.json', 'metadata.json', 'source_status.json'})
        index = (self.stage/'index.html').read_text(encoding='utf-8')
        self.assertIn('href="notices.json"', index)
        self.assertIn('href="metadata.json"', index)
        self.assertNotIn(SECRET, index)
        text = (self.stage/'notices.json').read_text(encoding='utf-8')
        self.assertNotIn(SECRET, text)
        self.assertIn('content_text', text)
        self.assertNotIn('gemini',text)

    def test_empty_snapshot_is_valid_publication(self):
        self.save([])
        self.assertEqual(stage_public(self.store.data_dir, self.public, self.stage)['notice_count'], 0)

    def test_public_health_does_not_copy_private_state_errors_or_unknown_sources(self):
        self.save()
        self.store.save_scraper_status({
            'kipa_bid': dict(status='ERROR', last_attempt_at=STAMP, notices_found=0,
                             error_type=SECRET, error_message=SECRET),
            'not-public': dict(status='ERROR', error_message=SECRET),
        })
        stage_public(self.store.data_dir, self.public, self.stage)
        text = (self.stage/'source_status.json').read_text(encoding='utf-8')
        self.assertNotIn(SECRET, text)
        self.assertNotIn('not-public', text)
        doc = validate_source_status(json.loads(text))
        row = next(r for r in doc['sources'] if r['source_id'] == 'kipa_bid')
        self.assertEqual(row, dict(source_id='kipa_bid', status='ERROR', checked_at=STAMP, notices_found=0))

    def test_inconsistent_count_timestamp_or_schema_blocks_publication(self):
        self.save()
        original = json.loads((self.public/'metadata.json').read_text(encoding='utf-8'))
        for change in ({'notice_count': 9}, {'generated_at': '2000-01-01T00:00:00Z'},
                       {'schema_version': True}, {'notice_count': True}):
            (self.public/'metadata.json').write_text(json.dumps({**original, **change}), encoding='utf-8')
            with self.subTest(change=change), self.assertRaises(ActionsCheckError):
                stage_public(self.store.data_dir, self.public, self.stage)
            self.assertFalse(self.stage.exists())

    def test_stale_or_extra_private_content_in_public_feed_is_rejected(self):
        self.save()
        original = json.loads((self.public/'notices.json').read_text(encoding='utf-8'))
        for mutation in ('extra', 'stale', 'integer_new'):
            modified = json.loads(json.dumps(original))
            if mutation == 'extra':
                modified['notices'][0]['content_text'] = SECRET
            elif mutation == 'integer_new':
                modified['notices'][0]['is_new'] = int(modified['notices'][0]['is_new'])
            else:
                modified['notices'] = []
            (self.public/'notices.json').write_text(json.dumps(modified), encoding='utf-8')
            with self.subTest(mutation=mutation), self.assertRaises(ActionsCheckError):
                stage_public(self.store.data_dir, self.public, self.stage)

    def test_incomplete_state_or_feed_not_silently_initialized(self):
        with self.assertRaises(ActionsCheckError):
            validate_state(self.store.data_dir)
        self.assertFalse(self.store.data_dir.exists())
        self.save()
        (self.public/'metadata.json').unlink()
        with self.assertRaises(ActionsCheckError):
            stage_public(self.store.data_dir, self.public, self.stage)

    def test_dirty_stage_not_reused(self):
        self.save()
        self.stage.mkdir()
        (self.stage/'.env').write_text(SECRET, encoding='utf-8')
        with self.assertRaisesRegex(ActionsCheckError, 'STAGE_EXISTS'):
            stage_public(self.store.data_dir, self.public, self.stage)
        self.assertEqual((self.stage/'.env').read_text(encoding='utf-8'), SECRET)

    def test_diagnostics_omit_raw_messages_environment_and_bodies(self):
        self.save()
        self.store.save_scraper_status({'kipa_bid': {'status': 'ERROR', 'error_message': SECRET}})
        report = diagnostics(self.store.data_dir)
        self.assertEqual(report['state'], 'VALID')
        self.assertNotIn(SECRET, repr(report))
        self.assertNotIn('error_message', repr(report))
        self.assertNotIn(self.notice.title, repr(report))
        self.assertEqual(report['analysis_counts']['SUCCESS'], 1)

    def test_invalid_diagnostics_still_available_and_cli_errors_sanitized(self):
        self.assertEqual(diagnostics(self.store.data_dir)['state'], 'MISSING_OR_INVALID')
        self.store.data_dir.mkdir()
        self.store.notices_path.write_text(SECRET, encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()) as console:
            code = main(['validate-state', '--data-dir', str(self.store.data_dir)])
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET, console.getvalue())

    def test_corrupt_restored_state_blocks_staging_without_reset(self):
        self.save()
        corrupt = '{"credential": "' + SECRET + '"'
        self.store.notices_path.write_text(corrupt, encoding='utf-8')
        report = diagnostics(self.store.data_dir)
        self.assertEqual(report['check'], 'StorageFormatError')
        self.assertNotIn(SECRET, repr(report))
        with self.assertRaises(StorageFormatError):
            stage_public(self.store.data_dir, self.public, self.stage)
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.store.notices_path.read_text(encoding='utf-8'), corrupt)

    def test_duplicate_restored_identity_blocks_publication(self):
        self.save()
        record = json.loads(self.store.notices_path.read_text(encoding='utf-8'))[0]
        self.store.notices_path.write_text(json.dumps([record, record]), encoding='utf-8')
        with self.assertRaises(DiffConflictError):
            stage_public(self.store.data_dir, self.public, self.stage)
        self.assertFalse(self.stage.exists())

    def test_diagnostics_unknown_exception_never_exposes_dynamic_name_or_message(self):
        unsafe_error = type(SECRET, (Exception,), {})
        with patch('tools.actions_support.validate_state', side_effect=unsafe_error(SECRET)):
            report = diagnostics(self.store.data_dir)
        self.assertEqual(report['check'], 'VALIDATION_ERROR')
        self.assertNotIn(SECRET, repr(report))

    def test_stage_cli_and_diagnostics_use_temporary_paths_without_network(self):
        self.save()
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')):
            for command in ('validate-state', 'stage', 'diagnostics'):
                with self.subTest(command=command), contextlib.redirect_stdout(io.StringIO()) as console:
                    code = main([command, '--data-dir', str(self.store.data_dir),
                                 '--public-dir', str(self.public), '--stage-dir', str(self.stage)])
                self.assertEqual(code, 0)
                self.assertNotIn(SECRET, console.getvalue())
                self.assertIsInstance(json.loads(console.getvalue()), dict)


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # JSON syntax is a YAML 1.2 subset. No third-party YAML parser needed.
        cls.workflow = json.loads((ROOT/'.github/workflows/central-notice-pages.yml').read_text(encoding='utf-8'))
        cls.steps = cls.workflow['jobs']['build']['steps']

    def test_daily_dispatch_serial_default_branch_and_python_contract(self):
        self.assertEqual(self.workflow['on']['schedule'], [{'cron': '17 22 * * *'}])
        self.assertIs(self.workflow['on']['workflow_dispatch']['inputs']['bootstrap_state']['default'], False)
        self.assertIs(self.workflow['concurrency']['cancel-in-progress'], False)
        self.assertIn('default_branch', self.workflow['jobs']['build']['if'])
        setup = next(s for s in self.steps if s.get('uses', '').startswith('actions/setup-python@'))
        self.assertEqual(setup['with']['python-version'], '3.13')
        install = next(s for s in self.steps if 'pip install' in s.get('run', ''))
        self.assertIn('requirements-ocr.txt',install['run'])
        self.assertIn('tesseract-ocr-kor',install['run'])
        self.assertIn('tesseract-ocr-eng',install['run'])

    def test_token_permissions_and_secret_scope(self):
        jobs = self.workflow['jobs']
        self.assertEqual(jobs['build']['permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertEqual(jobs['deploy']['permissions']['pages'], 'write')
        self.assertEqual(jobs['deploy']['permissions']['id-token'], 'write')
        self.assertNotIn('GEMINI_API_KEY', self.workflow['env'])
        secret_steps = [s for s in self.steps if 'GEMINI_API_KEY' in s.get('env', {})]
        self.assertEqual(len(secret_steps), 0)
        self.assertTrue(all(s['env']['GEMINI_API_KEY'] == '${{ secrets.GEMINI_API_KEY }}' for s in secret_steps))

    def test_state_restore_before_pipeline_and_no_silent_cold_start(self):
        selected = next(s for s in self.steps if s.get('id') == 'state')
        self.assertIn('STATE_MISSING', selected['with']['script'])
        self.assertIn('STATE_EXPIRED', selected['with']['script'])
        self.assertIn('head_repository_id', selected['with']['script'])
        restore = next(s for s in self.steps if s.get('uses', '').startswith('actions/download-artifact@'))
        run = next(s for s in self.steps if s.get('id') == 'pipeline')
        self.assertLess(self.steps.index(restore), self.steps.index(run))
        self.assertIn('python -m src.main', run['run'])
        self.assertIn('"$code" -gt 1', run['run'])
        self.assertNotIn('continue-on-error', run)

    def test_validated_state_and_pages_paths_and_deploy_dependency(self):
        stage = next(s for s in self.steps if s.get('run') == 'python -m tools.actions_support stage')
        pages = next(s for s in self.steps if s.get('uses', '').startswith('actions/upload-pages-artifact@'))
        self.assertEqual(pages['with']['path'], '.run/pages')
        self.assertLess(self.steps.index(stage), self.steps.index(pages))
        state = next(s for s in self.steps if s.get('with', {}).get('name') == 'central-state-v1')
        self.assertEqual(set(state['with']['path'].splitlines()), {'.run/data/notices.json', '.run/data/scraper_status.json', '.run/data/analysis_diagnostics.json', '.run/data/ocr_cache', '.run/data/ocr_diagnostics.json'})
        self.assertIn('always()',state['if'])
        self.assertIn('checkpoint.outputs.valid',state['if'])
        self.assertEqual(state['with']['retention-days'], 90)
        self.assertIs(state['with']['include-hidden-files'], True)
        diagnostics_step = next(s for s in self.steps if s.get('with', {}).get('path') == '.actions-diagnostics.json')
        self.assertIs(diagnostics_step['with']['include-hidden-files'], True)
        self.assertEqual(self.workflow['jobs']['deploy']['needs'], 'build')
        self.assertEqual(self.workflow['jobs']['deploy']['environment']['name'], 'github-pages')

    def test_deployed_urls_are_recorded_from_actual_pages_output(self):
        steps = self.workflow['jobs']['deploy']['steps']
        report = next(s for s in steps if s.get('env', {}).get('PAGE_URL'))
        self.assertEqual(report['env']['PAGE_URL'], '${{ steps.deployment.outputs.page_url }}')
        self.assertIn('notices.json metadata.json', report['run'])
        self.assertIn('GITHUB_STEP_SUMMARY', report['run'])
        self.assertNotIn('${{', report['run'])


if __name__ == '__main__':
    unittest.main()
