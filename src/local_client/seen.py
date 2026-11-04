"""User-local acknowledgements, independent of central Notice/Gemini status."""
from pathlib import Path
from hashlib import sha256

from .sync import FeedClient, SyncError, _parse, _atomic_snapshot, _stamp


class SeenStateError(ValueError):
    pass


class SeenStore:
    def __init__(self, path, base_url):
        self.path = Path(path)
        self.origin = FeedClient(base_url).base_url

    def _document(self):
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return {'schema_version': 1, 'origins': {}}
        except OSError:
            raise SeenStateError('SEEN_READ_FAILED') from None
        try:
            doc = _parse(raw)
            if (not isinstance(doc, dict) or set(doc) != {'schema_version', 'origins'}
                    or type(doc['schema_version']) is not int or doc['schema_version'] != 1
                    or not isinstance(doc['origins'], dict)):
                raise ValueError()
            for origin, records in doc['origins'].items():
                if FeedClient(origin).base_url != origin or not isinstance(records, dict):
                    raise ValueError()
                for notice_id, version in records.items():
                    if not isinstance(notice_id, str) or not notice_id.strip():
                        raise ValueError()
                    _stamp(version)
            return doc
        except (ValueError, TypeError, SyncError):
            raise SeenStateError('INVALID_SEEN_STATE') from None

    def load(self):
        return dict(self._document()['origins'].get(self.origin, {}))

    def mark(self, notice):
        doc = self._document()  # Never silently overwrite an unreadable file.
        records = doc['origins'].setdefault(self.origin, {})
        records[notice['notice_id']] = notice['updated_at']
        try:
            _stamp(notice['updated_at'])
            _atomic_snapshot(self.path, doc)
        except SyncError:
            raise SeenStateError('SEEN_WRITE_FAILED') from None
        return dict(records)


def seen_path(cache_path):
    cache = Path(cache_path)
    # A custom shared cache directory must not share acknowledgements between
    # OS users. Hash the local profile path; never store/send the profile name.
    profile = sha256(str(Path.home()).casefold().encode('utf-8')).hexdigest()[:16]
    return cache.with_name(cache.name + '.' + profile + '.seen.json')
