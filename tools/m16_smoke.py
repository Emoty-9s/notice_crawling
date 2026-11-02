"""Explicit minimal live probe. No Gemini, storage/public writes or bypasses.

python -m tools.m16_smoke --source ripc_pms kista_ippro
At most robots + list shell + RIPC list AJAX + one detail (retries disabled).
"""

import argparse
import json
import socket
from urllib.error import HTTPError, URLError

from src.pipeline import load_site_configs
from src.scrapers.kista_ippro import KistaScraper
from src.scrapers.ripc_pms import RipcScraper


ADAPTERS = {'ripc_pms': RipcScraper, 'kista_ippro': KistaScraper}


def probe(source, config):
    scraper = ADAPTERS[source]({**config, 'enabled': True, 'max_pages': 1,
                               'http': {'max_retries': 0, 'timeout_seconds': 10}})
    # fetch_list checks robots, table shape and pager; a JS shell must fail.
    report = {'source_id': source, 'status': 'BLOCKED', 'stage': 'robots_or_list', 'notice_count': 0}
    try:
        pages = scraper.fetch_list()
        items = scraper.parse_list(pages)
        report['stage'] = 'detail'
        if not items:
            report['reason'] = 'NO_PUBLIC_NOTICES'
            return report
        item = items[0]
        notice = scraper.normalize(scraper.parse_detail(scraper.fetch_detail(item), item))
        if not notice.title or not notice.url:
            report['reason'] = 'INVALID_NOTICE'
            return report
        report.update(status='SUCCESS', stage='complete', notice_count=1, list_count=len(items),
                      stable_notice_id=notice.notice_id, title_nonempty=True,
                      apply_start=notice.apply_start, apply_end=notice.apply_end)
    except URLError as error:
        if isinstance(error, HTTPError):
            report['reason'] = f'HTTP_{error.code}'
        elif isinstance(error.reason, socket.gaierror):
            report['reason'] = 'DNS_ERROR'
            report['errno'] = error.reason.errno
        else:
            report['reason'] = 'NETWORK_ERROR'
    except Exception as error:
        report['reason'] = type(error).__name__
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', nargs='+', choices=tuple(ADAPTERS), default=list(ADAPTERS))
    args = parser.parse_args(argv)
    configs = {site['source_id']: site for site in load_site_configs()}
    reports = [probe(source, configs[source]) for source in dict.fromkeys(args.source)]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0 if all(report['status'] == 'SUCCESS' for report in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
