"""M11 offline deployment boundary and JSON-syntax YAML workflow checks."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.core.models import GeminiResult, Notice
from src.core.storage import JsonStorage
from src.renderer.feed import write_feed
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
            gemini=GeminiResult(status='SUCCESS', relevant=True, category='IP', participation_type='입찰 참여자',
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
                with self.assertRaises(ActionsCheckError) as error:
                    preflight(self.config, environ=env)
                self.assertNotIn(SECRET, str(error.exception))

    def test_stage_only_allowlisted_pair_matching_saved_snapshot(self):
        self.save()
        (self.public/'.env').write_text(SECRET, encoding='utf-8')
        (self.public/'private-state.json').write_text(SECRET, encoding='utf-8')
        metadata = stage_public(self.store.data_dir, self.public, self.stage)
        self.assertEqual(metadata['notice_count'], 1)
        self.assertEqual({p.name for p in self.stage.iterdir()}, {'notices.json', 'metadata.json'})
        text = (self.stage/'notices.json').read_text(encoding='utf-8')
        self.assertNotIn(SECRET, text)
        self.assertNotIn('content_text', text)

    def test_empty_snapshot_is_valid_publication(self):
        self.save([])
        self.assertEqual(stage_public(self.store.data_dir, self.public, self.stage)['notice_count'], 0)

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
        for mutation in ('extra', 'stale'):
            modified = json.loads(json.dumps(original))
            if mutation == 'extra':
                modified['notices'][0]['content_text'] = SECRET
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
        self.assertFalse(any('pip install' in step.get('run', '') for step in self.steps))

    def test_token_permissions_and_secret_scope(self):
        jobs = self.workflow['jobs']
        self.assertEqual(jobs['build']['permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertEqual(jobs['deploy']['permissions']['pages'], 'write')
        self.assertEqual(jobs['deploy']['permissions']['id-token'], 'write')
        self.assertNotIn('GEMINI_API_KEY', self.workflow['env'])
        secret_steps = [s for s in self.steps if 'GEMINI_API_KEY' in s.get('env', {})]
        self.assertEqual(len(secret_steps), 2)
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
        self.assertEqual(set(state['with']['path'].splitlines()), {'.run/data/notices.json', '.run/data/scraper_status.json'})
        self.assertEqual(state['with']['retention-days'], 90)
        self.assertIs(state['with']['include-hidden-files'], True)
        diagnostics_step = next(s for s in self.steps if s.get('with', {}).get('path') == '.actions-diagnostics.json')
        self.assertIs(diagnostics_step['with']['include-hidden-files'], True)
        self.assertEqual(self.workflow['jobs']['deploy']['needs'], 'build')
        self.assertEqual(self.workflow['jobs']['deploy']['environment']['name'], 'github-pages')


if __name__ == '__main__':
    unittest.main()
