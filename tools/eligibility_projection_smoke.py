"""Synthetic central/feed/local smoke; no network, provider or private DB access.

python -m tools.eligibility_projection_smoke
All state/output lives in a new temporary directory and is removed on exit.
"""
import json
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.eligibility import ANALYSIS_POLICY, current_analysis
from src.core.models import GeminiResult, Notice
from src.core.storage import JsonStorage
from src.local_client.dashboard import DashboardData, notice_rows
from src.local_client.monitor import notice_badge
from src.local_client.seen import SeenStore
from src.local_client.sync import FeedClient, validate_pair
from src.pipeline import load_site_configs, run_pipeline
from tools.actions_support import stage_public


def main():
    now = datetime(2026, 11, 4, 3, tzinfo=timezone.utc)
    stamp = now.isoformat()
    base = 'https://example.test/'
    def notice(identity, **changes):
        value = Notice(notice_id=identity, source_id='khidi_business', institution='Synthetic',
            title=identity, url=base+identity, content_text='Synthetic participation notice',
            content_hash=identity, first_seen_at=stamp, last_seen_at=stamp, updated_at=stamp,
            gemini=GeminiResult(status='SUCCESS', relevant=True, category='IP',
                participation_type='partner', reason='Synthetic evidence', keywords=[],
                analyzed_content_hash=identity, analyzed_at=stamp, analysis_policy=ANALYSIS_POLICY))
        return replace(value, **changes)
    with tempfile.TemporaryDirectory(prefix='eligibility-smoke-') as folder:
        root = Path(folder)
        configs = load_site_configs()
        config = root/'sites.json'
        config.write_text(json.dumps({'sites': [dict(c, enabled=c['source_id']=='khidi_business')
                                                for c in configs]}), encoding='utf-8')
        store = JsonStorage(root/'state')
        cached = notice('cached')
        old = notice('old')
        old = replace(old, gemini=replace(old.gemini, analysis_policy='v1'))
        missing = notice('missing')
        missing = replace(missing, gemini=replace(missing.gemini, analysis_policy=None))
        denied = notice('denied')
        denied = replace(denied,title='청소 용역 계약',content_text='청소 용역 계약의 시설 청소 세부 작업 사항입니다.',gemini=replace(denied.gemini, relevant=False))
        expired = notice('expired', apply_end='2020-01-01', gemini=GeminiResult())
        store.save_notices([cached, old, missing, denied, expired])
        fresh = notice('new', gemini=GeminiResult())
        registry = Mock(results={}, errors={}, skipped=[])
        registry.run.return_value = [fresh]
        client = Mock()
        client.generate.return_value = json.dumps(dict(relevant=True, category='IP',
            participation_type='partner', reason='Synthetic evidence', keywords=[]))
        public = root/'public'
        def load_pair():
            feed = json.loads((public/'notices.json').read_text(encoding='utf-8'))
            metadata = json.loads((public/'metadata.json').read_text(encoding='utf-8'))
            validate_pair(feed, metadata)
            assert feed['schema_version'] == metadata['schema_version'] == 3
            assert {n['notice_id'] for n in feed['notices']} == {'cached','old','missing','new'}
            return feed, metadata
        with patch('src.pipeline.build_mvp_registry', return_value=registry):
            first = run_pipeline(client=client, config_path=config, storage=store,
                                 public_dir=public, clock=lambda:now)
            assert len(first.notices) == 6 and first.feed_count == 4
            assert client.generate.call_count == 0
            assert next(n for n in first.notices if n.notice_id=='new').gemini.status=='NOT_ANALYZED'
            feed, metadata = load_pair()
            assert [n['notice_id'] for n in feed['notices'] if n['is_new']] == ['new']
            sync = FeedClient(base, cache_dir=root/'cache', clock=lambda:now,
                transport=lambda url, timeout:(public/url.rsplit('/',1)[-1]).read_bytes())
            assert sync.sync().status == 'UPDATED'
            assert sync.sync().status == 'UNCHANGED'
            seen = SeenStore(root/'seen.json', base)
            row = next(n for n in feed['notices'] if n['is_new'])
            assert notice_badge(row, seen.mark(row)) == 'NEW'
            assert len(notice_rows(DashboardData(sync.load_cache(), ()))) == 4
            stage_public(store.data_dir, public, root/'stage-first')
            second = run_pipeline(client=client, config_path=config, storage=store,
                                  public_dir=public, clock=lambda:now+timedelta(minutes=1))
            assert len(second.notices) == len(store.load_notices()) == 6
            assert client.generate.call_count == 0
            feed, metadata = load_pair()
            assert not any(n['is_new'] for n in feed['notices'])
            assert sync.sync().status == 'UPDATED'
            assert sync.sync().status == 'UNCHANGED'
            stage_public(store.data_dir, public, root/'stage-second')
        assert load_site_configs() == configs
        print(json.dumps(dict(status='PASS', schema_version=3, eligible_count=metadata['notice_count'],
            history_count=6, first_run_calls=0, second_run_calls=0,
            new_transition=[True,False], local_sync='PASS', dashboard='PASS',
            publication='PASS', private_data_used=False, real_provider_calls=0)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
