"""Opt-in official-site pagination check; no AI calls or state/cache writes.

Only counts, error classes and request methods are printed. The scraper's
observed links/forms determine every request, never an invented page URL.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from src.pipeline import load_site_configs, SUPPORTED_SOURCES
from src.scrapers.registry import build_registry
from src.scrapers.base import UrllibTransport
from src.scrapers.pagination import MAX_COLLECTION_PAGES


def probe(config):
    methods=[]
    class Transport(UrllibTransport):
        def get(self,url,**kwargs):
            methods.append('GET');return super().get(url,**kwargs)
        def post(self,url,**kwargs):
            methods.append('POST');return super().post(url,**kwargs)
    config=dict(config,enabled=True,http=dict(max_retries=0,timeout_seconds=15))
    configs=[dict(c, enabled=c['source_id']==config['source_id']) if c['source_id']!=config['source_id']
             else config for c in load_site_configs()]
    registry=build_registry(configs,transport_factory=lambda source:Transport())
    scraper=registry._scrapers[config['source_id']]
    result=dict(source_id=config['source_id'],cap=MAX_COLLECTION_PAGES,status='ERROR')
    try:
        pages=scraper.fetch_list()
        rows=scraper._parse_items(pages)
        result.update(status='SUCCESS',pages=len(pages),unique_notices=len(rows))
    except Exception as error:
        result['error_type']=type(error).__name__
    result['request_methods']=methods
    return result


def main():
    configs=[c for c in load_site_configs() if c['source_id'] in SUPPORTED_SOURCES]
    with ThreadPoolExecutor(max_workers=7) as executor:
        results=list(executor.map(probe,configs))
    print(json.dumps(results,ensure_ascii=True,indent=2),flush=True)
    return int(any(r['status']!='SUCCESS' for r in results))


if __name__=='__main__':raise SystemExit(main())
