"""Incremental acquisition, safe pagination and durable OCR recovery contracts."""
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import Mock,patch

from src.core.incremental import IncrementalCrawl,signature
from src.core.storage import JsonStorage,_atomic_json,StorageIOError
from src.core.extraction import Extractor,ExtractionQueue,Resource,INCOMPLETE
from src.core.normalizer import generate_content_hash
from src.scrapers._board import BoardScraper,NoticeLink,ParsedNotice
from src.scrapers.registry import ScraperRegistry
from src.scrapers.base import ScraperError
from src.pipeline import run_pipeline
from src.renderer.feed import build_feed
from src.local_client.sync import validate_pair

NOW=datetime(2026,11,13,3,tzinfo=timezone.utc)
OLD='2026-11-04T03:00:00Z'


def item(identity,published='2026-11-10',title='특허분석 수행기관 모집'):
    return NoticeLink(str(identity),title,f'https://unit.test/detail?id={identity}',published_at=published,apply_end='2026-11-30')


class PagesTransport:
    def __init__(self,pages,*,fail_detail=False):
        self.pages=pages;self.requests=[];self.fail_detail=fail_detail
    def get(self,url,**kwargs):
        from urllib.parse import parse_qs,urlsplit
        self.requests.append(url)
        if '/list' in url:
            page=int(parse_qs(urlsplit(url).query)['p'][0])
            return json.dumps(dict(items=[i.__dict__ for i in self.pages[page-1]],pages=list(range(1,len(self.pages)+1))))
        if self.fail_detail:raise ConnectionError('synthetic detail failure')
        return '특허분석 수행기관 모집. 참가 자격은 원문 확인. '+url


