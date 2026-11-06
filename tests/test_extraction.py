"""Offline contracts for common OCR extraction and v3 Windows consumption."""
import io
import tempfile
import unittest
import zipfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.extraction import Extractor, Resource, discover, INCOMPLETE, OCR_LABEL
from src.ai.prefilter import Prefilter
from src.local_client.work_opportunity import classify
from src.local_client.sync import validate_pair
from src.renderer.feed import build_feed
from test_central_local_v3 import notice, STAMP


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.engine = Mock(return_value='특허분석 수행기관 모집\n참가 자격: 특허법인 또는 변리사\n마감일 2026.11.20')
        self.extract = Extractor(self.tmp.name, ocr=self.engine, fetch=lambda r:(b'\x89PNG'+r.url.encode(), 'poster.png'))

    def test_html_plus_image_always_ocr_and_local_qualification_is_review(self):
        n = notice(title='공고', content_text='기관의 충분한 HTML 본문입니다. '*20, apply_end=None)
        resources = discover('<p>본문</p><img src="/poster.png"><img src="/logo.png"><img src="/icon_pdf.gif">',n.url)
        self.assertEqual(len(resources),1)
        result = self.extract.enrich(n, resources)
        self.engine.assert_called_once()
        self.assertIn('특허분석 수행기관 모집', result.content_text)
        self.assertIn('[HTML 원문 직접 추출]',result.content_text)
        self.assertIn(OCR_LABEL,result.content_text)
        self.assertIsNone(result.apply_end)
        self.assertEqual(Prefilter().classify(result)[0],'CANDIDATE')
        local = classify(result.to_dict())
        self.assertEqual(local['qualification'],'CHECK_REQUIRED')
        self.assertEqual(local['information_status'],'OCR_REVIEW')
        feed = build_feed([result],generated_at=STAMP)
        validate_pair(feed,dict(schema_version=3,generated_at=STAMP,notice_count=1))
        self.assertNotIn('extraction',feed['notices'][0])

    def test_image_only_phrase_recovers_related_notice_and_cache_is_sha256(self):
        n=notice(title='공고',content_text='')
        first=self.extract.enrich(n,[Resource('https://x.test/a','poster.png','image')])
        self.extract.fetch=lambda r:(b'\x89PNGhttps://x.test/a','renamed.png')
        second=self.extract.enrich(n,[Resource('https://x.test/b','renamed.png','image')])
        self.assertEqual(first.content_text,second.content_text)
        self.assertEqual(self.engine.call_count,1)
        self.assertEqual(Prefilter().classify(first)[0],'CANDIDATE')
        self.assertTrue(second.extraction['resources'][0]['cache_hit'])

    def test_failure_isolated_and_retried_not_success_cached(self):
        self.engine.side_effect=[RuntimeError('bad image'), '특허분석 수행기관 모집', '재시도 성공']
        first=self.extract.enrich(notice(),[Resource('a'), Resource('b')])
        self.assertEqual(first.extraction['status'],'PARTIAL')
        self.assertIn(INCOMPLETE,first.content_text)
        second=self.extract.enrich(notice(),[Resource('a'),Resource('b')])
        self.assertEqual(second.extraction['status'],'SUCCESS')
        self.assertEqual(self.engine.call_count,3)

    def test_unsupported_and_budget_remain_visible_review(self):
        self.extract.fetch=lambda r:(b'unsupported', 'form.xlsx')
        result=self.extract.enrich(notice(title='청소 용역',content_text='청소 시설 계약 세부 사항 '*20),[Resource('a')])
        self.assertEqual(result.extraction['resources'][0]['status'],'UNSUPPORTED')
        self.assertEqual(Prefilter().classify(result)[0],'REVIEW')
        self.extract.deadline=0
        result=self.extract.enrich(notice(),[Resource('a'),Resource('b')])
        self.assertEqual([r['status'] for r in result.extraction['resources']],['DEFERRED','DEFERRED'])

    def test_uncertain_image_and_hidden_editor_and_download_links_discovered(self):
        resources=discover('<input name="contents" value="&lt;img src=&quot;/unknown.webp&quot;&gt;">'
                           '<a href="/fileDownload?id=1">공고문</a><img src="/ambiguous.png">','https://x.test')
        self.assertEqual(len(resources),3)

    def test_unresolved_javascript_attachment_is_visible_not_silently_omitted(self):
        resources=discover('<button title="첨부파일 다운로드" onclick="unknownDownload(1)">공고문.pdf</button>','https://x.test')
        result=self.extract.enrich(notice(),resources)
        self.assertEqual(len(result.extraction['resources']),1)
        self.assertEqual(result.extraction['resources'][0]['error'],'UNRESOLVED_ATTACHMENT_LINK')
        self.assertIn(INCOMPLETE,result.content_text)

    def test_observed_rda_download_buttons_resolve_without_duplicate_unresolved_entry(self):
        from _site_cases import fixture_context
        scraper,*_=fixture_context('rda_bid')
        html='''<div id="attach-file"><button title="첨부파일 다운로드" onclick="fn_download('bidancm','100','0');">공고.hwpx</button></div>
        <script>var url = "/fileDownLoadDw.do?boardId="+boardId+"&dataNo="+dataNo+"&sortNo="+sortNo;</script>'''
        links=scraper.parse_attachments(html)
        self.assertEqual(len(links),1)
        self.assertIn('/fileDownLoadDw.do?boardId=bidancm&dataNo=100&sortNo=0',links[0])

    def test_pre_ocr_central_history_loads_without_reset_or_lost_fields(self):
        from src.core.storage import JsonStorage, _atomic_json
        store=JsonStorage(Path(self.tmp.name)/'legacy')
        original=notice().to_dict()
        original.pop('extraction')
        _atomic_json(store.notices_path,[original])
        loaded=store.load_notices()[0]
        self.assertEqual(loaded.extraction,{})
        self.assertEqual({k:v for k,v in loaded.to_dict().items() if k!='extraction'},original)
        original.pop('analysis')
        _atomic_json(store.notices_path,[original])
        self.assertEqual(store.load_notices()[0].notice_id,original['notice_id'])

    def test_ocr_cannot_override_direct_qualification_exclusion(self):
        result = self.extract.enrich(notice(content_text='특허법인은 참가 불가. 특허분석 수행기관 모집'),[Resource('a')])
        decision = classify(result.to_dict())
        self.assertEqual(decision['status'],'EXCLUDE')
        self.assertEqual(decision['qualification'],'EXPLICIT_EXCLUSION')

    def test_hwpx_direct_and_internal_image(self):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as z:
            z.writestr('Contents/section0.xml','<root><t>직접 추출 참가 자격</t></root>')
            z.writestr('BinData/image1.png',b'png')
        result=self.extract.document(output.getvalue(),'notice.hwpx')
        self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual({p['method'] for p in result['parts']},{'DIRECT','OCR'})
        self.assertIn('직접 추출 참가 자격',result['parts'][0]['text'])

    def test_duplicate_lines_are_not_removed_when_dates_or_qualifications_differ(self):
        self.engine.return_value='공통 문장\n공통 문장\n마감일 2026.11.20\n마감일 2026.11.21'
        result=self.extract.enrich(notice(content_text='공통 문장'),[Resource('a')])
        self.assertEqual(result.content_text.count('공통 문장'),1)
        self.assertIn('2026.11.20',result.content_text)
        self.assertIn('2026.11.21',result.content_text)

    def test_pdf_direct_scan_mixed_and_resume(self):
        try:
            import pymupdf
            from PIL import Image
        except ImportError:
            self.skipTest('install requirements-ocr.txt')
        image=io.BytesIO();Image.new('RGB',(300,200),'white').save(image,format='PNG')
        doc=pymupdf.open()
        page=doc.new_page();page.insert_text((30,30),'Direct PDF text')
        page=doc.new_page();page.insert_image(page.rect,stream=image.getvalue())
        page=doc.new_page();page.insert_text((30,30),'Mixed PDF text');page.insert_image(pymupdf.Rect(40,40,200,200),stream=image.getvalue())
        data=doc.tobytes();doc.close()
        self.extract.pages_per_run=1
        first=self.extract.document(data,'test.pdf')
        self.assertEqual(first['status'],'PARTIAL')
        self.assertEqual(self.engine.call_count,0)
        self.assertIn('Direct PDF text',first['parts'][0]['text'])
        second=self.extract.document(data,'test.pdf')
        self.assertEqual(second['pages_processed'],2)
        final=self.extract.document(data,'test.pdf')
        self.assertEqual(final['status'],'SUCCESS')
        self.assertEqual(self.engine.call_count,1) # same image on two pages
        self.assertEqual({p.get('page') for p in final['parts']},{1,2,3})

    def test_png_jpg_webp_pass_to_engine(self):
        for ext in ('png','jpg','webp'):
            result=self.extract.document(ext.encode(),'notice.'+ext)
            self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual(self.engine.call_count,3)

    @unittest.skipUnless(shutil.which('tesseract'), 'native OCR runs on Linux Actions; Docker quality check on Windows')
    def test_real_cpu_korean_engine_in_isolated_worker(self):
        sample=Path(__file__).parent/'fixtures/ocr/korean-notice.png'
        extractor=Extractor(self.tmp.name,isolated=True)
        result=extractor.document(sample.read_bytes(),sample.name,'image')
        self.assertEqual(result['status'],'SUCCESS')
        text=' '.join(p['text'] for p in result['parts'])
        self.assertIn('특허분석수행기관모집',''.join(text.split()))
        self.assertIn('특허법인',text)
        self.assertIn('변리사',text)


if __name__=='__main__':
    unittest.main()
