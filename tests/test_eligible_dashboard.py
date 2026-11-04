"""Bounded collection and participation projection, with zero provider calls."""
import json
import unittest
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from src.ai.gemini import load_policy
from src.ai.relevance import RelevanceAnalyzer
from src.core.eligibility import ANALYSIS_POLICY, deadline_state, eligible_active_notices
from src.core.models import GeminiResult
from src.core.storage import JsonStorage
from src.pipeline import run_pipeline, load_site_configs, SUPPORTED_SOURCES
from src.local_client.monitor import notice_badge, ordered_notices, SOURCE_LIST_URLS, source_list_url
from src.renderer.feed import build_feed
from src.scrapers.pagination import MAX_COLLECTION_PAGES
from src.scrapers.registry import build_registry
from _site_cases import fixture_context, SPECS
from test_retention_seen import notice, NOW, STAMP

class EligibilityTests(unittest.TestCase):
    def test_date_boundaries_and_unknown_closure(self):
        for end,expected in [('2026-11-02','EXPIRED'),('2026-11-03','ACTIVE'),('2026-11-04','ACTIVE'),(None,'UNKNOWN'),('추후 안내','UNKNOWN')]:
            self.assertEqual(deadline_state(end,today=NOW),expected)
        self.assertEqual(deadline_state(None,title='접수 마감',today=NOW),'EXPIRED')
        self.assertEqual(deadline_state(None,content='접수 마감 후 결과 발표',today=NOW),'UNKNOWN')

    def test_incomplete_expired_old_policy_excluded(self):
        good=notice();bad=[replace(good,gemini=replace(good.gemini,status='PENDING')),
            replace(good,apply_end='2026-11-02'),replace(good,gemini=replace(good.gemini,analysis_policy=None))]
        self.assertEqual(eligible_active_notices([good,*bad],today=NOW),[good,bad[0],bad[2]])

    def test_policy_role_examples(self):
        policy=load_policy();self.assertEqual(policy['version'],2)
        self.assertTrue(any(e['relevant'] and e['participation_type']=='협력기관' for e in policy['examples']))
        self.assertTrue(any(not e['relevant'] and e['participation_type']=='수혜기업' for e in policy['examples']))
        for text in ('특허법인','입찰','수행기관','뉴스','행사','교육','수혜기업'):
            self.assertIn(text,' '.join(policy['rules']))

    def test_old_success_reanalyzed_and_current_policy_cached(self):
        old=replace(notice(),status='EXISTING',gemini=replace(notice().gemini,analysis_policy=None))
        client=Mock();client.generate.return_value=json.dumps(dict(relevant=False,category='지원사업',participation_type='수혜기업',reason='수혜기업 전용',keywords=[]))
        result=RelevanceAnalyzer(client,retry_existing=True,clock=lambda:NOW).analyze(old)
        self.assertFalse(result.gemini.relevant);self.assertEqual(result.gemini.analysis_policy,ANALYSIS_POLICY)
        self.assertEqual(len(build_feed([result],generated_at=STAMP)['notices']),1)
        self.assertEqual(RelevanceAnalyzer(client,retry_existing=True).analyze(result),result)
        self.assertEqual(client.generate.call_count,1)

    def test_old_and_missing_policy_success_both_require_reanalysis(self):
        for policy in (None, 'patent-firm-participation-v1'):
            with self.subTest(policy=policy):
                old = replace(notice(), status='EXISTING',
                              gemini=replace(notice().gemini, analysis_policy=policy))
                client = Mock()
                client.generate.return_value = json.dumps(dict(relevant=True, category='IP',
                    participation_type='협력기관', reason='참여 가능', keywords=[]))
                analyzer = RelevanceAnalyzer(client, retry_existing=True, clock=lambda: NOW)
                result = analyzer.analyze(old)
                self.assertEqual(result.gemini.analysis_policy, ANALYSIS_POLICY)
                self.assertEqual(analyzer.analyze(result), result)
                client.generate.assert_called_once()

    def test_new_existing_updated_and_deadline_sort(self):
        records=[notice('new','2027-01-01'),replace(notice('soon','2026-11-03'),status='EXISTING'),replace(notice('unknown'),status='UPDATED')]
        rows=ordered_notices(build_feed(records,generated_at=STAMP)['notices'])
        self.assertEqual([n['notice_id'] for n in rows],['new','soon','unknown'])
        self.assertEqual([notice_badge(n) for n in rows],['NEW','EXISTING','EXISTING'])

    def test_source_links_equal_canonical_config(self):
        configs={c['source_id']:c for c in load_site_configs()}
        self.assertEqual(set(SOURCE_LIST_URLS),set(SUPPORTED_SOURCES))
        for source in SOURCE_LIST_URLS:self.assertEqual(source_list_url(source),configs[source]['list_url'])
        self.assertIsNone(source_list_url('evil'))

    def test_queue_priority_budget_and_expired_history(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            root=Path(root);store=JsonStorage(root/'state')
            previous=[replace(notice('backlog'),gemini=GeminiResult()),replace(notice('updated'),gemini=GeminiResult()),notice('expired','2020-01-01')]
            store.save_notices(previous)
            config=root/'sites.json';config.write_text(json.dumps({'sites':[dict(c,enabled=c['source_id']=='khidi_business') for c in load_site_configs()]}))
            registry=Mock(results={},errors={},skipped=[])
            registry.run.return_value=[replace(notice('new'),gemini=GeminiResult()),replace(previous[1],content_hash='updated')]
            client=Mock();client.generate.return_value=json.dumps(dict(relevant=True,category='IP',participation_type='협력기관',reason='참여 가능',keywords=[]))
            with patch('src.pipeline.build_mvp_registry',return_value=registry):
                result=run_pipeline(client=client,config_path=config,storage=store,public_dir=root/'public',clock=lambda:NOW,analysis_max_calls=2)
            self.assertEqual([n.gemini.status for n in result.observed],['NOT_ANALYZED','NOT_ANALYZED'])
            self.assertEqual(client.generate.call_count,0);self.assertEqual(len(result.notices),4)
            self.assertEqual(next(n for n in result.notices if n.notice_id=='backlog').gemini.status,'NOT_ANALYZED')

    def test_active_unanalyzed_precedes_unknown_backlog_and_expired_never_calls(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            store = JsonStorage(root/'state')
            store.save_notices([replace(notice('a-backlog'), gemini=GeminiResult()),
                                replace(notice('z-active', '2026-11-04'), gemini=GeminiResult()),
                                replace(notice('expired', '2020-01-01'), gemini=GeminiResult())])
            config = root/'sites.json'
            config.write_text(json.dumps({'sites': [dict(c, enabled=c['source_id']=='khidi_business')
                                                    for c in load_site_configs()]}))
            registry = Mock(results={}, errors={}, skipped=[])
            registry.run.return_value = []
            client = Mock()
            client.generate.return_value = json.dumps(dict(relevant=True, category='IP',
                participation_type='협력기관', reason='참여 가능', keywords=[]))
            with patch('src.pipeline.build_mvp_registry', return_value=registry):
                result = run_pipeline(client=client, config_path=config, storage=store,
                    public_dir=root/'public', clock=lambda:NOW, analysis_max_calls=1)
            client.generate.assert_not_called()
            records = {n.notice_id:n for n in result.notices}
            self.assertEqual(records['z-active'].gemini.status, 'NOT_ANALYZED')
            self.assertEqual(records['a-backlog'].gemini.status, 'NOT_ANALYZED')
            self.assertEqual(records['expired'].gemini.status, 'NOT_ANALYZED')
            self.assertEqual(result.feed_count, 3)  # Closed rows remain available for local date overrides.

class PaginationTests(unittest.TestCase):
    def test_seven_share_cap(self):
        configs=[dict(c,enabled=c['source_id'] in SUPPORTED_SOURCES,max_pages=20) for c in load_site_configs()]
        registry=build_registry(configs)
        active=[s for s in registry._scrapers.values() if s.enabled]
        self.assertEqual(len(active),7)
        for scraper in active:self.assertEqual(scraper.max_pages,MAX_COLLECTION_PAGES)

    def test_observed_pages_one_two_three_cap_and_duplicate_ids(self):
        for source in SPECS:
            for count in (1,2,3,5):
                with self.subTest(source=source,count=count):
                    scraper,listing,*_=fixture_context(source)
                    param=scraper.config['pagination']['parameter']
                    links=[u for u in scraper.page_links(listing)
                           if int(parse_qs(urlsplit(u).query)[param][0]) > (0 if param=='pager.offset' else 1)]
                    self.assertTrue(links)
                    scraper.page_links=Mock(return_value=links[:max(0,count-1)])
                    scraper.request_text=Mock(return_value=listing)
                    pages=scraper.fetch_list()
                    self.assertEqual(len(pages),min(count,MAX_COLLECTION_PAGES))
                    self.assertEqual(len(scraper._parse_items(pages)),len(scraper.parse_list(listing)))

    def test_page_failure_does_not_return_partial_source(self):
        scraper,listing,*_=fixture_context('khidi_business')
        scraper.request_text=Mock(side_effect=[listing,TimeoutError()])
        with self.assertRaises(TimeoutError):scraper.fetch_list()