class PageScraper(BoardScraper):
    source='unit'
    def parse_list(self,response):
        return [NoticeLink(**row) for row in json.loads(response)['items']]
    def page_links(self,response):
        return [f'https://unit.test/list?p={p}' for p in json.loads(response)['pages']]
    def parse_detail(self,response,item):
        return ParsedNotice(item,response,'<p>'+response+'</p><img src="/poster.png">')


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def scraper(self,pages,*,source='unit',options=None,fail=False,now=NOW):
        adapter=type('TestSource',(PageScraper,),dict(source=source))
        config=dict(source_id=source,enabled=True,institution='검증 기관',list_url='https://unit.test/list?p=1',
                    pagination={'parameter':'p'},max_pages=3,http={'max_retries':0})
        if options is not None:config['incremental']=options
        transport=PagesTransport(pages,fail_detail=fail)
        return adapter(config,transport=transport,clock=lambda:now,logger=Mock())
    def saved(self,scraper,link,*,acquired=OLD):
        n=scraper.normalize(ParsedNotice(link,'저장된 특허분석 수행기관 모집 원문'))
        return replace(n,first_seen_at=acquired,last_seen_at=acquired,updated_at=acquired)
    def attach(self,scraper,history,state=None,now=NOW):
        if state is not None:_atomic_json(self.root/'crawl_state.json',state)
        coordinator=IncrementalCrawl(self.root,history,{},now)
        scraper.incremental=coordinator.for_source(scraper)
        return coordinator
    def state(self,source,entries,stamp=OLD):
        return dict(version=1,initial_baseline_date='2026-11-06',sources={source:dict(
            baseline_at=stamp,last_successful_crawl_at=stamp,notices=entries)})

    def test_pre_baseline_known_ids_do_not_fetch_details_or_enqueue_attachments(self):
        link=item(1,'2026-11-01');s=self.scraper([[link]])
        old=self.saved(s,link);s.extractor=ExtractionQueue()
        c=self.attach(s,[old]);result=s.run();c.commit({s.source_id:result})
        self.assertEqual(result,[old]);self.assertEqual(s.extractor.resources,{})
        self.assertEqual(s.incremental.metrics['detail_requests'],0)
        self.assertEqual(s.incremental.metrics['frozen_skipped'],1)
        self.assertEqual(s.transport.requests,['https://unit.test/list?p=1'])
        stored=json.loads((self.root/'crawl_state.json').read_text(encoding='utf-8'))['sources']['unit']
        self.assertEqual(stored['notices'][old.notice_id]['published_at'],'2026-11-01')
        self.assertEqual(stored['last_successful_crawl_at'],'2026-11-13T03:00:00Z')

    def test_unknown_old_publication_is_acquired_without_a_date_gate(self):
        old_link=item(1,'2026-11-01');late=item(2,'2020-01-01')
        s=self.scraper([[old_link,late]]);self.attach(s,[self.saved(s,old_link)])
        result=s.run()
        self.assertEqual({n.notice_id for n in result},{s.notice_id_for(old_link),s.notice_id_for(late)})
        self.assertEqual(s.incremental.metrics['detail_requests'],1)
        self.assertIn('/detail?id=2',s.transport.requests[-1])

    def test_old_publication_acquired_after_baseline_still_gets_recent_change_detection(self):
        link=item(1,'2020-01-01');s=self.scraper([[link]])
        old=self.saved(s,link,acquired='2026-11-12T00:00:00Z')
        self.attach(s,[old]);s.run()
        self.assertEqual(s.incremental.metrics['detail_requests'],1)
        self.assertEqual(s.incremental.metrics['frozen_skipped'],0)

    def test_baseline_boundary_is_kst_not_utc(self):
        s=self.scraper([[item(1)]])
        before=self.saved(s,item(1),acquired='2026-11-05T14:59:59Z')
        after=replace(before,first_seen_at='2026-11-05T15:00:00Z')
        self.attach(s,[before])
        self.assertTrue(s.incremental.frozen(before))
        self.assertFalse(s.incremental.frozen(after))

    def test_index_ahead_of_history_never_suppresses_an_unacquired_old_id(self):
        link=item(1,'2020-01-01');s=self.scraper([[link]])
        identity=s.notice_id_for(link)
        entries={identity:dict(published_at='2020-01-01',last_detail_checked_at='2026-11-13T02:59:00Z',list_signature=signature(link))}
        self.attach(s,[],self.state('unit',entries,stamp='2026-11-13T03:00:00Z'))
        s.run()
        self.assertEqual(s.incremental.metrics['new_notices'],1)
        self.assertEqual(s.incremental.metrics['detail_requests'],1)

    def test_new_ids_after_known_streak_on_same_page_are_not_missed(self):
        a,b=item(1,'2026-10-01'),item(2,'2026-09-01')
        s=self.scraper([[a,b]],options={'latest_first_verified':True,'consecutive_known':1})
        self.attach(s,[self.saved(s,a)])
        self.assertEqual(len(s.run()),2)
        self.assertFalse(s.incremental.early_stopped)
        self.assertEqual(s.incremental.metrics['new_notices'],1)

    def test_verified_newest_order_continues_new_notices_beyond_three_pages(self):
        links=[item(i,f'2026-11-{13-i:02d}') for i in range(1,5)]
        boundary=item(99,'2026-10-01')
        s=self.scraper([[n] for n in [*links,boundary,item(100,'2026-09-01')]],
                       options={'latest_first_verified':True,'consecutive_known':1})
        self.attach(s,[self.saved(s,boundary)])
        result=s.run()
        self.assertEqual(len(result),5)
        self.assertEqual(s.incremental.metrics['detail_requests'],4)
        self.assertEqual(s.incremental.metrics['list_pages'],5)
        self.assertTrue(s.incremental.early_stopped)
        self.assertNotIn('https://unit.test/list?p=6',s.transport.requests)

    def test_recent_seven_day_id_window_is_not_cut_short_by_known_streak(self):
        a,b=item(1,'2026-11-12'),item(2,'2026-11-11')
        late=item(3,'2026-11-07');boundary=item(4,'2026-10-30')
        s=self.scraper([[a],[b],[late],[boundary]],options={'latest_first_verified':True,'consecutive_known':1})
        self.attach(s,[self.saved(s,n) for n in (a,b,boundary)])
        result=s.run()
        self.assertEqual(len(result),4)
        self.assertEqual(s.incremental.metrics['new_notices'],1)
        self.assertEqual(s.incremental.metrics['list_pages'],4)

    def test_unverified_missing_or_unstable_dates_keep_existing_window(self):
        for options,pages in (({},[[item(i,None)] for i in range(1,5)]),
            ({'latest_first_verified':True},[[item(i,None)] for i in range(1,5)]),
            ({'latest_first_verified':True},[[item(1,'2026-10-01'),item(2,'2026-10-02')],[item(3,'2026-09-01')],[item(4,'2026-08-01')],[item(5,'2026-07-01')]])):
            with self.subTest(options=options,pages=pages):
                s=self.scraper(pages,options=options)
                self.attach(s,[self.saved(s,n) for page in pages for n in page])
                s.run()
                self.assertEqual(s.incremental.metrics['list_pages'],3)
                self.assertEqual(s.incremental.metrics['detail_requests'],0)
                self.assertFalse(s.incremental.early_stopped)

    def test_recent_metadata_changes_force_bounded_refresh_and_stable_id(self):
        before=item(1);after=replace(before,title='수정된 특허분석 수행기관 모집')
        s=self.scraper([[after]])
        old=self.saved(s,before,acquired='2026-11-10T00:00:00Z')
        entries={old.notice_id:dict(published_at=old.published_at,list_signature=signature(before),last_detail_checked_at='2026-11-13T02:59:00Z')}
        self.attach(s,[old],self.state('unit',entries))
        result=s.run()
        self.assertEqual(result[0].notice_id,old.notice_id)
        self.assertEqual(result[0].title,after.title)
        self.assertEqual(s.incremental.metrics['recent_rechecked'],1)

    def test_recent_refresh_limit_rotates_to_oldest_checks(self):
        links=[item(i) for i in range(5)]
        s=self.scraper([links],options={'recent_refresh_limit':2,'recent_refresh_hours':0})
        history=[self.saved(s,n,acquired='2026-11-10T00:00:00Z') for n in links]
        entries={n.notice_id:dict(published_at=n.published_at,list_signature=signature(i),last_detail_checked_at='2026-11-11T00:00:00Z') for n,i in zip(history,links)}
        c=self.attach(s,history,self.state('unit',entries));result=s.run();c.commit({'unit':result})
        self.assertEqual([u for u in s.transport.requests if '/detail' in u],[links[0].url,links[1].url])
        next_source=self.scraper([links],options={'recent_refresh_limit':2,'recent_refresh_hours':0},now=NOW+timedelta(hours=1))
        self.attach(next_source,history,now=NOW+timedelta(hours=1));next_source.run()
        self.assertEqual([u for u in next_source.transport.requests if '/detail' in u],[links[2].url,links[3].url])

    def test_failed_collection_and_page_limit_do_not_advance_success_cursor(self):
        s=self.scraper([[item(2)]],fail=True)
        initial=self.state('unit',{})
        c=self.attach(s,[],initial)
        with self.assertRaises(ScraperError):s.run()
        c.commit({})
        self.assertEqual(json.loads((self.root/'crawl_state.json').read_text(encoding='utf-8')),initial)
        s=self.scraper([[item(i,'2026-11-12')] for i in range(4)],options={'latest_first_verified':True,'max_pages':2})
        c=self.attach(s,[],initial);result=s.run();c.commit({'unit':result})
        stored=json.loads((self.root/'crawl_state.json').read_text(encoding='utf-8'))['sources']['unit']
        self.assertEqual(stored['last_successful_crawl_at'],OLD)
        self.assertFalse(stored['range_complete'])

    def test_corrupt_source_index_falls_back_only_for_affected_source(self):
        a=self.scraper([[item(1,'2026-10-01')]])
        b=self.scraper([[item(1,'2026-10-01')]],source='other')
        history=[self.saved(a,item(1,'2026-10-01')),self.saved(b,item(1,'2026-10-01'))]
        initial=self.state('unit',[])
        initial['sources']['other']=dict(baseline_at=OLD,last_successful_crawl_at=OLD,notices={})
        _atomic_json(self.root/'crawl_state.json',initial)
        c=IncrementalCrawl(self.root,history,{},NOW)
        for s in (a,b):s.incremental=c.for_source(s)
        results={s.source_id:s.run() for s in (a,b)};c.commit(results)
        self.assertEqual(a.incremental.metrics['mode'],'FULL_FALLBACK')
        self.assertEqual(a.incremental.metrics['detail_requests'],1)
        self.assertEqual(b.incremental.metrics['detail_requests'],0)
        self.assertTrue(list((self.root/'crawl_state_recovery').glob('*.json')))

    def test_bad_index_plus_source_network_failure_does_not_break_other_diagnostics(self):
        s=self.scraper([[item(1)]],fail=True)
        _atomic_json(self.root/'crawl_state.json',dict(version=1,initial_baseline_date='2026-11-06',sources={'unit':[]}))
        c=IncrementalCrawl(self.root,[],{},NOW);s.incremental=c.for_source(s)
        with self.assertRaises(ScraperError):s.run()
        c.commit({})
        self.assertEqual(c.diagnostics()['unit']['mode'],'FULL_FALLBACK')
        self.assertIsNone(c.diagnostics()['unit']['last_successful_crawl_at'])

    def test_identity_hook_error_uses_ordinary_collection_not_false_deduplication(self):
        s=self.scraper([[item(1)]])
        self.attach(s,[])
        with patch.object(s,'notice_id_for',side_effect=RuntimeError('incremental-only failure')):
            # Identity inference fails before fetching details. Normal fallback
            # still calls the adapter's ordinary normalization exactly once.
            result=s.run()
        self.assertEqual(len(result),1)
        self.assertEqual(s.incremental.metrics['mode'],'FULL_FALLBACK')

    def test_new_source_creates_its_own_first_success_baseline(self):
        s=self.scraper([[item(1,'2020-01-01')]],source='future_site_39')
        c=self.attach(s,[]);result=s.run();c.commit({s.source_id:result})
        value=json.loads((self.root/'crawl_state.json').read_text(encoding='utf-8'))['sources'][s.source_id]
        self.assertEqual(value['baseline_at'],'2026-11-13T03:00:00Z')
        self.assertIn(result[0].notice_id,value['notices'])

    def test_all_seven_adapters_share_the_same_pre_baseline_zero_detail_policy(self):
        from _site_cases import SPECS,fixture_context
        from _m16_cases import context
        for source in [*SPECS,'ripc_pms','kista_ippro']:
            with self.subTest(source=source):
                if source in SPECS:s,listing,*_=fixture_context(source)
                else:s,listing,*_=context(source)
                s.max_pages=1
                items=s.parse_list(listing)
                history=[replace(s.normalize(ParsedNotice(i,'저장된 특허분석 원문')),first_seen_at=OLD) for i in items]
                s.transport.get.side_effect=(['User-agent: *\nAllow: /',listing] if source in ('ripc_pms','kista_ippro') else [listing])
                c=IncrementalCrawl(self.root/source,history,{},NOW)
                s.incremental=c.for_source(s)
                self.assertEqual(len(s.run()),len(history))
                self.assertEqual(s.incremental.metrics['detail_requests'],0)

    def test_pipeline_interrupt_preserves_new_id_pending_job_then_skips_detail_on_restart(self):
        from _site_cases import CONFIGS
        store=JsonStorage(self.root/'data');path=self.root/'sites.json'
        configs=deepcopy(CONFIGS)
        for c in configs:c['enabled']=c['source_id']=='kipa_bid'
        path.write_text(json.dumps({'sites':configs}),encoding='utf-8')
        link=item(1,'2020-01-01')
        def registry():
            r=ScraperRegistry(logger=Mock());s=self.scraper([[link]],source='kipa_bid');r.register(s)
            return r,s
        r,s=registry()
        with patch('src.pipeline.build_mvp_registry',return_value=r),patch('src.core.extraction.Extractor.enrich',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                run_pipeline(config_path=path,storage=store,public_dir=self.root/'public',clock=lambda:NOW)
        saved=store.load_notices()[0]
        self.assertEqual(saved.extraction['status'],'PARTIAL')
        self.assertEqual(saved.extraction['resources'][0]['source_url'],'https://unit.test/poster.png')
        r,s=registry()
        with patch('src.pipeline.build_mvp_registry',return_value=r),patch('src.core.extraction.download',return_value=(b'png','poster.png')) as fetch,patch('src.core.extraction.Extractor.document',return_value=dict(status='SUCCESS',parts=[dict(status='SUCCESS',method='OCR',text='이미지 특허분석 수행기관 모집')])):
            result=run_pipeline(config_path=path,storage=store,public_dir=self.root/'public',clock=lambda:NOW+timedelta(hours=1))
        self.assertEqual(s.incremental.metrics['detail_requests'],0)
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(result.notices[0].extraction['status'],'SUCCESS')
        self.assertIn('이미지 특허분석',result.notices[0].content_text)
        feed=build_feed(result.notices,generated_at='2026-11-13T04:00:00Z')
        validate_pair(feed,dict(schema_version=3,generated_at=feed['generated_at'],notice_count=len(feed['notices'])))
        self.assertEqual(result.notices[0].notice_id,saved.notice_id)

    def test_successful_ocr_resources_are_reused_without_downloading_and_text_survives_deferral(self):
        from test_central_local_v3 import notice
        engine=Mock(side_effect=['보존할 기존 OCR 업무 근거',RuntimeError('failed')])
        fetch=Mock(side_effect=lambda r:(b'\x89PNG'+r.url.encode(),'poster.png'))
        e=Extractor(self.root/'ocr',ocr=engine,fetch=fetch)
        resources=[Resource('https://unit.test/a','a.png','image'),Resource('https://unit.test/b','b.png','image')]
        first=e.enrich(notice(),resources)
        e.deadline=0;fetch.reset_mock()
        second=e.enrich(notice(),resources,previous_resources=first.extraction['resources'],reuse_completed=True)
        fetch.assert_not_called()
        self.assertIn('보존할 기존 OCR 업무 근거',second.content_text)
        self.assertIn(INCOMPLETE,second.content_text)
        self.assertEqual(second.extraction['resources'][0]['status'],'SUCCESS')
        e.start_budget();engine.side_effect=None;engine.return_value='재시도된 두 번째 OCR 결과'
        third=e.enrich(notice(),resources,previous_resources=second.extraction['resources'],reuse_completed=True)
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.args[0].url,'https://unit.test/b')
        self.assertIn('보존할 기존 OCR 업무 근거',third.content_text)
        self.assertEqual(third.extraction['status'],'SUCCESS')

    def test_skipping_or_not_listing_history_never_removes_feed_or_ocr_results(self):
        from _site_cases import CONFIGS
        store=JsonStorage(self.root/'data');path=self.root/'sites.json'
        configs=deepcopy(CONFIGS)
        for c in configs:c['enabled']=c['source_id']=='kipa_bid'
        path.write_text(json.dumps({'sites':configs}),encoding='utf-8')
        links=[item(1,'2026-10-01'),item(2,'2026-10-01')]
        s=self.scraper([[links[0]]],source='kipa_bid')
        history=[replace(self.saved(s,i),extraction={'status':'SUCCESS','resources':[],
                     'original_text':'보존된 원문','original_hash':'saved'}) for i in links]
        store.save_notices(history)
        r=ScraperRegistry();r.register(s)
        with patch('src.pipeline.build_mvp_registry',return_value=r),patch('src.core.extraction.download',side_effect=AssertionError('no attachment request')):
            result=run_pipeline(config_path=path,storage=store,public_dir=self.root/'public',clock=lambda:NOW)
        self.assertEqual(s.incremental.metrics['detail_requests'],0)
        self.assertEqual({n.notice_id for n in result.notices},{n.notice_id for n in history})
        self.assertEqual(result.feed_count,2)
        for n in result.notices:
            prior=next(p for p in history if p.notice_id==n.notice_id)
            self.assertEqual((n.content_text,n.content_hash,n.extraction,n.gemini),(prior.content_text,prior.content_hash,prior.extraction,prior.gemini))
        hidden=next(n for n in result.notices if n.notice_id==history[1].notice_id)
        self.assertEqual(hidden.last_seen_at,history[1].last_seen_at)

    def test_notice_checkpoint_failure_cannot_advance_crawl_state(self):
        from _site_cases import CONFIGS
        store=JsonStorage(self.root/'data');path=self.root/'sites.json'
        configs=deepcopy(CONFIGS)
        for c in configs:c['enabled']=c['source_id']=='kipa_bid'
        path.write_text(json.dumps({'sites':configs}),encoding='utf-8')
        initial=self.state('kipa_bid',{})
        _atomic_json(store.data_dir/'crawl_state.json',initial)
        s=self.scraper([[item(1)]],source='kipa_bid');r=ScraperRegistry();r.register(s)
        with patch('src.pipeline.build_mvp_registry',return_value=r),patch.object(store,'save_notices',side_effect=StorageIOError('checkpoint failed')):
            with self.assertRaises(StorageIOError):
                run_pipeline(config_path=path,storage=store,public_dir=self.root/'public',clock=lambda:NOW)
        self.assertEqual(json.loads((store.data_dir/'crawl_state.json').read_text(encoding='utf-8')),initial)


if __name__=='__main__':unittest.main()
