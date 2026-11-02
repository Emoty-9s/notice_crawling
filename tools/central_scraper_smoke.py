"""Opt-in live diagnosis; no Gemini or central state/feed writes.

python -m tools.central_scraper_smoke
Responses are saved only when --capture-dir is explicitly supplied.
"""
import argparse
import json
from pathlib import Path

from src.pipeline import load_site_configs
from src.scrapers.khidi_business import KhidiBusinessScraper
from src.scrapers.seoul_rnd_notice import SeoulRndNoticeScraper

ADAPTERS = {'khidi_business': KhidiBusinessScraper, 'seoul_rnd_notice': SeoulRndNoticeScraper}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-dir', type=Path)
    parser.add_argument('--all-details', action='store_true')
    args = parser.parse_args(argv)
    configs = {c['source_id']: c for c in load_site_configs()}
    reports = []
    for source, adapter in ADAPTERS.items():
        scraper = adapter({**configs[source], 'enabled': True,
                           'http': {'max_retries': 0, 'timeout_seconds': 20}})
        report = {'source_id': source, 'status': 'ERROR', 'stage': 'fetch_list'}
        def capture(name, text):
            if args.capture_dir:
                folder = args.capture_dir / source
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text(text, encoding='utf-8')
        try:
            listing = scraper.fetch_list()
            capture('list.html', listing)
            report['stage'] = 'parse_list'
            items = scraper.parse_list(listing)
            report['list_count'] = len(items)
            count = 0
            for item in items if args.all_details else items[:1]:
                report['stage'] = 'fetch_detail'
                detail = scraper.fetch_detail(item)
                capture(f'detail_{count}.html', detail)
                report['stage'] = 'parse_detail'
                scraper.normalize(scraper.parse_detail(detail, item))
                count += 1
            report.update(status='SUCCESS', stage='complete', detail_count=count)
        except Exception as error:
            report['error_type'] = type(error).__name__
            # Parser errors contain selector diagnostics, never HTTP bodies.
            from src.scrapers._html import StructureError
            if isinstance(error, StructureError):
                report['reason'] = str(error)
        reports.append(report)
    print(json.dumps(reports, ensure_ascii=True, indent=2))
    return int(any(r['status'] != 'SUCCESS' for r in reports))


if __name__ == '__main__':
    raise SystemExit(main())
