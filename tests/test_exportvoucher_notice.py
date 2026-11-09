import io
import json
import tempfile
import unittest
from datetime import datetime,timezone
from email.message import Message
from pathlib import Path
from unittest.mock import Mock,patch

from src.core.extraction import Extractor,Resource,discover,INCOMPLETE
from src.scrapers.exportvoucher_notice import (ExportVoucherScraper,ExportVoucherSession,
    PublicAttachment,parse_file_list,attachment_groups,validate_attachment,notice_url,LIST)
from src.scrapers._html import StructureError

ROOT=Path(__file__).parent/'fixtures/exportvoucher_notice'
def read(name): return (ROOT/name).read_text(encoding='utf-8')
def scraper(transport=None):
    return ExportVoucherScraper(dict(source_id='exportvoucher_notice',institution='수출바우처',
        list_url=LIST,enabled=True,pagination={'parameter':'pageNo'}),transport=transport,
        clock=lambda:datetime(2026,11,9,tzinfo=timezone.utc))
def sample(s,identity='13038'):
    return next(i for i in s.parse_list(read('list1.html')) if i.source_notice_id==identity)
def parsed_sample():
    transport=Mock()
    transport.get.side_effect=[read('detail-13038.html'),read('files-13038.json')]
    s=scraper(transport)
    item=sample(s)
    parsed=s.parse_detail(s.fetch_detail(item),item)
    return s.normalize(parsed),discover(parsed.body_html,item.url)

class Response(io.BytesIO):
    def __init__(self,data,url,content_type):
        super().__init__(data)
        self.url=url
        self.headers=Message()
        self.headers['Content-Type']=content_type


