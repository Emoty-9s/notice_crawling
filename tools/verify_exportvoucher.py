"""Opt-in exportvoucher-only live check. No raw attachments persist on disk."""
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from src.ai.prefilter import Prefilter
from src.core.extraction import ExtractionQueue, Extractor
from src.core.storage import _atomic_json
from src.pipeline import load_site_configs
from src.renderer.feed import write_feed
from src.local_client.sync import validate_pair
from src.scrapers.exportvoucher_notice import ExportVoucherScraper, ExportVoucherSession, notice_url


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sample-only',action='store_true')
    parser.add_argument('--require-ocr',action='store_true',help='Require real image attachment OCR, for the installed Actions runtime')
    args=parser.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=False)
    config=next(c for c in load_site_configs() if c['source_id']=='exportvoucher_notice')
    config={**config,'enabled':True,'max_pages':3,'pagination':{'parameter':'pageNo'},
            'http':{'timeout_seconds':25,'max_retries':2}}
    scraper=ExportVoucherScraper(config)
    queue=ExtractionQueue()
    scraper.extractor=queue
    report=dict(source_id=scraper.source_id,status='FAILED',external_ai_calls=0,downloads=[],stage='collection')
    try:
        if not args.sample_only:
            notices=scraper.run()
            report['collected_count']=len(notices)
        else:
            listing=scraper.request_text(config['list_url'])
            page1=scraper.parse_list(listing)
            page2=scraper.parse_list(scraper.request_text(config['list_url']+'&pageNo=2'))
            assert {i.source_notice_id for i in page1}!={i.source_notice_id for i in page2}
            report.update(list_count=len(page1),page2_count=len(page2),distinct_pages=True)
            listed={i.source_notice_id:i for i in page1+page2}
            notices=[]
            for identity in ('13038','8410','13047','13034'):
                url=notice_url(identity)
                report['stage']='detail_'+identity
                item=listed[identity]
                # Use the same fetch/parse/discovery code as the real collector.
                detail=scraper.fetch_detail(item)
                parsed=scraper.parse_detail(detail,item)
                notice=scraper.normalize(parsed)
                from src.core.extraction import discover
                queue.enrich(notice,discover(parsed.body_html,url))
                notices.append(notice)
        report['attachment_counts']={k:len(v) for k,v in scraper.attachment_results.items()}
        assert report['attachment_counts'].get('13038',0)>=1
        assert report['attachment_counts'].get('13047')==0
        report['stage']='download_and_extract'
        original=ExportVoucherSession.download
        def audited(session,resource,*,notice):
            data,name=original(session,resource,notice=notice)
            report['downloads'].append(dict(notice_url=notice.url,resource_url=resource.url,
                name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            return data,name
        extractor=Extractor(args.output/'ocr_cache',budget_seconds=180,pages_per_run=30,isolated=True)
        checked=[]
        with patch.object(ExportVoucherSession,'download',audited):
            for n in notices:
                if 'ntt_id=13038' in n.url or 'ntt_id=13034' in n.url:
                    n=extractor.enrich(n,queue.resources[n.notice_id])
                    field='extraction' if 'ntt_id=13038' in n.url else 'image_extraction'
                    report[field]=dict(status=n.extraction.get('status'),resources=[dict(
                        source_url=r.get('source_url'),name=r.get('name'),status=r['status'],
                        text_characters=sum(len(p.get('text','')) for p in r.get('parts',[])),
                        successful_text_parts=sum(p.get('status')=='SUCCESS' and bool(p.get('text','').strip()) for p in r.get('parts',[])),
                        successful_ocr_parts=sum(p.get('method')=='OCR' and p.get('status')=='SUCCESS' and bool(p.get('text','').strip()) for p in r.get('parts',[])),
                        methods=sorted({p.get('method') for p in r.get('parts',[]) if p.get('method')}))
                        for r in n.extraction.get('resources',[])])
                checked.append(n)
        assert len(report['downloads'])>=1 and all(d['bytes']>0 for d in report['downloads'])
        assert any(r['successful_text_parts']>0 and r['text_characters']>100 for r in report['extraction']['resources'])
        if args.require_ocr:
            assert any('/common.FileDownload.do?' in r['source_url'] and r['successful_ocr_parts']>0
                       for r in report['image_extraction']['resources']), 'ATTACHMENT_OCR_NOT_VERIFIED'
        assert all(not p.suffix.lower() in {'.pdf','.hwp','.hwpx','.jpg','.png'} for p in args.output.rglob('*') if p.is_file())
        _atomic_json(args.output/'notices.json',[n.to_dict() for n in checked])
        policy=Prefilter()
        stamp=checked[0].first_seen_at
        write_feed([policy.evaluate(n,stamp) for n in checked],generated_at=stamp,output_dir=args.output/'public')
        feed=json.loads((args.output/'public/notices.json').read_text(encoding='utf-8'))
        meta=json.loads((args.output/'public/metadata.json').read_text(encoding='utf-8'))
        validate_pair(feed,meta)
        report.update(status='PASS',stage='feed_v3',feed_count=len(feed['notices']),raw_attachments_persisted=False)
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error))
        if error.__cause__:
            report['cause']=str(error.__cause__)
    _atomic_json(args.output/'report.json',report)
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return int(report['status']!='PASS')


if __name__=='__main__': raise SystemExit(main())
