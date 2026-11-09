"""M12 network-free consumer and last-good cache acceptance tests."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError, URLError

from src.core.models import GeminiResult, Notice
from src.local_client.__main__ import main
from src.local_client.sync import FeedClient, MAX_DOWNLOAD_BYTES, SyncError, download, validate_pair
from src.renderer.feed import build_feed
from src.core.public_text import public_hash


BASE = 'https://example.test/project/'
STAMP = '2026-11-02T01:00:00Z'
SECRET = 'private-value-must-not-appear'


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


class LocalClientTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='local-client-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        notice = Notice(
            notice_id='n1', source_id='s1', institution='기관', title='공고', url='https://example.test/notice',
            content_hash='hash', content_text='공개 요약', first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
            gemini=GeminiResult(status='SUCCESS', analysis_policy='patent-firm-participation-v2', relevant=True, category='IP', participation_type='협력기관',
                                reason='참여 가능', keywords=['특허'], analyzed_content_hash='hash', analyzed_at=STAMP))
        self.feed = build_feed([notice], generated_at=STAMP)
        self.metadata = {'schema_version': 3, 'generated_at': STAMP, 'notice_count': 1}
        self.transport = Mock(side_effect=self.serve)
        self.client = FeedClient(BASE, cache_dir=self.root/'cache', timeout=7, transport=self.transport)
        # Any accidental real HTTP, including from central code, fails this suite.
        blocker = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def serve(self, url, timeout):
        self.assertEqual(timeout, 7)
        if url == BASE + 'metadata.json':
            return encoded(self.metadata)
        if url == BASE + 'notices.json':
            return encoded(self.feed)
        self.fail('unexpected URL')

    def seed(self):
        self.assertEqual(self.client.sync().status, 'UPDATED')
        self.transport.reset_mock()
        return self.client.cache_path.read_bytes()

    def test_download_metadata_then_feed_and_persist_producer_contract(self):
        result = self.client.sync()
        self.assertEqual(result.status, 'UPDATED')
        self.assertEqual(result.feed, self.feed)
        self.assertEqual(result.metadata, self.metadata)
        self.assertIsNone(result.error_code)
        self.assertEqual(self.transport.call_args_list, [call(BASE+'metadata.json', 7), call(BASE+'notices.json', 7)])
        snapshot = self.client.load_cache()
        self.assertEqual(snapshot, {'base_url': BASE, 'feed': self.feed, 'metadata': self.metadata})
        self.assertEqual({p.name for p in self.client.cache_path.parent.iterdir()}, {'snapshot.json'})
        self.assertIn('공고', self.client.cache_path.read_text(encoding='utf-8'))

    def test_same_feed_reception_is_unchanged_and_does_not_write(self):
        before = self.seed()
        with patch('src.local_client.sync._atomic_snapshot', side_effect=AssertionError('unexpected write')):
            self.assertEqual(self.client.sync().status, 'UNCHANGED')
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(self.client.cache_path.read_bytes(), before)

    def test_new_snapshot_replaces_old_and_new_instance_can_read_it(self):
        self.seed()
        self.feed['generated_at'] = self.metadata['generated_at'] = '2026-11-03T01:00:00Z'
        self.feed['notices'][0]['title'] = '수정 공고'
        self.feed['notices'][0]['public_content_hash']=public_hash(self.feed['notices'][0])
        self.assertEqual(self.client.sync().status, 'UPDATED')
        reader = FeedClient(BASE.rstrip('/'), cache_dir=self.client.cache_path.parent)
        self.assertEqual(reader.load_cache()['feed'], self.feed)

    def test_empty_feed_is_valid_and_replaces_nonempty_feed(self):
        self.seed()
        self.feed['notices'] = []
        self.metadata['notice_count'] = 0
        self.assertEqual(self.client.sync().feed['notices'], [])
        self.assertEqual(self.client.load_cache()['metadata']['notice_count'], 0)

    def test_ocr_feed_above_legacy_size_limit_syncs_without_truncation(self):
        # Leading JSON whitespace grows the payload without altering the schema
        # or its public hashes. The real expanded production feed is >16 MiB.
        payload = b' ' * (16 * 1024 * 1024 + 1) + encoded(self.feed)
        self.assertLess(len(payload), MAX_DOWNLOAD_BYTES)
        response = Mock()
        response.read.return_value = payload
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('src.local_client.sync.urlopen', return_value=response):
            self.assertEqual(download(BASE+'notices.json', 7), payload)
        self.transport.side_effect = [encoded(self.metadata), payload]
        result = self.client.sync()
        self.assertEqual(result.status, 'UPDATED')
        self.assertEqual(result.feed, self.feed)
        self.assertEqual(self.client.load_cache()['feed'], self.feed)

    def test_timeout_and_network_errors_fallback_to_last_good_cache(self):
        before = self.seed()
        for error, code in [(TimeoutError(SECRET), 'TIMEOUT'), (URLError(TimeoutError(SECRET)), 'TIMEOUT'),
                            (URLError(SECRET), 'NETWORK_ERROR'), (ConnectionError(SECRET), 'NETWORK_ERROR'),
                            (HTTPError(BASE, 503, SECRET, {}, None), 'NETWORK_ERROR'),
                            (IncompleteRead(b'partial response'), 'NETWORK_ERROR')]:
            self.transport.side_effect = error
            with self.subTest(code=code):
                result = self.client.sync()
                self.assertEqual((result.status, result.error_code), ('FALLBACK', code))
                self.assertEqual(result.feed, self.feed)
                self.assertNotIn(SECRET, repr(result))
                self.assertEqual(self.client.cache_path.read_bytes(), before)

    def test_network_error_without_cache_raises_and_does_not_initialize_empty_cache(self):
        self.transport.side_effect = TimeoutError(SECRET)
        with self.assertRaisesRegex(SyncError, '^TIMEOUT$'):
            self.client.sync()
        self.assertFalse(self.client.cache_path.parent.exists())

    def test_malformed_json_in_either_document_falls_back_without_changes(self):
        before = self.seed()
        malformed = [b'{', b'\xff', b'{"schema_version":1,"schema_version":1}', b'NaN', b'"\\ud800"']
        for filename in ('metadata.json', 'notices.json'):
            for raw in malformed:
                self.transport.side_effect = lambda url, timeout: raw if url.endswith(filename) else self.serve(url, timeout)
                with self.subTest(filename=filename, raw=raw):
                    result = self.client.sync()
                    self.assertEqual((result.status, result.error_code), ('FALLBACK', 'INVALID_JSON'))
                    self.assertEqual(self.client.cache_path.read_bytes(), before)

    def test_unsupported_schema_in_both_documents_including_bool_and_float(self):
        self.seed()
        for document in (self.feed, self.metadata):
            for version in (1, 4, True, 3.0, '3', None):
                document['schema_version'] = version
                with self.subTest(version=version):
                    result = self.client.sync()
                    self.assertEqual((result.status, result.error_code), ('FALLBACK', 'UNSUPPORTED_SCHEMA'))
            document['schema_version'] = 3

    def test_invalid_metadata_stops_before_feed_download(self):
        self.metadata['notice_count'] = True
        with self.assertRaisesRegex(SyncError, 'INVALID_FEED'):
            self.client.sync()
        self.assertEqual(self.transport.call_count, 1)
        self.assertFalse(self.client.cache_path.exists())

    def test_pair_timestamp_and_count_mismatch_preserve_cache(self):
        before = self.seed()
        for field, value in [('notice_count', 99), ('generated_at', '2026-11-03T01:00:00Z')]:
            original = self.metadata[field]
            self.metadata[field] = value
            self.assertEqual(self.client.sync().error_code, 'SNAPSHOT_MISMATCH')
            self.assertEqual(self.client.cache_path.read_bytes(), before)
            self.metadata[field] = original

    def test_record_validation_rejects_incomplete_private_duplicate_and_bad_types(self):
        for mutation in ('missing', 'private', 'duplicate', 'keywords', 'date', 'title', 'generated_at'):
            feed, metadata = copy.deepcopy(self.feed), dict(self.metadata)
            if mutation == 'missing':
                del feed['notices'][0]['summary']
            elif mutation == 'private':
                feed['notices'][0]['content_text'] = SECRET
            elif mutation == 'duplicate':
                feed['notices'].append(dict(feed['notices'][0]))
                metadata['notice_count'] = 2
            elif mutation == 'keywords':
                feed['notices'][0]['keywords'] = [True]
            elif mutation == 'date':
                feed['notices'][0]['published_at'] = 1
            elif mutation == 'title':
                feed['notices'][0]['title'] = ''
            else:
                feed['generated_at'] = metadata['generated_at'] = '2026-11-02'
            with self.subTest(mutation=mutation), self.assertRaises(SyncError):
                validate_pair(feed, metadata)

    def test_nullable_dates_empty_summary_and_empty_keywords_match_public_contract(self):
        self.feed['notices'][0].update(published_at=None,apply_start=None,apply_end=None,summary='')
        self.feed['notices'][0]['public_content_hash']=public_hash(self.feed['notices'][0])
        self.assertEqual(self.client.sync().status, 'UPDATED')

    def test_corrupt_cache_is_never_fallback_and_valid_download_repairs_it(self):
        self.client.cache_path.parent.mkdir()
        self.client.cache_path.write_bytes(b'{')
        self.transport.side_effect = TimeoutError()
        with self.assertRaises(SyncError):
            self.client.sync()
        self.assertEqual(self.client.cache_path.read_bytes(), b'{')
        self.transport.side_effect = self.serve
        self.assertEqual(self.client.sync().status, 'UPDATED')
        self.assertEqual(self.client.load_cache()['feed'], self.feed)

    def test_cache_from_another_feed_is_not_used_as_fallback(self):
        before = self.seed()
        other = FeedClient('https://example.test/other/', cache_dir=self.client.cache_path.parent,
                           transport=Mock(side_effect=TimeoutError()))
        with self.assertRaisesRegex(SyncError, '^TIMEOUT$'):
            other.sync()
        self.assertEqual(self.client.cache_path.read_bytes(), before)

    def test_partial_download_failure_never_commits_new_metadata(self):
        before = self.seed()
        self.metadata['generated_at'] = '2026-11-03T01:00:00Z'
        def partial(url, timeout):
            if url.endswith('notices.json'):
                raise TimeoutError()
            return self.serve(url, timeout)
        self.transport.side_effect = partial
        result = self.client.sync()
        self.assertEqual(result.metadata['generated_at'], STAMP)
        self.assertEqual(self.client.cache_path.read_bytes(), before)

    def test_atomic_fsync_and_replace_failures_preserve_entire_old_pair_and_clean_temp(self):
        before = self.seed()
        self.metadata['generated_at'] = self.feed['generated_at'] = '2026-11-03T01:00:00Z'
        for target in ('os.fsync', 'os.replace', 'tempfile.NamedTemporaryFile'):
            with self.subTest(target=target), patch('src.local_client.sync.'+target, side_effect=OSError(SECRET)):
                result = self.client.sync()
            self.assertEqual((result.status, result.error_code), ('FALLBACK', 'CACHE_WRITE_FAILED'))
            self.assertEqual(self.client.cache_path.read_bytes(), before)
            self.assertEqual(list(self.client.cache_path.parent.iterdir()), [self.client.cache_path])

    def test_atomic_replace_is_only_commit_point_with_complete_validated_pair(self):
        before = self.seed()
        self.metadata['generated_at'] = self.feed['generated_at'] = '2026-11-03T01:00:00Z'
        import os
        replace = os.replace
        def inspect(source, destination):
            self.assertEqual(self.client.cache_path.read_bytes(), before)
            candidate = json.loads(Path(source).read_text(encoding='utf-8'))
            validate_pair(candidate['feed'], candidate['metadata'])
            self.assertEqual(Path(source).parent, self.client.cache_path.parent)
            replace(source, destination)
        with patch('src.local_client.sync.os.replace', side_effect=inspect) as commit:
            self.assertEqual(self.client.sync().status, 'UPDATED')
        commit.assert_called_once()

    def test_partial_write_and_flush_failures_preserve_cache_and_clean_temp(self):
        before = self.seed()
        self.metadata['generated_at'] = self.feed['generated_at'] = '2026-11-03T01:00:00Z'
        factory = tempfile.NamedTemporaryFile
        for stage in ('write', 'flush'):
            @contextlib.contextmanager
            def failing_file(**kwargs):
                with factory(**kwargs) as actual:
                    proxy = Mock(wraps=actual)
                    proxy.name = actual.name
                    if stage == 'write':
                        def fail_write(text):
                            actual.write(text[:20])
                            raise OSError(SECRET)
                        proxy.write.side_effect = fail_write
                    else:
                        proxy.flush.side_effect = OSError(SECRET)
                    yield proxy
            with self.subTest(stage=stage), patch('src.local_client.sync.tempfile.NamedTemporaryFile', failing_file):
                result = self.client.sync()
            self.assertEqual(result.error_code, 'CACHE_WRITE_FAILED')
            self.assertEqual(self.client.cache_path.read_bytes(), before)
            self.assertEqual(list(self.client.cache_path.parent.iterdir()), [self.client.cache_path])

    def test_checked_in_initial_public_json_is_accepted(self):
        root = Path(__file__).resolve().parents[1]
        validate_pair(json.loads((root/'public/notices.json').read_text(encoding='utf-8')),
                      json.loads((root/'public/metadata.json').read_text(encoding='utf-8')))

    def test_write_failure_without_previous_cache_is_an_error(self):
        with patch('src.local_client.sync.os.replace', side_effect=OSError(SECRET)):
            with self.assertRaisesRegex(SyncError, '^CACHE_WRITE_FAILED$'):
                self.client.sync()
        self.assertFalse(self.client.cache_path.exists())
        self.assertEqual(list(self.client.cache_path.parent.iterdir()), [])

    def test_invalid_url_and_timeout_rejected_before_network(self):
        for url in ('file:///tmp/feed', 'https://user:pass@example.test/', 'https://example.test/?key=secret',
                    'https://example.test/#fragment', 'https://example.test:bad/', 'https://example.test/\n', ''):
            with self.subTest(url=url), self.assertRaisesRegex(SyncError, 'INVALID_BASE_URL'):
                FeedClient(url, transport=self.transport)
        for timeout in (0, -1, True, float('nan'), float('inf'), '1'):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(SyncError, 'INVALID_TIMEOUT'):
                FeedClient(BASE, timeout=timeout, transport=self.transport)
        self.transport.assert_not_called()

    def test_oversized_or_wrong_transport_response_falls_back(self):
        self.seed()
        for value, code in [(b' ' * (MAX_DOWNLOAD_BYTES+1), 'RESPONSE_TOO_LARGE'), ('{}', 'INVALID_RESPONSE')]:
            self.transport.side_effect = None
            self.transport.return_value = value
            self.assertEqual(self.client.sync().error_code, code)

    def test_default_transport_request_timeout_headers_and_read_limit(self):
        response = Mock()
        response.read.return_value = encoded(self.metadata)
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch('src.local_client.sync.urlopen', return_value=context) as open_url:
            self.assertEqual(download(BASE+'metadata.json', 7), encoded(self.metadata))
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, BASE+'metadata.json')
        self.assertEqual(request.get_header('Accept'), 'application/json')
        self.assertEqual(open_url.call_args.kwargs['timeout'], 7)
        response.read.assert_called_once_with(MAX_DOWNLOAD_BYTES+1)

    def test_cli_success_unchanged_fallback_and_no_cache_exit_codes_are_safe(self):
        args = ['--base-url', BASE, '--cache-dir', str(self.client.cache_path.parent), '--timeout', '7']
        for expected, status in ((0, 'UPDATED'), (0, 'UNCHANGED'), (1, 'FALLBACK')):
            if status == 'FALLBACK':
                self.transport.side_effect = TimeoutError(SECRET)
            with patch('src.local_client.sync.download', self.transport), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(args), expected)
            self.assertIn(status, out.getvalue())
            self.assertNotIn(SECRET, out.getvalue())
        with patch('src.local_client.sync.download', self.transport), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['--base-url', BASE, '--cache-dir', str(self.root/'empty')]), 2)
        self.assertNotIn(SECRET, out.getvalue())


if __name__ == '__main__':
    unittest.main()
