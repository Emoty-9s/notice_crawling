import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError,URLError
from urllib.request import Request

from tests.test_exportvoucher_notice import Response
from tools.exportvoucher_diagnostics import RequestAudit,error_metadata


class AuditTests(unittest.TestCase):
    def test_pacing_spans_sessions_and_metadata_never_contains_tokens_or_payload(self):
        clock=[10.]
        sleeps=[]
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0]+=seconds
        events=[]
        audit=RequestAudit(events,interval=5,clock=lambda:clock[0],sleep=sleep)
        request=Request('https://www.exportvoucher.com/common.FileDownload.do?file_id=FILE_1&sec_code=SECRET_CODE',
                        headers={'Cookie':'SECRET_COOKIE'})
        for _ in range(2):
            response=Response(b'PRIVATE_BODY',request.full_url,'application/pdf')
            response.status=200
            opener=Mock()
            opener.open.return_value=response
            with audit.wrap(opener).open(request,timeout=15) as r:
                self.assertEqual(r.read1(100),b'PRIVATE_BODY')
        self.assertEqual(sleeps,[5.])
        self.assertEqual([e['session'] for e in events],[1,2])
        self.assertEqual([e['logical_request'] for e in events],[1,1])
        self.assertEqual([e['response_bytes'] for e in events],[12,12])
        self.assertTrue(all(e['http_status']==200 and e['status']=='SUCCESS' and not e['connection_reused'] for e in events))
        serialized=json.dumps(events)
        for secret in ('SECRET_CODE','SECRET_COOKIE','PRIVATE_BODY','FILE_1'):
            self.assertNotIn(secret,serialized)

    def test_connect_failure_and_http_status_record_retry_without_error_url(self):
        events=[]
        audit=RequestAudit(events)
        opener=Mock()
        opener.open.side_effect=[URLError(ConnectionResetError(104,'reset SECRET_COOKIE')),
            HTTPError('https://test/?sec_code=SECRET_CODE',403,'SECRET_BODY',{},None)]
        traced=audit.wrap(opener)
        request=Request('https://www.exportvoucher.com/common/File2List?docId=DOC_1')
        for _ in range(2):
            with self.assertRaises(URLError): traced.open(request,timeout=25)
        self.assertEqual([e['retry_count'] for e in events],[0,1])
        self.assertEqual([e['http_status'] for e in events],[None,403])
        self.assertEqual(events[0]['error_category'],'CONNECTION_RESET')
        self.assertEqual(events[0]['phase'],'connect_or_tls')
        self.assertNotIn('SECRET',json.dumps(events))

    def test_read_failure_is_separate_from_tls_and_partial_bytes_preserved(self):
        events=[]
        response=Mock(status=200)
        response.read1.side_effect=[b'abc',TimeoutError('PRIVATE_CONTENT')]
        response.headers.get_content_type.return_value='application/pdf'
        opener=Mock()
        opener.open.return_value=response
        with self.assertRaises(TimeoutError):
            with RequestAudit(events).wrap(opener).open(Request('https://www.exportvoucher.com/common.FileDownload.do'),timeout=15) as r:
                r.read1(3)
                r.read1(3)
        self.assertEqual(events[0]['http_status'],200)
        self.assertEqual(events[0]['phase'],'body')
        self.assertEqual(events[0]['response_bytes'],3)
        self.assertNotIn('PRIVATE_CONTENT',json.dumps(events))
        self.assertEqual(error_metadata(URLError('_ssl.c:1018: The handshake operation timed out'))['error_category'],
                         'TLS_HANDSHAKE_TIMEOUT')
