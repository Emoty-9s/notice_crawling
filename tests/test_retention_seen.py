"""History is preserved; NEW is a central-run flag, independent of local seen."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from src.core.models import Notice, GeminiResult
from src.core.eligibility import ANALYSIS_POLICY
from src.core.storage import JsonStorage
from src.local_client.monitor import notice_badge
from src.local_client.seen import SeenStore, SeenStateError
from src.local_client.sync import FeedClient, validate_pair
from src.pipeline import run_pipeline, MVP_SOURCES
from src.renderer.feed import build_feed

NOW = datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
STAMP = NOW.isoformat()
BASE = 'https://example.test/'

def notice(identity='n1', deadline=None):
    return Notice(notice_id=identity, source_id='khidi_business', institution='기관', title='공고',
                  url=BASE+identity, apply_end=deadline, content_hash='hash', content_text='공개 내용',
                  first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
                  gemini=GeminiResult(status='SUCCESS', relevant=True, category='IP',
                      participation_type='협력기관', reason='참여 가능', keywords=['특허'],
                      analyzed_content_hash='hash', analyzed_at=STAMP, analysis_policy=ANALYSIS_POLICY))

class HistoryTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)

    def pipeline(self, previous, collected):
        store=JsonStorage(self.root/'state');store.save_notices(previous)
        config=self.root/'sites.yaml'
        config.write_text(json.dumps({'sites':[dict(source_id=s,enabled=False) for s in MVP_SOURCES]}))
        registry=Mock(results={},errors={},skipped=[]);registry.run.return_value=collected
        client=Mock()
        with patch('src.pipeline.build_mvp_registry',return_value=registry):
            result=run_pipeline(client=client,config_path=config,storage=store,
                                public_dir=self.root/'public',clock=lambda:NOW)
        client.generate.assert_not_called()
        self.assertEqual(store.load_notices(),list(result.notices))
        return result

    def test_all_history_retained_even_disabled_and_expired_over_90_days(self):
        result=self.pipeline([notice('old','2020-01-01'),notice('today','2026-11-03'),notice('unknown')],[])
        self.assertEqual(len(result.notices),3);self.assertEqual(result.feed_count,2)

    def test_expired_new_preserved_without_ai_or_publication(self):
        result=self.pipeline([],[replace(notice(deadline='2020-01-01'),gemini=GeminiResult())])
        self.assertEqual(len(result.notices),1);self.assertEqual(len(result.observed),1)
        self.assertEqual(result.feed_count,0)

    def test_deadline_correction_preserves_identity(self):
        old=notice(deadline='2020-01-01')
        result=self.pipeline([old],[replace(old,apply_end='2027-01-01')])
        self.assertEqual(result.notices[0].notice_id,old.notice_id)
        self.assertEqual(result.feed_count,1)

    def test_cache_projection_does_not_delete_validated_producer_snapshot(self):
        feed=build_feed([notice('expired','2026-11-02'),notice('today','2026-11-03')],generated_at='2026-11-01T00:00:00Z')
        snapshot=dict(base_url=BASE,feed=feed,metadata=dict(schema_version=2,generated_at=feed['generated_at'],notice_count=2))
        client=FeedClient(BASE,cache_dir=self.root,clock=lambda:NOW)
        client.cache_path.write_text(json.dumps(snapshot),encoding='utf-8');before=client.cache_path.read_bytes()
        view=client.load_cache();validate_pair(view['feed'],view['metadata'])
        self.assertEqual([n['notice_id'] for n in view['feed']['notices']],['today'])
        self.assertEqual(client.cache_path.read_bytes(),before)

    def test_new_is_unaffected_by_user_ack_and_updated_has_no_badge(self):
        row=build_feed([notice()],generated_at=STAMP)['notices'][0]
        store=SeenStore(self.root/'seen.json',BASE)
        self.assertEqual(notice_badge(row,store.load()),'NEW')
        self.assertEqual(notice_badge(row,store.mark(row)),'NEW')
        row=build_feed([replace(notice(),status='UPDATED')],generated_at=STAMP)['notices'][0]
        self.assertEqual(notice_badge(row,{}),'EXISTING')

    def test_corrupt_seen_file_is_not_silently_overwritten(self):
        path=self.root/'seen.json';path.write_bytes(b'{bad')
        with self.assertRaises(SeenStateError):SeenStore(path,BASE).mark({'notice_id':'n','updated_at':STAMP})
        self.assertEqual(path.read_bytes(),b'{bad')
