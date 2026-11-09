"""Opt-in public HTTP/HTML diagnostics. No state, authentication, AI or bypass."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from src.pipeline import load_site_configs
from src.scrapers._html import parse_html
from src.scrapers.tipa_legacy_bid import TipaBidScraper
from src.scrapers.kiat_home import KiatBidScraper

ADAPTERS={'tipa_legacy_bid':TipaBidScraper,'kiat_home':KiatBidScraper}
URLS={'tipa_legacy_bid':'https://www.tipa.or.kr/s040305',
      'kiat_home':'https://cont.kiat.or.kr/bidding/biddingList.do'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=ADAPTERS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    config=next(c for c in load_site_configs() if c['source_id']==args.source)
    config={**config,'list_url':URLS[args.source],'enabled':True}
    result=dict(source_id=args.source,url=config['list_url'],status='FAILED')
    try:
        with urlopen(Request(config['list_url'],headers={'User-Agent':'NoticeMonitor/0.2'}),timeout=25) as response:
            raw=response.read(5_000_001)
            if len(raw)>5_000_000: raise ValueError('RESPONSE_LIMIT')
            result.update(http_status=response.status,final_url=response.url,
                content_type=response.headers.get('Content-Type'),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            text=raw.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
        root=parse_html(text)
        result.update(title=[n.text() for n in root.find('title')],
            tables=[dict(attributes=n.attrs,headings=[h.text() for h in n.find('th')][:10]) for n in root.find('table')])
        items=ADAPTERS[args.source](config).parse_list(text)
        result.update(status='PASS',list_count=len(items))
    except Exception as error:
        result.update(error_type=type(error).__name__,error=str(error))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return int(result['status']!='PASS')


if __name__=='__main__': raise SystemExit(main())
