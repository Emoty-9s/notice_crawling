import copy
import json
import tempfile
import unittest
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from src.local_client.notice_settings import (effective_deadline,in_view,NoticeSettingsStore,
                                             NoticeSettingsError,settings_path)
from src.local_client.sync import FeedClient,SyncError
from src.local_client.monitor import read_local,sync_monitor

BASE='https://example.test/'
WORK=dict(status='HIGH',display=True,actual_work='특허분석',provider_evidence='수행기관 모집')

class DeadlineTests(unittest.TestCase):
    def test_all_sources_and_future_sources_share_day20_day21_boundary(self):
        from src.local_client.monitor import SOURCE_LIST_URLS
        for source in (*SOURCE_LIST_URLS,'future_institution'):
            for text in ('특허분석 용역','특허분석 상시모집'):
                n=dict(source_id=source,title=text,published_at='2026-10-01',first_seen_at='2026-10-10T00:00:00Z')
                self.assertEqual(effective_deadline(n,today=date(2026,10,21)),dict(date='2026-10-22',source='PUBLISHED_PLUS_21',state='ACTIVE'))
                self.assertEqual(effective_deadline(n,today=date(2026,10,22))['state'],'EXPIRED')

    def test_user_official_published_first_seen_priority_and_clear(self):
        n=dict(apply_end='2026-10-30',published_at='2026-10-01',first_seen_at='2026-10-10T00:00:00Z')
        self.assertEqual(effective_deadline(n,dict(user_deadline='2027-01-01'),today=date(2026,11,1))['source'],'USER')
        self.assertEqual(effective_deadline(n,dict(user_deadline=None),today=date(2026,11,1))['source'],'OFFICIAL')
        n['apply_end']='상시모집'
        self.assertEqual(effective_deadline(n,today=date(2026,10,1))['source'],'PUBLISHED_PLUS_21')
        n['published_at']=None
        self.assertEqual(effective_deadline(n,today=date(2026,10,31)),dict(date='2026-10-31',source='FIRST_SEEN_PLUS_21',state='EXPIRED'))

    def test_kst_midnight_and_timestamp_date_basis(self):
        n=dict(first_seen_at='2026-09-30T15:00:00Z')
        self.assertEqual(effective_deadline(n,today=datetime(2026,10,21,14,59,59,tzinfo=timezone.utc))['state'],'ACTIVE')
        self.assertEqual(effective_deadline(n,today=datetime(2026,10,21,15,tzinfo=timezone.utc))['state'],'EXPIRED')
        self.assertEqual(effective_deadline(n,today=date(2026,10,1))['date'],'2026-10-22')

    def test_explicit_date_is_inclusive_and_extends_expired_official(self):
        n=dict(apply_end='2020-01-01')
        self.assertEqual(effective_deadline(n,dict(user_deadline='2026-11-04'),today=date(2026,11,4))['state'],'ACTIVE')
        self.assertEqual(effective_deadline(n,dict(user_deadline='2026-11-04'),today=date(2026,11,5))['state'],'EXPIRED')

    def test_unknown_invalid_dates_do_not_invent_basis(self):
        n=dict(apply_end='추후 안내',published_at='2026-02-30',first_seen_at='invalid')
        self.assertEqual(effective_deadline(n),dict(date=None,source='UNKNOWN_DATE',state='UNKNOWN_DATE'))

    def test_views_delete_precedence_and_no_ai_promotion(self):
        n=dict(apply_end='2020-01-01')
        self.assertFalse(in_view(n,{},WORK))
        self.assertTrue(in_view(n,{},WORK,view='마감된 공고'))
        pref=dict(user_deadline='2099-01-01',deleted_from_list=True)
        self.assertFalse(in_view(n,pref,WORK));self.assertFalse(in_view(n,pref,WORK,view='마감된 공고'))
        self.assertTrue(in_view(n,pref,{},view='삭제한 공고'))
        pref['deleted_from_list']=False
        self.assertTrue(in_view(n,pref,WORK))
        self.assertFalse(in_view(n,pref,dict(status='EXCLUDE',score=1.0)))
        self.assertTrue(in_view(n,pref,{},include_excluded=True))

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'notice-settings.json';self.store=NoticeSettingsStore(self.path,BASE)

    def test_read_does_not_create_db_or_file_and_only_settings_are_written(self):
        with patch('sqlite3.connect',side_effect=AssertionError('No company DB')):
            self.assertEqual(self.store.load(),{});self.assertFalse(self.path.exists())
            row=self.store.update('n',user_deadline='2026-12-31')['n']
        self.assertEqual(set(row),{'notice_id','user_deadline','deleted_from_list','updated_at'})
        self.assertEqual(row['notice_id'],'n')

    def test_edit_clear_delete_restore_restart_and_other_ids_preserved(self):
        self.store.update('n',user_deadline='2026-12-01');self.store.update('other',deleted_from_list=True)
        self.store.update('n',deleted_from_list=True)
        other=NoticeSettingsStore(self.path,BASE)
        self.assertEqual(other.load()['n']['user_deadline'],'2026-12-01')
        other.update('n',user_deadline='2027-01-01');other.update('n',deleted_from_list=False)
        self.assertEqual(self.store.load()['n']['user_deadline'],'2027-01-01')
        self.store.update('n',user_deadline=None)
        self.assertIsNone(other.load()['n']['user_deadline']);self.assertTrue(other.load()['other']['deleted_from_list'])

    def test_invalid_or_corrupt_state_never_overwrites(self):
        for value in ('2026-02-30','20261104','2026-11-04T00:00:00Z','',1):
            with self.assertRaises(NoticeSettingsError):self.store.update('n',user_deadline=value)
        self.path.write_bytes(b'{broken')
        with self.assertRaises(NoticeSettingsError):self.store.update('n',deleted_from_list=True)
        self.assertEqual(self.path.read_bytes(),b'{broken')

    def test_failed_atomic_replace_preserves_old_file(self):
        self.store.update('n',user_deadline='2026-12-01');before=self.path.read_bytes()
        with patch('src.local_client.sync.os.replace',side_effect=OSError('synthetic')):
            with self.assertRaises(NoticeSettingsError):self.store.update('n',deleted_from_list=True)
        self.assertEqual(self.path.read_bytes(),before)

    def test_origin_isolation_and_repeated_store_writes_merge(self):
        other=NoticeSettingsStore(self.path,'https://other.test/')
        self.store.update('n',deleted_from_list=True);other.update('n',user_deadline='2099-01-01')
        self.assertTrue(self.store.load()['n']['deleted_from_list'])
        self.assertFalse(other.load()['n']['deleted_from_list'])

    def test_database_path_collision_is_rejected(self):
        with self.assertRaises(NoticeSettingsError):NoticeSettingsStore(self.path,BASE,protected_paths=[self.path])
        cache=self.path.with_name('snapshot.json');db=settings_path(cache)
        self.assertIsNone(read_local(cache,db,BASE))
        self.assertEqual(sync_monitor(BASE,cache,db,transport=lambda *_:self.fail('no network')).error_code,'PATH_COLLISION')

    def test_feed_sync_preserves_expired_and_preferences(self):
        from test_central_local_v3 import notice,STAMP
        from src.renderer.feed import build_feed
        from dataclasses import replace
        old=notice(apply_end='2020-01-01',published_at='2020-01-01')
        feed=build_feed([old],generated_at=STAMP);meta=dict(schema_version=3,generated_at=STAMP,notice_count=1)
        self.assertEqual(len(feed['notices']),1)
        responses={'notices.json':feed,'metadata.json':meta}
        client=FeedClient(BASE,cache_dir=self.path.parent,transport=lambda url,_:json.dumps(responses[url.rsplit('/',1)[1]]).encode())
        prefs=self.store.update('n',user_deadline='2099-01-01',deleted_from_list=True)
        before=self.path.read_bytes();first=client.sync();second=client.sync()
        self.assertEqual((first.status,second.status),('UPDATED','UNCHANGED'))
        self.assertEqual(client.load_cache()['feed']['notices'][0]['apply_end'],'2020-01-01')
        responses['notices.json']=build_feed([replace(old,updated_at=STAMP,title='변경 특허분석 용역')],generated_at=STAMP)
        client.sync();self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(self.store.load()['n']['deleted_from_list'])