class ExportVoucherTests(unittest.TestCase):
    def test_real_pages_and_pinned_notice_dedup_preserve_notice_identity(self):
        s=scraper(Mock())
        pages=[read(f'list{i}.html') for i in (1,2,3)]
        self.assertEqual([len(s.parse_list(p)) for p in pages],[14,14,14])
        self.assertNotEqual({i.source_notice_id for i in s.parse_list(pages[0])},
                            {i.source_notice_id for i in s.parse_list(pages[1])})
        self.assertEqual(len(s._parse_items(pages)),34)
        s.transport.get.side_effect=pages
        self.assertEqual(len(s.fetch_list()),3)
        self.assertEqual(s.transport.get.call_args_list[1].args[0],LIST+'&pageNo=2')
        n,resources=parsed_sample()
        self.assertEqual(n.notice_id,s.notice_id_for(sample(s)))
        self.assertEqual(len(resources),2)
        self.assertTrue(resources[0].name.endswith('.hwp'))
        self.assertNotIn('sec_code',resources[0].url)
        self.assertNotIn('FileDownload',n.content_text)

    def test_actual_no_widget_is_no_attachment_but_empty_group_is_failure(self):
        s=scraper(Mock())
        item=sample(s,'13047')
        s.transport.get.return_value=read('detail-13047.html')
        parsed=s.parse_detail(s.fetch_detail(item),item)
        self.assertEqual(s.attachment_results['13047'],[])
        self.assertEqual(s.transport.get.call_count,1)
        self.assertEqual(attachment_groups(read('detail-13047.html')),[])
        self.assertEqual(s.parse_attachments('<a href="/policy.pdf">global policy</a>'),[])
        s.transport.get.side_effect=[read('detail-13038.html'),'[]']
        with self.assertRaises(StructureError): s.fetch_detail(sample(s))
        with self.assertRaises(StructureError): s.parse_detail(read('detail-13038.html'),sample(s))

    def test_file_metadata_and_live_token_do_not_change_durable_resource_identity(self):
        first=parse_file_list(read('files-13038.json'))
        data=json.loads(read('files-13038.json'))
        for item in data: item['secCode']='freshCode'
        second=parse_file_list(json.dumps(data))
        self.assertEqual([f.resource_url for f in first],[f.resource_url for f in second])
        self.assertNotEqual(first[0].download_url,second[0].download_url)
        for invalid in ('[]','<html>error</html>','{}',json.dumps([dict(data[0],fileSize=0)]),
                        json.dumps([dict(data[0],fileId='../../private')])):
            with self.subTest(invalid=invalid[:40]),self.assertRaises(StructureError): parse_file_list(invalid)

    def test_download_reopens_public_context_and_reproduces_ajax_on_same_opener(self):
        n,resources=parsed_sample()
        payload=b'%PDF-1.7\npublic bytes'
        rows=[dict(json.loads(read('files-13038.json'))[1],fileSize=len(payload))]
        file=parse_file_list(json.dumps(rows))[0]
        opener=Mock()
        opener.open.side_effect=[Response(read('detail-13038.html').encode(),n.url,'text/html;charset=utf-8'),
            Response(json.dumps(rows).encode(), 'https://www.exportvoucher.com/common/File2List?docId=DOC_000000003940343','application/json'),
            Response(payload,file.download_url,'application/octet-stream')]
        client=ExportVoucherSession(opener=opener)
        data,name=client.download(resources[1],notice=n)
        self.assertEqual(data,payload)
        self.assertEqual(name,file.name)
        calls=opener.open.call_args_list
        api_request=calls[1].args[0]
        self.assertEqual(api_request.get_header('X-requested-with'),'XMLHttpRequest')
        self.assertEqual(api_request.get_header('Referer'),n.url)
        self.assertEqual(calls[2].args[0].full_url,file.download_url)
        self.assertIsNone(api_request.get_header('Authorization'))

    def test_empty_html_wrong_signature_and_size_are_never_download_success(self):
        for data,name,content_type,size in [(b'','a.pdf','application/pdf',1),
            (b'<html>error</html>','a.hwp','application/octet-stream',18),
            (b'%PDF-1.7','a.pdf','text/html',8),(b'not a pdf','a.pdf','application/pdf',9),
            (b'%PDF-1.7','a.pdf','application/pdf',100)]:
            with self.subTest(name=name,data=data),self.assertRaises(ValueError):
                validate_attachment(data,name,content_type,size)
        with self.assertRaises(StructureError):
            ExportVoucherSession().get('https://www.exportvoucher.com/common/File2List?docId=DOC_1',timeout=1,headers={})
        n,_=parsed_sample()
        with self.assertRaises(StructureError):
            ExportVoucherSession().download(Resource('https://other.test/file?file_id=FILE_1'),notice=n)

    def test_source_specific_downloader_reuses_existing_text_cache_and_completed_resources(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest('optional PDF reader unavailable')
        document=pymupdf.open()
        document.new_page().insert_text((40,40),'Public provider procurement qualification and patent consulting evidence.')
        payload=document.tobytes()
        document.close()
        notice,resources=parsed_sample()
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='extract-check-') as folder:
            engine=Extractor(folder,budget_seconds=20,isolated=False)
            with patch('src.scrapers.exportvoucher_notice.ExportVoucherSession') as factory:
                factory.return_value.download.return_value=(payload,'public.pdf')
                enriched=engine.enrich(notice,[resources[1]])
                self.assertEqual(enriched.extraction['status'],'SUCCESS')
                self.assertIn('patent consulting evidence',enriched.content_text)
                factory.return_value.download.assert_called_once()
            with patch('src.scrapers.exportvoucher_notice.ExportVoucherSession') as factory:
                reused=engine.enrich(notice,[resources[1]],previous_resources=enriched.extraction['resources'],reuse_completed=True)
                factory.assert_not_called()
                self.assertEqual(reused.extraction['status'],'SUCCESS')
            self.assertTrue(all(p.suffix=='.json' for p in Path(folder).rglob('*') if p.is_file()))
            with patch('src.scrapers.exportvoucher_notice.ExportVoucherSession') as factory:
                factory.return_value.download.side_effect=ValueError('EXPORTVOUCHER_EMPTY_DOWNLOAD')
                failed=engine.enrich(notice,[resources[1]])
            self.assertEqual(failed.extraction['status'],'PARTIAL')
            self.assertEqual(failed.extraction['resources'][0]['status'],'FAILED')
            self.assertIn(INCOMPLETE,failed.content_text)
