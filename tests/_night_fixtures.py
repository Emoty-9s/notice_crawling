"""Synthetic desktop validation data; never a user's business database."""
import json
from dataclasses import replace
from pathlib import Path

from src.core.models import GeminiResult, Notice
from src.local_client.performance import Performance, PerformanceStore
from src.renderer.feed import build_feed
from src.renderer.source_status import SOURCES, public_source_status

STAMP = '2026-11-02T09:00:00Z'
BASE = 'https://example.test/'


def create_demo(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    db = folder / 'performance.db'
    store = PerformanceStore(db)
    store.create(Performance(performance_id='DEMO-01', project_name='반도체 IP-R&D 특허분석 프로젝트',
                             year=2025, technical_field='반도체', work_type='특허분석',
                             keywords=['반도체', 'IP-R&D', '특허분석'], notes='PRIVATE_DO_NOT_DISPLAY', client='PRIVATE_DO_NOT_DISPLAY'))
    store.create(Performance(performance_id='DEMO-02', project_name='AI 기술동향 및 특허 포트폴리오 분석',
                             year=2024, technical_field='AI', work_type='특허분석', keywords=['AI', '특허분석']))
    first = Notice(notice_id='DEMO-N1', source_id='kipa_bid', institution='한국발명진흥회',
                   title='2026년 반도체 IP-R&D 특허분석 협력기관 모집',
                   content_text='협력기관의 반도체 특허분석 수행을 위한 모집 공고입니다.', content_hash='demo-hash',
                   published_at='2026-11-02', apply_start='2026-11-02', apply_end='2026-11-15',
                   url='https://example.test/notice/1', first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
                   gemini=GeminiResult(status='SUCCESS', analysis_policy='patent-firm-participation-v2', relevant=True, category='IP-R&D', participation_type='협력기관',
                                       keywords=['반도체', 'IP-R&D', '특허분석'], reason='특허분석 수행기관으로 참여할 수 있습니다.',
                                       analyzed_at=STAMP, analyzed_content_hash='demo-hash'))
    second = replace(first, notice_id='DEMO-N2', institution='한국특허전략개발원', source_id='kista_ippro',
                     title='AI 분야 지식재산 전략 지원 전문기관 공고')
    feed = build_feed([first, second], generated_at=STAMP)
    metadata = dict(schema_version=2, generated_at=STAMP, notice_count=len(feed['notices']))
    snapshot = dict(base_url=BASE, feed=feed, metadata=metadata)
    cache = folder / 'snapshot.json'
    cache.write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
    health = public_source_status({s: dict(status='ERROR' if i == 2 else 'SUCCESS', last_attempt_at=STAMP,
                                         notices_found=0 if i == 2 else 10) for i, s in enumerate(SOURCES)}, STAMP)
    return snapshot, cache, db, health
