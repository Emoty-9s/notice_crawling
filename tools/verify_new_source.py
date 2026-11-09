"""Opt-in live verification in a fresh folder; no production state or AI APIs.

python -m tools.verify_new_source --source tipa_legacy_bid --output .run/tipa-check
"""
import argparse
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from src.ai.prefilter import Prefilter
from src.core.extraction import ExtractionQueue, Extractor
from src.core.storage import _atomic_json
from src.pipeline import load_site_configs
from src.renderer.feed import write_feed
from src.scrapers.tipa_legacy_bid import TipaBidScraper
from src.scrapers.kiat_home import KiatBidScraper

ADAPTERS = {'tipa_legacy_bid': TipaBidScraper, 'kiat_home': KiatBidScraper}
URLS = {'tipa_legacy_bid': 'https://www.tipa.or.kr/s040305',
        'kiat_home': 'https://cont.kiat.or.kr/bidding/biddingList.do'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=ADAPTERS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    # Never use an existing folder: history/cache/settings cannot be overwritten.
    args.output.mkdir(parents=True, exist_ok=False)
    config = next(c for c in load_site_configs() if c['source_id'] == args.source)
    config = {**config, 'list_url': URLS[args.source], 'enabled': True,
              'max_pages': 3, 'http': {'max_retries': 0, 'timeout_seconds': 25}}
    if args.source == 'kiat_home':
        config['pagination'] = {'parameter': 'page'}
    now = datetime.now(timezone.utc)
    report = dict(source_id=args.source, checked_at=now.isoformat(), url=config['list_url'],
                  status='FAILED', stage='collection', collected=0, external_ai_calls=0)
    try:
        scraper = ADAPTERS[args.source](config, clock=lambda: now)
        queue = ExtractionQueue()
        scraper.extractor = queue
        # Capture exact requests for offline regression and page identity checks.
        original = scraper.request_text
        requests = []
        def request(url):
            html = original(url)
            name = f'response-{len(requests):03}.html'
            (args.output / name).write_text(html, encoding='utf-8')
            requests.append(dict(url=url, file=name, phase=getattr(scraper, '_request_phase', None)))
            return html
        scraper.request_text = request
        notices = scraper.run()
        report.update(collected=len(notices), requests=requests,
                      unique_ids=len({n.notice_id for n in notices}))
        if not notices or report['unique_ids'] != len(notices):
            raise ValueError('EMPTY_OR_DUPLICATE_COLLECTION')
        for n in notices:
            if not n.content_text or not n.url:
                raise ValueError('MISSING_REQUIRED_FIELDS')
        report['unknown_publication_dates'] = sum(n.published_at is None for n in notices)
        report['stage'] = 'attachments'
        sample = next(n for n in notices if queue.resources.get(n.notice_id))
        extractor = Extractor(args.output / 'ocr_cache', budget_seconds=90, pages_per_run=20, isolated=True)
        enriched = extractor.enrich(sample, queue.resources[sample.notice_id])
        report['attachment_sample'] = dict(notice_id=sample.notice_id, url=sample.url,
            status=enriched.extraction.get('status'),
            resources=[{k:r.get(k) for k in ('source_url','name','status','error_code')}
                       for r in enriched.extraction.get('resources',[])],
            text_chars=len(enriched.content_text))
        notices = [enriched if n.notice_id == sample.notice_id else n for n in notices]
        _atomic_json(args.output / 'notices.json', [n.to_dict() for n in notices])
        report['stage'] = 'feed_v3'
        prefilter = Prefilter()
        evaluated = [prefilter.evaluate(n, now.isoformat()) for n in notices]
        write_feed(evaluated, generated_at=now.isoformat(), output_dir=args.output / 'public')
        from src.local_client.sync import validate_pair
        feed = json.loads((args.output / 'public/notices.json').read_text(encoding='utf-8'))
        meta = json.loads((args.output / 'public/metadata.json').read_text(encoding='utf-8'))
        validate_pair(feed, meta)
        report.update(status='PASS', stage='feed_v3', feed_count=len(feed['notices']))
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
    _atomic_json(args.output / 'report.json', report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
