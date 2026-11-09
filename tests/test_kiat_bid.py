import unittest
from pathlib import Path
from unittest.mock import Mock
from src.scrapers.kiat_home import KiatBidScraper
from src.scrapers._html import StructureError

ROOT=Path(__file__).parent/'fixtures/kiat_home'
def read(name):
    return (ROOT/name).read_text(encoding='utf-8')
def scraper(**options):
    return KiatBidScraper(dict(source_id='kiat_home',institution='한국산업기술진흥원',
        enabled=True,list_url='https://cont.kiat.or.kr/bidding/biddingList.do',
        pagination={'parameter':'page'}),**options)

class KiatBidTests(unittest.TestCase):
    def test_actual_list_and_official_deadline_never_infer_publication(self):
        s=scraper()
        items=s._parse_items([read(f'list{i}.html') for i in (1,2,3)])
        self.assertEqual(len(items),45)
        self.assertEqual(items[0].source_notice_id,'567')
        self.assertIsNone(items[0].published_at)
        self.assertEqual(items[0].apply_end,'2026-11-24')
        n=s.normalize(s.parse_detail(read('detail1.html'),items[0]))
        self.assertEqual(n.notice_id,s.notice_id_for(items[0]))
        self.assertEqual(n.apply_end,'2026-11-24')
        self.assertIn('공동수급',n.content_text)
        self.assertIn('입찰참가 자격',n.content_text)
        self.assertNotIn('<br',n.content_text)
        self.assertEqual(s.parse_attachments(read('detail1.html')),
            [f'https://cont.kiat.or.kr/guideDownload/{i}.do' for i in (25685,25686,25687)])
        reannounce=next(i for i in items if i.source_notice_id=='554')
        self.assertTrue(s.normalize(s.parse_detail(read('reannounce.html'),reannounce)).title.startswith('(입찰재공고)'))

    def test_three_observed_pages_and_fail_closed(self):
        s=scraper(transport=Mock())
        s.transport.get.side_effect=[read(f'list{i}.html') for i in (1,2,3)]
        self.assertEqual(len(s.fetch_list()),3)
        self.assertEqual(s.transport.get.call_args_list[1].args[0],s.config['list_url']+'?page=2')
        with self.assertRaises(StructureError): s.parse_list('<html>login</html>')
        with self.assertRaises(StructureError): s.parse_list(read('list1.html').replace('seq=','other='))
        with self.assertRaises(StructureError):
            s.parse_detail(read('detail1.html').replace('2026.11.24','마감 미정'),s.parse_list(read('list1.html'))[0])
        with self.assertRaises(StructureError):
            s.parse_attachments(read('detail1.html').replace('doGuideDownload','unknownFunction'))
