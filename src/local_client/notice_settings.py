"""Local notice preferences and KST display deadlines; no company DB or AI I/O."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

from src.core.eligibility import deadline_date
from src.core.retention import retention_date
from .seen import seen_path
from .sync import FeedClient, SyncError, _parse, _atomic_snapshot, _stamp

AUTO_CLOSE_DAYS = 21
_WRITE_LOCK = threading.RLock()

class NoticeSettingsError(ValueError):
    pass

def settings_path(cache_path):
    return seen_path(cache_path).with_suffix('.notice-settings.json')

def effective_deadline(notice, preference=None, *, today=None):
    """Explicit deadline days are inclusive. Automatic day +21 closes at 00 KST."""
    preference=preference or {}
    for field,source in ((preference.get('user_deadline'),'USER'),(notice.get('apply_end'),'OFFICIAL')):
        end=deadline_date(field)
        if end is not None:
            return dict(date=end.isoformat(),source=source,state='EXPIRED' if retention_date(today)>end else 'ACTIVE')
    for field,source in ((notice.get('published_at'),'PUBLISHED_PLUS_21'),(notice.get('first_seen_at'),'FIRST_SEEN_PLUS_21')):
        start=deadline_date(field)
        if start is not None:
            try: end=start+timedelta(days=AUTO_CLOSE_DAYS)
            except OverflowError: continue
            return dict(date=end.isoformat(),source=source,state='EXPIRED' if retention_date(today)>=end else 'ACTIVE')
    return dict(date=None,source='UNKNOWN_DATE',state='UNKNOWN_DATE')

def in_view(notice, preference, work_result, *, view='현재 공고', include_excluded=False, today=None):
    from .work_opportunity import is_displayable
    deleted=preference.get('deleted_from_list',False)
    if view=='삭제한 공고': return deleted
    if deleted: return False
    if not include_excluded and not is_displayable(work_result): return False
    closed=effective_deadline(notice,preference,today=today)['state']=='EXPIRED'
    return closed if view=='마감된 공고' else not closed

class NoticeSettingsStore:
    def __init__(self,path,base_url,*,protected_paths=()):
        self.path=Path(path)
        self.origin=FeedClient(base_url).base_url
        if self.path.resolve() in {Path(p).resolve() for p in protected_paths}:
            raise NoticeSettingsError('NOTICE_SETTINGS_PATH_COLLISION')

    def _document(self):
        try: raw=self.path.read_bytes()
        except FileNotFoundError:return dict(schema_version=1,origins={})
        except OSError:raise NoticeSettingsError('NOTICE_SETTINGS_READ_FAILED') from None
        try:
            doc=_parse(raw)
            if not isinstance(doc,dict) or set(doc)!={'schema_version','origins'} or type(doc['schema_version']) is not int or doc['schema_version']!=1 or not isinstance(doc['origins'],dict):raise ValueError()
            for origin,rows in doc['origins'].items():
                if FeedClient(origin).base_url!=origin or not isinstance(rows,dict):raise ValueError()
                for key,row in rows.items():
                    if not isinstance(key,str) or not key.strip() or not isinstance(row,dict) or set(row)!={'notice_id','user_deadline','deleted_from_list','updated_at'}:raise ValueError()
                    if row['notice_id']!=key or type(row['deleted_from_list']) is not bool:raise ValueError()
                    end=row['user_deadline']
                    if end is not None and (not isinstance(end,str) or deadline_date(end) is None or deadline_date(end).isoformat()!=end):raise ValueError()
                    _stamp(row['updated_at'])
            return doc
        except (ValueError,TypeError,SyncError):raise NoticeSettingsError('INVALID_NOTICE_SETTINGS') from None

    def load(self):
        with _WRITE_LOCK:return dict(self._document()['origins'].get(self.origin,{}))

    def update(self,notice_id,**changes):
        if not isinstance(notice_id,str) or not notice_id.strip() or not changes or set(changes)-{'user_deadline','deleted_from_list'}:raise NoticeSettingsError('INVALID_NOTICE_SETTING')
        if 'user_deadline' in changes:
            value=changes['user_deadline']
            if value is not None and (not isinstance(value,str) or deadline_date(value) is None or deadline_date(value).isoformat()!=value):raise NoticeSettingsError('INVALID_USER_DEADLINE')
        if 'deleted_from_list' in changes and type(changes['deleted_from_list']) is not bool:raise NoticeSettingsError('INVALID_NOTICE_SETTING')
        with _WRITE_LOCK:
            doc=self._document();rows=doc['origins'].setdefault(self.origin,{})
            row=rows.get(notice_id,dict(notice_id=notice_id,user_deadline=None,deleted_from_list=False,updated_at=''))
            rows[notice_id]={**row,**changes,'updated_at':datetime.now(timezone.utc).isoformat()}
            try:_atomic_snapshot(self.path,doc)
            except SyncError:raise NoticeSettingsError('NOTICE_SETTINGS_WRITE_FAILED') from None
            return dict(rows)
