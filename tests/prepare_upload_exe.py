"""Prepare explicit synthetic EXE test inputs inside tests, never production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from _night_fixtures import create_demo


if __name__ == '__main__':
    root = Path(__file__).resolve().parent/'fixtures'/'performance_upload'/'runtime'
    root.mkdir(parents=True, exist_ok=True)
    create_demo(root)
    book = Workbook()
    sheet = book.active
    sheet.title = '실적A'
    sheet.append(['가상 회사명'])
    sheet.append(['관리번호', '사업명', '고객사', '수행년도', '기술분야', '업무유형', '업무내용'])
    sheet.append(['001245', '반도체 특허분석', '합성 연구원', 2026, '반도체', '특허분석', '반도체 특허 분석 업무'])
    other = book.create_sheet('실적B')
    other.append(['프로젝트 ID', '용역명', '발주기관', '사업연도', '비고'])
    other.append(['PRJ-2026/002', '바이오 특허 분석', '합성 기관', 2025, '바이오 분석'])
    book.create_sheet('빈 sheet')
    book.save(root/'upload.xlsx')
    book.close()
    print('UPLOAD_EXE_FIXTURES_READY tests/fixtures/performance_upload/runtime')
