"""Prepare explicitly synthetic local-AI EXE inputs under tests only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from _night_fixtures import create_demo


if __name__ == '__main__':
    root = Path(__file__).parent/'fixtures/performance_enrichment/runtime'
    root.mkdir(parents=True, exist_ok=True)
    if not (root/'snapshot.json').exists():
        create_demo(root)
    book = Workbook()
    sheet = book.active
    sheet.title = '실적'
    sheet.append(['관리번호', '사업명', '고객사', '수행년도', '기술분야', '업무유형', '주요업무', '금액'])
    sheet.append(['001245', '반도체 제조 공정 특허동향 분석', None, 2026, '반도체', '원본 업무유형',
                  '메모리 반도체 설계와 웨이퍼 가공 기술 분석', None])
    sheet.append(['PRJ-2026/002', '항체 신약과 유전자 치료제 특허동향 분석', None, None, None, None,
                  '바이오 의약품의 항체 신약 특허 분석', None])
    sheet.append(['PRJ-003', 'AI 기반 의료영상 진단 기술 특허 분석', None, None, None, None,
                  '딥러닝을 활용한 환자 영상 진단 장치', None])
    sheet.append(['ID-004'])
    sheet.append(['EV-005', '전기자동차 배터리팩', None, 2026])
    sheet.append(['EV-006', '전기자동차 배터리팩 하우징', None, 2026])
    book.save(root/'ai-upload.xlsx')
    book.close()
    print('LOCAL_AI_EXE_FIXTURES_READY tests/fixtures/performance_enrichment/runtime')
