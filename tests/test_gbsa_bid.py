import unittest
from pathlib import Path
from unittest.mock import Mock
from src.scrapers.gbsa_bid import GbsaBidScraper
from src.scrapers._html import StructureError

ROOT=Path(__file__).parent/'fixtures/gbsa_bid'
def read(name): return (ROOT/name).read_text(encoding='utf-8')
def scraper(**options):
    return GbsaBidScraper(dict(source_id='gbsa_bid',institution='경기도경제과학진흥원',enabled=True,
        list_url='https://www.gbsa.or.kr/board/bid_info.do',pagination={'parameter':'pageIndex'}),**options)

class GbsaBidTests(unittest.TestCase):
    def test_actual_three_pages_detail_and_public_file_ids(self):
        s=scraper()
        items=s._parse_items([read(f'list{i}.html') for i in (1,2,3)])
        self.assertEqual(len(items),30)
        self.assertEqual(items[0].source_notice_id,'12117')
        n=s.normalize(s.parse_detail(read('detail3.html'),items[0]))
        self.assertEqual(n.notice_id,s.notice_id_for(items[0]))
        self.assertEqual(n.published_at,'2026-11-06')
        self.assertIsNone(n.apply_end)
        self.assertIn('구매',n.content_text)
        files=s.parse_attachments(read('detail9.html'))
        self.assertEqual(files,[f'https://www.gbsa.or.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000127490&fileSn={i}' for i in (0,1)])

    def test_observed_paging_and_structure_changes_fail_closed(self):
        s=scraper(transport=Mock())
        s.transport.get.side_effect=[read(f'list{i}.html') for i in (1,2,3)]
        self.assertEqual(len(s.fetch_list()),3)
        self.assertEqual(s.transport.get.call_args_list[1].args[0],s.config['list_url']+'?pageIndex=2')
        with self.assertRaises(StructureError): s.parse_list('<html>no board</html>')
        with self.assertRaises(StructureError): s.parse_list(read('list1.html').replace('nttId=','unknown='))
        with self.assertRaises(StructureError): s.parse_attachments(read('detail9.html').replace('FILE_000000000127490','INVALID'))
