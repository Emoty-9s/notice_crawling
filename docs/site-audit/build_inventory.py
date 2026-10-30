"""Compose M01 audit documents/config from extracted source and observed facts.

No network requests, scraper implementation, or third-party dependencies.
"""

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'docs/site-audit'
SOURCE = json.loads((AUDIT / 'SOURCE_EXTRACT.json').read_text(encoding='utf-8'))
URLS = list(dict.fromkeys(e['normalized_url'] for e in SOURCE['url_occurrences']))
SITES = {}


def site(number, source_id, institution, name, observation, *,
         content_type='SPECIAL', strategy='MANUAL_ONLY', risk='HIGH',
         access='TOOL_ERROR', list_url=None, blocker=None, evidence=(),
         detail_url=None, detail_pattern=None, body=None, body_notes='미확인',
         pagination='UNVERIFIED', page_parameter=None, page_url=None,
         page_notes='목록/페이지 이동을 검증하지 못함', complete=False,
         login=None, auth_notes='미확인', anti_bot=None, anti_bot_notes='미확인',
         mvp=None, mvp_notes=None):
    url = URLS[number - 1]
    refs = [e for e in SOURCE['url_occurrences'] if e['normalized_url'] == url]
    source_url = {'url': url, 'references': sorted(set(
        f"{r['sheet']}!R{r['row']}C{r['column']}" for r in refs)),
        'original_institution_labels': sorted(set(r['institution_cell'] for r in refs
                                                 if r['institution_cell']))}
    evidence_rows = [{'url': url, 'method': 'web.open', 'result': observation}]
    for evidence_url, result in evidence:
        evidence_rows.append({'url': evidence_url, 'method': 'web.open/click', 'result': result})
    SITES[number] = {
        'source_id': source_id, 'institution': institution, 'name': name,
        'source_urls': [source_url], 'list_url': list_url,
        'detail_url_pattern': detail_pattern, 'enabled': False,
        'access_status': access, 'content_type': content_type,
        'classification_notes': ('HTML 응답의 텍스트에서 목록/본문을 확인한 기준의 잠정 분류. '
                                 '로컬 HTTP 재현 검증은 남아 있음.' if content_type == 'STATIC_HTML' else
                                 '관찰된 응답을 기준으로 분류. SPECIAL은 기술 특성 미확인/특수 접근도 포함하며 DYNAMIC을 뜻하지 않음.'),
        'pagination': {'type': pagination, 'parameter': page_parameter,
                       'example_url': page_url,
                       'second_page_verified': bool(page_url and complete), 'notes': page_notes},
        'detail': {'example_url': detail_url,
                   'reachable_without_login': True if detail_url and body is not None else None,
                   'body_available_in_html': body, 'notes': body_notes},
        'html': {'list_visible_in_web_html': content_type == 'STATIC_HTML' if access in
                 ('READABLE_LIST', 'ALTERNATIVE_LIST', 'READABLE_PORTAL') else None,
                 'local_http_verified': False,
                 'notes': 'web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.'},
        'json_api': {'verified': None, 'endpoint': None,
                     'notes': '재현 가능한 공고 JSON/API 요청은 확인하지 못함. API 부재를 의미하지 않음.'},
        'javascript': {'required': None,
                       'notes': 'JS 비활성 대조와 XHR/network 검증 미수행. 빈 텍스트만으로 JS 필수라 단정하지 않음.'},
        'auth': {'required': login, 'method': '공동인증서 또는 이메일/비밀번호' if login else None,
                 'notes': auth_notes},
        'anti_bot': {'detected': anti_bot, 'notes': anti_bot_notes},
        'recommended_strategy': strategy,
        'strategy_notes': ('공개 HTML 조회를 먼저 재현한다. 상세/페이지 이동의 미확인 항목을 검증한 뒤 구현.'
                           if strategy == 'REQUESTS' else
                           '현재 증거로 자동수집 경로를 확정할 수 없어 수동 확인 대상으로 보류. 우회하지 않음.'),
        'risk': {'level': risk, 'notes': blocker or body_notes},
        'audit_status': 'LIST_DETAIL_PAGINATION_VERIFIED' if complete else 'LIMITED',
        'checked_on': '2026-10-30', 'blocker': blocker,
        'mvp_priority': mvp, 'mvp_notes': mvp_notes,
        'evidence': evidence_rows,
    }


KHIDI_DETAIL = 'https://www.khidi.or.kr/board/view?linkId=48951946&menuId=MENU01108'
KHIDI_DETAIL_CHECKED = 'https://www.khidi.or.kr/board/view?boardStyle=&categoryId=&continent=&country=&linkId=48951946&maxIndex=00489508879998&menuId=MENU01108&minIndex=00489499069998&no1=9999999998&pageNum=1&rowCnt=10&schEndDate=&schStartDate=&schText=&schType=0'
KHIDI_PAGE = 'https://www.khidi.or.kr/board?boardStyle=&categoryId=&continent=&country=&maxIndex=00489508879998&menuId=MENU01108&minIndex=00489499069998&pageNum=2&rowCnt=10&schEndDate=&schStartDate=&schText=&schType=0&upDown=0'
KIPA_BID_DETAIL = 'https://www.kipa.org/kipa/notice/kw_0402.jsp?article_no=134746&board_no=15&board_wrapper=/kipa/notice/kw_0402.jsp&mode=view&pager.offset=0'
KIPA_BID_PAGE = 'https://www.kipa.org/kipa/notice/kw_0402.jsp?board_no=15&mode=list&pager.offset=10'
KIPA_BIZ_DETAIL = 'https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?article_no=122253&board_no=28&board_wrapper=/kipa/ip001/kw_business_1602.jsp&default:category_id=239&mode=view&pager.offset=0'
KIPA_BIZ_PAGE = 'https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?board_no=28&default:category_id=239&mode=list&pager.offset=10'
RDA_DETAIL = 'https://www.rda.go.kr/board/board.do?boardId=bidancm&currPage=1&dataNo=100000813836&menu_id=ofc&mode=updateCnt&prgId=bid_bidancmEntry&searchKey=&searchVal='
RDA_PAGE = 'https://www.rda.go.kr/board/board.do?boardId=bidancm&catgId=&currPage=2&mode=list&prgId=bid_bidancmEntry&searchEDate=&searchKey=&searchOrgDeptKey=&searchOrgDeptVal=&searchSDate=&searchVal='
SEOUL_DETAIL = 'https://seoul.rnbd.kr/client/c030200/c030200_04.jsp?cPage=1&sField=&sWord=&seqNo=1129'
SEOUL_PAGE = 'https://seoul.rnbd.kr/client/c030200/c030200_00.jsp?cPage=2&sField=&sWord='
KAIA_DETAIL = 'https://www.kaia.re.kr/KAIA/contents/K30101000000.do?id=20260820101844013278&schM=view'
KAIA_PAGE = 'https://www.kaia.re.kr/KAIA/contents/K30101000000.do?page=2'
KISED_LIST = 'https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000'
KISED_DETAIL = 'https://www.kised.or.kr/board.es?act=view&bid=0005&list_no=4648&mid=a10303000000&nPage=1&tag='
KISED_PAGE = 'https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000&nPage=2'
SMTECH_LIST = 'https://www.smtech.go.kr/front/ifg/no/notice02_list.do'
SMTECH_DETAIL = 'https://www.smtech.go.kr/front/ifg/no/notice02_detail.do?ancmId=S02881&aplySn=1&buclCd=S9121&buclYy=&dtlAncmSn=1&pageIndex=1&schdSe=MO5005&searchCondition=&searchKeyword='
KISTA_DETAIL = 'https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?DepthCode1=3&DepthCode2=1&annId=3&annYy=2026&bbsType=ac'

site(1, 'khidi_business', '한국보건산업진흥원', '사업공고',
     'text/html 목록: 931건, 페이지 1/94, 제목/등록일과 상세 링크 확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='LOW', access='READABLE_LIST', list_url=URLS[0],
     detail_url=KHIDI_DETAIL_CHECKED, detail_pattern='/board/view?menuId=MENU01108&linkId={linkId}',
     body=True, body_notes='표본 상세에서 지원대상/지원규모/신청기간을 웹 텍스트로 확인. 첨부 열지 않음.',
     pagination='QUERY', page_parameter='pageNum', page_url=KHIDI_PAGE,
     page_notes='목록 링크를 따라 pageNum=2 조회 성공.', complete=True, login=False,
     auth_notes='비로그인 웹 조회로 목록/상세/2페이지 열람.', anti_bot=False,
     anti_bot_notes='표본 응답에서 CAPTCHA/차단 화면 미관찰. 장기 수집 허용 여부는 별도.',
     evidence=[(KHIDI_DETAIL_CHECKED, '상세 웹 본문과 첨부 링크가 분리되어 있음.'),
               (KHIDI_PAGE, '2페이지 응답 확인.')], mvp=1,
     mvp_notes='공개 목록/상세/페이지 이동 확인, 웹 본문에 관련성 판단용 설명 제공.')
site(2, 'koat_bid', '한국농업기술진흥원', '입찰정보',
     'text/html 목록 121건, 제목/날짜/첨부 표시. 제목 링크가 도구에서 동일 목록으로 해석됨.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[1],
     blocker='상세 링크/페이지 이동 실제 요청 인자 미확인.',
     pagination='UI_NUMERIC_UNRESOLVED', page_notes='1~10/다음/마지막 UI 관찰. 실제 이동 요청 미검증.',
     auth_notes='목록은 비로그인 열람; 상세 미확인.',
     evidence=[(URLS[1], '제목 링크 클릭 결과 동일 목록. 상세 성공으로 집계하지 않음.')])
site(3, 'ipnavi_legacy_board', '한국지식재산보호원', 'IP-NAVI 기존 게시판',
     'text/html 응답에 메뉴/검색/표 헤더만 보이고 목록 행과 총 건수가 비어 있음.',
     access='EMPTY_LIST_SHELL', blocker='게시판 코드 유효성/실제 데이터 로딩 경로 미확인. 빈 행만으로 DYNAMIC 판단 불가.')
site(4, 'ripc_pms', '한국발명진흥회', '지역지식재산센터 PMS',
     'text/html 응답이나 읽을 수 있는 본문 0줄.', access='EMPTY_HTML',
     blocker='렌더링/iframe/공개 공고 경로/로그인 여부 모두 미확인.')
site(5, 'kipa_bid', '한국발명진흥회', '입찰공고',
     'text/html 목록 2081건, 페이지 1/209. 상세와 pager.offset=10 조회 성공.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[4],
     detail_url=KIPA_BID_DETAIL, detail_pattern='/kipa/notice/kw_0402.jsp?mode=view&article_no={id}&board_no=15',
     body=True, body_notes='표본 상세는 용역명/나라장터 안내 중심으로 짧음. 핵심 조건은 외부/첨부에 있어 본문만 판별 제약.',
     pagination='OFFSET', page_parameter='pager.offset', page_url=KIPA_BID_PAGE,
     page_notes='목록의 2페이지 링크가 offset=10이며 응답 열람 성공.', complete=True,
     login=False, auth_notes='목록/상세/2페이지 비로그인 열람.', anti_bot=False,
     anti_bot_notes='표본 응답에서 CAPTCHA/차단 화면 미관찰.',
     evidence=[(KIPA_BID_DETAIL, '상세에 짧은 설명, 나라장터 링크, HWP 첨부 링크.'),
               (KIPA_BID_PAGE, '2페이지 조회 성공.')])
site(6, 'kipa_ip_didimdol', '한국발명진흥회', 'IP 디딤돌 사업공고',
     '원본 기관 셀은 대시(-). 응답의 기관명과 IP 디딤돌 메뉴로 보완. 목록 23건/3페이지.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[5],
     detail_url=KIPA_BIZ_DETAIL, detail_pattern='/kipa/ip001/kw_business_1602.jsp?mode=view&article_no={id}&board_no=28&default:category_id=239',
     body=True, body_notes='표본 상세에 지원대상/지원내용/신청방법을 텍스트로 확인.',
     pagination='OFFSET', page_parameter='pager.offset', page_url=KIPA_BIZ_PAGE,
     page_notes='2페이지 링크의 offset=10 확인했으나 웹 도구 Cache miss. 응답 성공 미검증.',
     blocker='2페이지 응답 재현 필요.', login=False, auth_notes='목록과 표본 상세는 비로그인 조회.',
     evidence=[(KIPA_BIZ_DETAIL, '2026 IP 디딤돌 사업 설명 텍스트 확인.'),
               (KIPA_BIZ_PAGE, '도구 Cache miss. 성공으로 집계하지 않음.')], mvp=5,
     mvp_notes='실질 본문 확보. 조건부 후보: offset 페이지 재조회 성공 필요.')
site(7, 'exportvoucher_notice', '수출바우처', '수출지원기반활용사업 공지사항',
     'text/html 목록 905건과 페이지 1~10/다음 표시. 제목에 이동 가능한 링크가 노출되지 않음.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[6],
     pagination='UI_NUMERIC_UNRESOLVED', page_notes='페이지 UI 확인, 인자/전송방식 미확인.',
     blocker='상세 URL/본문 및 페이지 요청 검증 필요.', auth_notes='목록 비로그인 조회. 로그인 메뉴 자체는 로그인 필수 근거가 아님.')
site(8, 'mssmiv_notice', '제조중소기업혁신바우처', '중소기업혁신바우처 공지사항',
     '요청이 /_queue/index.html 대기열로 이동하고 순차 접속 안내를 표시.', access='QUEUE_PAGE',
     blocker='대기열 때문에 실제 목록/상세 미확인.', anti_bot=None,
     anti_bot_notes='접속 대기열은 관찰했으나 CAPTCHA나 봇 차단으로 확정하지 않음.')
site(9, 'kista_biz_portal', '한국특허전략개발원', 'IP통합지원포털',
     'text/html 포털에 여러 사업 공고/기간과 상세 링크를 제공. 공개 상세도 확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_PORTAL', list_url=URLS[8],
     detail_url=KISTA_DETAIL, detail_pattern='/ippro/com/iprndMain/selectBusinessAnnounceView.do?annId={id}&annYy={year}&bbsType={type}',
     body=True, body_notes='표본 상세는 공고명/접수기간/사업구분 메타데이터. 대상과제는 비어 있음.',
     pagination='PORTAL_PREVIEW', page_notes='포털은 미리보기. 사업별 전체 목록 페이지 이동은 미확인.',
     blocker='사업별 공고 전체 범위와 페이지 이동 미확정.', login=False,
     auth_notes='표본 공고 상세는 로그인 없이 열림. 사업 신청은 별도.',
     evidence=[(KISTA_DETAIL, '협력기관 풀 공고명과 접수기간 열람.')])
site(10, 'kista_business_board', '한국특허전략개발원', '사업정보 게시판',
     'text/html 목록 859건. 표에 제목/등록일이 보이나 상세 링크가 도구에 노출되지 않음.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[9],
     pagination='QUERY_CONTEXT_REQUIRED', page_parameter='pageIndex',
     page_notes='2 링크는 /user/board.do?pageIndex=2로 해석되어 메인으로 이동. bbsId 보존 필요성만 관찰, 동작 미검증.',
     blocker='상세 ID/요청 방식과 bbsId 유지 페이지 요청 검증 필요.',
     evidence=[('https://www.kista.re.kr/user/board.do?pageIndex=2', '메인 /main.do로 이동, 유효한 게시판 2페이지가 아님.')])
site(11, 'kista_bid_board', '한국특허전략개발원', '입찰공고 게시판',
     'text/html 목록 1279건. 제목/진행상태가 있으나 상세 URL 미확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[10],
     pagination='QUERY_CONTEXT_REQUIRED', page_parameter='pageIndex',
     page_notes='2 링크 조회에서 bbsId 없이 메인으로 이동. 1/5 표시는 전체 페이지수로 신뢰하지 않음.',
     blocker='상세/페이지 요청 컨텍스트 추가 확인 필요.',
     evidence=[('https://www.kista.re.kr/user/board.do?pageIndex=2', '메인으로 이동.')])
site(12, 'kista_ipams', '한국특허전략개발원', '산업재산진단기관 관리시스템',
     '원본 /ipams/는 현재 IEPMS 제목과 공개 공지 제목/날짜를 표시. 로그인 폼도 존재.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_PORTAL', list_url=URLS[11],
     blocker='모집공고/공지의 실제 전체 목록, 상세/페이지 이동 미확인.',
     auth_notes='로그인 폼과 공개 미리보기 공존. 공고 열람 로그인 필수 여부 미확인.')
site(13, 'kista_ippro', '한국특허전략개발원', 'IP-R&D 사업관리시스템',
     '로그인 경로지만 text/html에 사업공고/접수기간을 공개 표시. 포털에서 같은 시스템 공고 상세 열람.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_PORTAL', list_url=URLS[12],
     detail_url=KISTA_DETAIL, detail_pattern='/ippro/com/iprndMain/selectBusinessAnnounceView.do?annId={id}&annYy={year}&bbsType={type}',
     body=True, body_notes='협력기관 모집 표본 상세에서 공고명/기간 확인. 전체 본문 제공은 미확인.',
     blocker='전체 목록/페이지 이동 검증 필요. 로그인 경로명만으로 LOGIN 분류하지 않음.',
     login=False, auth_notes='포털 링크의 표본 모집공고 상세는 비로그인 조회 가능.',
     evidence=[(KISTA_DETAIL, '로그인 없이 상세 메타데이터 열림.')])
site(14, 'kista_ipas', '한국특허전략개발원', '국가 R&D 특허동향 심층분석 사업',
     '로그인 URL에서 text/html에 공고 제목/상태/날짜가 보임.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_PORTAL', list_url=URLS[13],
     blocker='상세/전체 목록/페이지 이동 미확인.',
     auth_notes='공개 미리보기와 로그인 폼 공존. 상세 열람의 로그인 필요 여부 미확인.')
site(15, 'kabit_home', '한국BI기술사업화협회', '대표 홈페이지',
     '원본 HTTP 조회와 HTTPS 재확인 모두 웹 도구 Timeout.', blocker='도구 접근 실패. 사이트 폐쇄/로그인/JS 여부로 해석하지 않음.')
site(16, 'kautm_home', '한국대학기술이전협회', '대표 홈페이지',
     '원본 HTTP 요청의 HTTPS 조회에서 웹 도구 502 Bad Gateway.', blocker='본문과 목록 경로 확인 불가. 실제 서버 상태와 도구 오류를 구분해야 함.')
site(17, 'ketep_home', '한국에너지기술평가원', '대표 홈페이지',
     '웹 도구 Timeout. 원본의 별도 입찰 경로도 접근 제한.', blocker='공개 목록/상세/페이지 이동 미확인.')
site(18, 'gbsa_bid', '경기도경제과학진흥원', '입찰정보',
     '원본 게시판과 홈페이지 직접 조회는 웹 도구 Bad Request. 공식 도메인 검색 결과에는 입찰 제목 존재.',
     blocker='검색 인덱스는 직접 게시판 조회 성공 증거가 아님. 목록/상세 요청 재확인 필요.',
     evidence=[('https://www.gbsa.or.kr/', '공식 도메인 검색 인덱스에 입찰정보가 있으나 web.open은 Bad Request.')])
site(19, 'kist_general', '한국과학기술연구원', '일반공지',
     '원본은 웹 도구 Bad Request. mode=list 추가 조회도 도구 접근 불가.', blocker='원본 게시판 접근 검증 필요.',
     evidence=[('https://www.kist.re.kr/ko/notice/general-notice.do?mode=list', '웹 도구 접근 불가.')])
site(20, 'kfrm_home', '범부처재생의료기술개발사업단', '대표 홈페이지',
     '원본 경로와 도메인 루트 재조회 모두 웹 도구 502 Bad Gateway.', blocker='원본 및 대체 루트에서 목록 접근 불가.',
     evidence=[('http://www.kfrm.org/', 'HTTPS 조회로 도구 502.')])
site(21, 'yongin_support', '용인기업지원시스템', '지원사업 공고',
     '포털 공개 사업 제목/기간 확인. 더보기에서 /application.do 목록 398건 확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST',
     list_url='https://ybs.ypa.or.kr/application.do', blocker='상세 URL 및 페이지 이동 요청 미확인.',
     pagination='UI_UNRESOLVED', auth_notes='로그인 안내는 있으나 목록은 공개. 상세/신청은 구분 필요.',
     evidence=[('https://ybs.ypa.or.kr/application.do', '지원사업 제목/기간 목록 398건 열람.')])
site(22, 'kaips_ip_business', '한국지식재산서비스협회', 'IP사업 게시판 기존 경로',
     '원본 HTTP의 HTTPS 조회에서 웹 도구 502 Bad Gateway.', blocker='원본 목록 접근 실패. 별도 Sheet2 경로도 Timeout.')
site(23, 'smtech_announcements', '중소기업기술개발사업 종합관리시스템', 'R&D 사업공고',
     '원본은 연간 일정표. /notice02_list.do에서 공고/접수기간 목록, 표본 상세 웹 본문 확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST', list_url=SMTECH_LIST,
     detail_url=SMTECH_DETAIL, detail_pattern='/front/ifg/no/notice02_detail.do?ancmId={id}&aplySn={n}&dtlAncmSn={n}&buclCd={code}',
     body=True, body_notes='표본 수출지원프로그램 상세에서 사업 설명/시작일/종료일 확인. 세부 조건은 첨부 참조.',
     pagination='UI_NUMERIC_UNRESOLVED', page_parameter='pageIndex',
     page_notes='1~10 UI 존재. pageIndex=2 직접 확인은 도구 접근 불가. JS 함수/POST 여부 미확정.',
     blocker='페이지 이동 요청 방식과 세션 없는 URL 재현 검증 필요.',
     login=False, auth_notes='로그인 안내 모달 텍스트와 별개로 표본 공고 목록/상세 비로그인 조회 가능.',
     evidence=[(SMTECH_LIST, '공고 목록 HTML 텍스트 확인.'),
               (SMTECH_DETAIL, 'URL 내 세션 식별자를 제외하고 공개 상세 열람 성공.'),
               (SMTECH_LIST + '?pageIndex=2', '도구 접근 불가. 페이지 이동 성공으로 집계하지 않음.')],
     mvp=6, mvp_notes='공개 목록/상세 확보. 조건부 후보: 페이지 이동 검증 필요.')
site(24, 'iris_announcements', '범부처통합연구지원시스템', 'IRIS 사업공고',
     '메인 사업공고 링크에서 공개 목록 /contents/retrieveBsnsAncmBtinSituListView.do 확인. 17건/2페이지.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST',
     list_url='https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do',
     blocker='상세 식별자/클릭 요청 및 페이지 이동 미확인.', pagination='UI_UNRESOLVED',
     auth_notes='사업공고 목록은 공개. 연구업무 로그인과 분리.',
     evidence=[('https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do', '제목/공고일/공고번호 및 1/2 페이지 표시.')])
site(25, 'g2b_legacy', '나라장터', '나라장터 기존 진입점',
     '원본 /index.jsp 요청이 sso.g2b.go.kr OIDC 인증 흐름으로 이동하며 웹 도구에서 열리지 않음.',
     access='SSO_REDIRECT', blocker='이 진입점으로 비로그인 공고 조회를 확인하지 못함. 공개 API/새 화면은 별도 검증 필요.',
     auth_notes='SSO 리다이렉트 관찰. 모든 공개 공고가 로그인 필수라는 의미는 아님.',
     evidence=[('https://www.g2b.go.kr/index.jsp', '동적 OIDC state/nonce 값은 기록/재사용하지 않음.')])
site(26, 'hsbiz_home', '화성산업진흥원', '대표 홈페이지',
     '원본 루트는 웹 도구 Timeout. 공식 검색에 새 /bbs/.../view.do 상세는 있으나 직접 열기는 Cache miss.',
     blocker='현재 공식 목록/상세 직접 검증 필요. 첨부 다운로드 API의 존재만으로 JSON_API 분류하지 않음.',
     evidence=[('https://www.hsbiz.or.kr/bbs/BBSMSTR_000000000041/view.do?nttId=B000000002215Hs8cN5', '검색 인덱스에는 입찰 상세, 직접 조회는 도구 Cache miss.')])
site(27, 'rda_bid', '농촌진흥청', '입찰공고',
     '공개 HTML 목록 3859건, 표본 상세와 currPage=2 조회 성공.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[26],
     detail_url=RDA_DETAIL, detail_pattern='/board/board.do?mode=updateCnt&boardId=bidancm&prgId=bid_bidancmEntry&dataNo={id}',
     body=True, body_notes='표본에 입찰 대상/납품기한/장소/방법 텍스트 존재. 세부 규격은 첨부에만 있어 본문 판별 범위 제한.',
     pagination='QUERY', page_parameter='currPage', page_url=RDA_PAGE,
     page_notes='목록 2 링크의 currPage=2 응답 확인.', complete=True,
     login=False, auth_notes='비로그인 목록/상세/2페이지 열람.', anti_bot=False,
     anti_bot_notes='표본 응답에서 CAPTCHA/차단 미관찰.',
     evidence=[(RDA_DETAIL, '공고 설명 웹 본문 확인.'), (RDA_PAGE, '2페이지 열람 성공.')],
     mvp=3, mvp_notes='공개 상세 텍스트와 안정적 게시물 ID/페이지 인자 확인. 첨부 내용 분석 제외.')
site(28, 'seoul_rnd_notice', '서울경제진흥원', '서울 R&D 지원센터 공지사항',
     '공개 HTML 제목/등록일 목록. 첫 상세 seqNo=1130은 Timeout, 다른 표본 seqNo=1129는 성공.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[27],
     detail_url=SEOUL_DETAIL, detail_pattern='/client/c030200/c030200_04.jsp?seqNo={id}',
     body=True, body_notes='표본 선정 결과 안내에서 웹 설명/일정/문의 내용 확인. 첫 표본 Timeout 이력 있음.',
     pagination='QUERY', page_parameter='cPage', page_url=SEOUL_PAGE,
     page_notes='목록의 2 링크 cPage=2 응답 확인.', complete=True,
     login=False, auth_notes='공개 공지 목록/상세 조회 성공. 신청/과제번호 확인의 로그인 요구와 구분.',
     anti_bot=False, anti_bot_notes='성공한 표본에서 CAPTCHA/차단 미관찰.',
     evidence=[(SEOUL_DETAIL, '대체 표본 상세 웹 본문 열람.'), (SEOUL_PAGE, '2페이지 열람 성공.'),
               ('https://seoul.rnbd.kr/client/c030200/c030200_04.jsp?cPage=1&sField=&sWord=&seqNo=1130', '첫 상세는 도구 Timeout.')],
     mvp=4, mvp_notes='목록/본문/페이지 이동 확인. 첫 상세 Timeout을 고려해 구현 전 재현 확인.')
site(29, 'tipa_legacy_bid', '중소기업기술정보진흥원', '입찰구매정보 기존 경로',
     '원본 /s040305가 /eng로 이동하고 읽을 수 있는 본문 0줄.', access='REDIRECT_OTHER',
     blocker='입찰 게시판으로 연결되는 현재 공개 경로 재확인 필요. 원본 링크가 목록을 제공하지 않음.',
     evidence=[('https://www.tipa.or.kr/eng', '원본 조회의 도착 URL. 목록/상세 미확인.')])
site(30, 'snip_bid', '성남산업진흥원', '입찰공고',
     '원본 게시판은 웹 도구 접근 불가. 루트는 text/html이나 본문 0줄.',
     blocker='게시판 접근/렌더링 확인 필요. 원본만으로 STATIC 또는 DYNAMIC 단정 불가.',
     evidence=[('https://www.snip.or.kr/', '본문 0줄.')])
site(31, 'kised_home', '창업진흥원', '대표 포털 진입점',
     '기관/K-Startup 선택 화면. 원본 Sheet2 입찰 안내 경로에서 별도 공개 입찰 게시판 확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST', list_url=KISED_LIST,
     blocker='실제 조사 상세는 kised_bid_public 항목 참조. 원본 루트 자체는 공고 목록이 아님.',
     evidence=[(KISED_LIST, '기관 공개 입찰 목록. 대표 루트와 별도 경로.')])
site(32, 'kised_ebid', '창업진흥원', '계약관리시스템 8443 포트',
     '웹 도구가 원본 8443 URL을 invalid ref_id/arguments로 처리해 본문 조회 자체가 불가.',
     access='TOOL_UNSUPPORTED_URL', blocker='8443 포트 접근 도구 제약. 로그인 필요 여부 미확인. 공개 대안 kised_bid_public 존재.',
     evidence=[('https://www.kised.or.kr/menu.es?mid=a10313000000', '공식 안내에 계약관리시스템 링크 존재. 조회 오류를 로그인 증거로 보지 않음.')])
site(33, 'kaia_rnd', '국토교통과학기술진흥원', '국토교통 R&D 공고',
     'HTML 목록 1224건/123페이지. 상세와 page=2 조회 성공.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[32],
     detail_url=KAIA_DETAIL, detail_pattern='/KAIA/contents/K30101000000.do?schM=view&id={id}',
     body=False, body_notes='표본 상세는 제목/기간과 PDF 본문 문서뷰어 중심. 핵심 설명의 HTML 본문 확보 실패. 첨부 분석 제외 정책상 MVP 우선 제외.',
     pagination='QUERY', page_parameter='page', page_url=KAIA_PAGE,
     page_notes='2페이지 링크 page=2 응답 확인.', complete=True,
     login=False, auth_notes='목록/상세/2페이지는 공개.', anti_bot=False,
     anti_bot_notes='표본에서 CAPTCHA/차단 미관찰.',
     evidence=[(KAIA_DETAIL, 'PDF 본문 뷰어 링크, 제목/기간만 확인.'), (KAIA_PAGE, '2페이지 열람 성공.')])
site(34, 'kiat_home', '한국산업기술진흥원', '대표 홈페이지 공고 미리보기',
     'text/html 메인에 사업공고 제목/기간과 새소식 미리보기. 더보기/제목 URL은 도구에서 구분되지 않음.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_PORTAL',
     blocker='원본은 메인. 정확한 전체 목록/상세 ID/페이지 이동 미확인.')
site(35, 'khidi_business_alias', '한국보건산업진흥원', '사업공고 siteId=null 변형',
     '동일 MENU01108 사업공고 HTML, 489줄. 원본 URL과 같은 게시판 제목/목록 구조.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='LOW', access='READABLE_LIST', list_url=URLS[0],
     body_notes='khidi_business와 같은 게시판으로 통합. 별도 공고 수집 대상으로 중복 등록하지 않음.')
site(36, 'mss_business', '중소벤처기업부', '사업공고',
     '원본 searchRltnYn=A URL은 Timeout. 해당 인자를 뺀 동일 cbIdx=310 목록은 HTML 2224건/223페이지.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST',
     list_url='https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310',
     pagination='UI_NUMERIC_UNRESOLVED', page_notes='페이지 UI 관찰. 상세 링크 클릭은 동일 목록으로 돌아옴.',
     blocker='원본 필터와 대체 목록의 범위 동등성, 상세 요청/페이지 이동 미검증.',
     auth_notes='대체 목록은 도구에서 공개 열람. 메뉴에 로그아웃 문구가 있어도 인증 세션으로 단정하지 않음.',
     evidence=[('https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310', '목록 확인, 제목 클릭은 동일 목록으로 해석됨.')])
site(37, 'technopark_main', '한국테크노파크진흥회', '사업공고 및 TP 공고 집계',
     '메인에 외부 TP 공고 링크. TP진흥회 사업공고는 5건/1페이지, TP 집계 목록은 Timeout.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST',
     list_url='https://www.technopark.or.kr/www/bbsPost/72/list.do?mid=1008',
     pagination='SINGLE_PAGE_OBSERVED', page_notes='진흥회 게시판은 5건/1페이지. TP 집계는 별도 목록으로 유지해야 함.',
     blocker='진흥회 게시판 상세 클릭과 외부 TP별 본문/집계 페이지를 추가 확인해야 함.',
     evidence=[('https://www.technopark.or.kr/www/bbsPost/72/list.do?mid=1008', '진흥회 공고 5건, 표/접수기간 확인.'),
               ('https://www.technopark.or.kr/www/linkBoard/list.do?mid=1012&type=P', 'TP별 사업공고 집계 목록은 Timeout.')])
site(38, 'kier_ebid', '한국에너지기술연구원', '전자입찰 공고',
     '원본 noticeList.do 조회에서 웹 도구 502 Bad Gateway.', blocker='목록/상세/로그인/페이지 요청 미확인.')
site(39, 'krict_bid', '한국화학연구원', '입찰공고',
     '원본 쿼리 URL은 도구 접근 불가. 쿼리 없는 같은 목록 경로는 0건/1페이지의 빈 입찰 표를 반환.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST',
     list_url='https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do',
     pagination='SINGLE_PAGE_EMPTY', page_notes='현재 진행 공고 없음, 1/1 표시. 여러 페이지 요청 미확인.',
     blocker='공고가 있는 시점의 상세와 상태/검색 필터 및 과거 공고 경로 재검증 필요.',
     body_notes='현재 표본 공고가 0개라 웹 상세 본문 유무를 판단할 수 없음.',
     evidence=[('https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do', '공고문/사양서 컬럼과 현재 공고 없음 안내 확인.'),
               ('https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do?bidStatus=B', '다른 상태 조회도 도구 접근 불가.')])
site(40, 'hipa_legacy_notice', '화성산업진흥원', '과거 hscity 공고·공시',
     'Sheet2의 hipa.hscity.go.kr/support/notice/list는 웹 도구 접근 불가.',
     blocker='과거 도메인 목록 접근 불가. hsbiz와 동일 게시판인지 확인되지 않아 자동 통합하지 않음.')
site(41, 'kised_bid_public', '창업진흥원', '공개 입찰공고',
     '원본 안내 페이지의 입찰공고 바로가기에서 공개 board.es 목록 835건/84페이지 발견.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='ALTERNATIVE_LIST', list_url=KISED_LIST,
     detail_url=KISED_DETAIL, detail_pattern='/board.es?act=view&bid=0005&mid=a10303000000&list_no={id}',
     body=True, body_notes='표본 상세에 용역명/접수기간/설명 텍스트. 세부 자격은 나라장터/첨부를 참조하므로 판단 범위 제한.',
     pagination='QUERY', page_parameter='nPage', page_url=KISED_PAGE,
     page_notes='공식 목록의 2 링크 nPage=2 조회 성공.', complete=True,
     login=False, auth_notes='8443 계약관리시스템 로그인 없이 별도 기관 공개 게시판 열람.',
     anti_bot=False, anti_bot_notes='공개 목록/상세/2페이지에서 CAPTCHA/차단 미관찰.',
     evidence=[(KISED_LIST, '공식 안내의 링크를 통해 공개 목록 확인.'),
               (KISED_DETAIL, '상세 웹 텍스트 확인.'), (KISED_PAGE, '2페이지 응답 확인.')],
     mvp=2, mvp_notes='로그인 시스템과 분리된 공개 입찰 목록/상세/페이지 경로 확보.')
site(42, 'kaia_legacy_bid', '국토교통과학기술진흥원', '과거 입찰공고 URL',
     '원본 /portal/bbs/list/B0000054.do?menuNo=200786는 웹 도구가 404 Not Found 보고.',
     content_type='UNSUPPORTED', access='LEGACY_404', blocker='이 과거 URL은 현재 조사 경로로 지원 불가. 기관 전체 미지원 판정은 아님.',
     evidence=[(URLS[32], '동일 기관의 새 R&D 공고는 열림. 입찰 게시판과 다른 종류이므로 대체로 간주하지 않음.')])
site(43, 'kaips_ip_business_alt', '한국지식재산서비스협회', 'IP사업 게시판 별도 경로',
     '원본 /bbs_shop/list.htm?board_code=kaips_4 조회는 웹 도구 Timeout.',
     blocker='기존 kaips_12와 게시판 동등성/상세/페이지 이동 미확인. 별도 원본 URL 유지.')
site(44, 'ipnavi_ipds_login', '한국지식재산보호원', 'IPDS 전문기관 수행관리',
     '로그인 화면이 기업용 공동인증서 또는 이메일 로그인, 로그인 후 기업정보 등록 필요를 명시.',
     content_type='LOGIN', access='LOGIN_PAGE', login=True,
     auth_notes='공동인증서/이메일 로그인 후 기업정보 등록 안내를 실제 확인. 로그인하지 않음.',
     blocker='전문기관 전용 인증 서비스. 공개 공고 수집 대상으로 자동화하지 않음.',
     pagination='NOT_APPLICABLE_LOGIN', page_notes='인증 화면만 확인. 내부 목록 조사/접근 안 함.')
site(45, 'kautm_tlo_news', '한국대학기술이전협회', 'TLO 뉴스',
     '원본 과거 PHPSESSID를 제거한 공개 URL을 조회했으나 웹 도구 502 Bad Gateway.',
     blocker='공개 목록/상세 접근 불가. 과거 세션 식별자는 재사용하지 않음.')
site(46, 'ketep_legacy_bid', '한국에너지기술평가원', '입찰공고 기존 경로',
     'Sheet2 /brdartcl/boardarticleView.do 경로는 웹 도구 접근 불가.',
     blocker='목록인지 상세인지도 원본 이름만으로 확정 불가. 공식 현재 입찰 경로 재확인 필요.')
site(47, 'khidi_bioagora', '한국보건산업진흥원', '바이오 아고라',
     'text/html 응답이나 읽을 수 있는 본문 0줄. 도구는 수개월 전 수집본으로 표시.', access='EMPTY_HTML',
     blocker='현재 상태/실제 공고 기능/iframe/JS/API 여부 미확인. 캐시만으로 운영 상태 판단 불가.')
site(48, 'exportvoucher_notice_alias', '수출바우처', '공지사항 메뉴 변형',
     'active_menu_cd 변형에서 동일 공지사항 905건/제목/페이지 구조 확인.',
     content_type='STATIC_HTML', strategy='REQUESTS', risk='MEDIUM', access='READABLE_LIST', list_url=URLS[6],
     blocker='exportvoucher_notice 항목과 같은 게시판. 상세/페이지 요청은 추가 확인 필요.')
site(49, 'technopark_legacy_domain', '한국테크노파크진흥회', '과거 technopark.kr 도메인',
     '원본 HTTP의 HTTPS 조회에서 웹 도구가 404 Not Found 보고.',
     content_type='UNSUPPORTED', access='LEGACY_404', blocker='과거 루트는 현재 조사 경로로 지원 불가. technopark.or.kr과 자동 리다이렉트/동등성 미확인.',
     evidence=[(URLS[36], '원본의 다른 도메인 technopark.or.kr은 열림. 별도 기관 사이트 항목 참조.')])


def compose():
    assert set(SITES) == set(range(1, 50))
    # Only equivalent board variants that were actually opened are merged.
    for alias, canonical in ((35, 1), (48, 7)):
        SITES[canonical]['source_urls'].extend(SITES[alias]['source_urls'])
        SITES[canonical]['evidence'].extend(SITES[alias]['evidence'])
        SITES[canonical].setdefault('merged_aliases', []).append(SITES[alias]['source_id'])
        del SITES[alias]
    sites = list(SITES.values())
    checked = sum(s['audit_status'] == 'LIST_DETAIL_PAGINATION_VERIFIED' for s in sites)
    counts = Counter(s['content_type'] for s in sites)
    summary = {
        'status': 'PARTIAL', 'checked_on': '2026-10-30',
        'source_file': SOURCE['source_file'], 'source_sha256': SOURCE['sha256'],
        'source_url_occurrences': len(SOURCE['url_occurrences']),
        'unique_normalized_source_urls': len(URLS), 'inventory_sources': len(sites),
        'distinct_hostnames': len({urlsplit(u).hostname for u in URLS}),
        'institution_groups': len({s['institution'] for s in sites}),
        'source_urls_attempted': len(URLS), 'list_detail_pagination_verified': checked,
        'classifications': {k: counts[k] for k in ('STATIC_HTML', 'JSON_API', 'DYNAMIC', 'LOGIN', 'SPECIAL', 'UNSUPPORTED')},
        'mvp_candidates': [s['source_id'] for s in sorted(sites, key=lambda s: s['mvp_priority'] or 999) if s['mvp_priority']],
        'method_notes': [
            'Source extraction: stdlib ZIP/XML/BIFF12 record parsing; original workbook not modified.',
            'Site evidence: web open/click HTML text and tool error observations; some pages are cached.',
            'Local urllib HTTP failed with DNS getaddrinfo; browser host unavailable; native UI stopped because current URL could not be verified.',
            'No browser network/XHR inspection; JSON API and mandatory JavaScript remain unknown, not absent.',
            'SPECIAL includes inaccessible/unverified endpoints, not proof of a special runtime.',
            'All enabled=false: inventory decisions only, no scraper or production activation.',
        ],
    }
    # JSON is a YAML 1.2 subset and permits stdlib round-trip validation without installing PyYAML.
    config = {'audit': summary, 'sites': sites}
    (ROOT / 'config/sites.yaml').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (AUDIT / 'AUDIT_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    render_inventory(summary, sites)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def render_inventory(summary, sites):
    lines = [
        '# Site Inventory', '',
        '## 상태와 집계', '',
        '**PARTIAL** — 전체 원본 URL 접근 확인을 시도했으며 제한된 사이트는 개별 보류로 남겼다.',
        '확인일: 2026-10-30 (Asia/Seoul). 페이지는 web 조회 도구의 수집본/캐시를 포함한다.', '',
        f"- 원본: `{SOURCE['source_file']}` (읽기 전용).",
        f"- SHA-256: `{SOURCE['sha256']}`.",
        f"- URL이 있는 셀/링크 조합 {summary['source_url_occurrences']}건 → 정규화 URL {len(URLS)}개 → 같은 게시판 변형 2개 통합 후 수집원 {len(sites)}개.",
        f"- {summary['institution_groups']}개 기관/서비스 그룹, {summary['distinct_hostnames']}개 호스트. 기관 그룹 수는 법인 수가 아니다.",
        f"- 접근 시도: 원본 URL {len(URLS)}개 전체. 목록·상세·실제 2페이지 확인 완료: {summary['list_detail_pagination_verified']}개 수집원.",
        '- 위 6개도 로컬 HTTP/JS 비활성 비교/API 검증까지 완료했다는 의미는 아니다.',
        '- 분류/전략/위험도는 전 수집원에 지정. 미확인 사실은 null/미확인으로 유지하며 전략은 관찰에 근거한 권고다.', '',
        '## 추출과 중복 처리', '',
        '- 설치 없이 `zipfile`, `struct`, `xml.etree.ElementTree`로 XLSB의 sharedStrings/worksheet 레코드와 관계 XML을 읽었다.',
        '- Sheet1 문자열 셀 403개/하이퍼링크 37개, Sheet2 문자열 셀 27개/하이퍼링크 27개를 확인했다.',
        '- 기관명은 Sheet1 B열의 병합 셀 범위를 적용했다. C31의 3개 URL을 모두 추출했으며 하이퍼링크 대상만 읽어 누락하지 않았다.',
        '- 셀 텍스트와 하이퍼링크가 같은 셀에서 같은 URL이면 1건으로 합쳤다. 같은 셀의 KIAT fragment 변형은 원본 참조를 보존한 채 정규화했다.',
        '- fragment와 과거 PHPSESSID를 제거했다. 세션값은 원본 파일 외 산출물에서 가리고 요청에 재사용하지 않았다.',
        '- KHIDI `siteId=null` 변형, 수출바우처 `active_menu_cd` 변형은 실제 같은 게시판 구조를 확인한 뒤 각각 통합했다.',
        '- 보건산업진흥원/한국보건산업진흥원 이름은 정리했다. KIPA 원본 기관 셀의 대시는 응답의 기관명을 근거로 보완했다.',
        '- 같은 기관이라도 사업정보/입찰/로그인 시스템/다른 게시판 URL은 합치지 않았다. 과거 도메인 동등성도 추정하지 않았다.',
        '- 셀별 원본 URL/표시명/위치는 `SOURCE_EXTRACT.json`, 분류와 상세 근거는 `config/sites.yaml`에 보존한다.', '',
        '## 조사 방법과 해석 제한', '',
        '- HTML 직접 수집 가능성은 web 도구가 반환한 `text/html`의 목록/본문을 근거로 잠정 판단했다. 로컬 Python HTTP는 DNS 오류로 실패했다.',
        '- browser host가 없고 native Chrome 제어도 현재 URL 검증 실패로 중단되어 DevTools/XHR, JS 비활성 비교는 수행하지 못했다.',
        '- 따라서 API 미확인 ≠ API 없음, 빈 텍스트 ≠ JS 필수, 로그인 메뉴 존재 ≠ 공고 열람 로그인 필수다.',
        '- 도구의 400/502/Timeout/Cache miss는 사이트의 실제 HTTP 응답 코드나 영구 장애로 단정하지 않는다. 404도 해당 옛 URL에 한정한다.',
        '- SPECIAL은 대기열/인증 전환/미확인 접근을 포함하는 보류 분류다. DYNAMIC/PLAYWRIGHT를 근거 없이 부여하지 않았다.',
        '- CAPTCHA/봇 차단은 성공 표본에서 미관찰 또는 미확인으로 기록한다. 대기열을 CAPTCHA라고 부르지 않는다.',
        '- 미지원/보류는 MANUAL_ONLY로 기록하고, 모든 enabled는 false다. 로그인/접근 통제 우회와 첨부 본문 분석은 하지 않았다.', '',
        '## 분류 요약', '',
        '| 분류 | 수집원 수 |', '|---|---:|',
    ]
    for category, count in summary['classifications'].items():
        lines.append(f'| {category} | {count} |')
    lines.extend(['', '## 전체 수집원', '',
                  '| ID | 기관/서비스 | 대상 | 분류 | 전략 | 위험도 | 조사 단계 |',
                  '|---|---|---|---|---|---|---|'])
    for s in sites:
        phase = '목록/상세/2페이지 확인' if s['audit_status'] == 'LIST_DETAIL_PAGINATION_VERIFIED' else '제한/후속 확인'
        lines.append(f"| [{s['source_id']}](#{s['source_id']}) | {s['institution']} | {s['name']} | {s['content_type']} | {s['recommended_strategy']} | {s['risk']['level']} | {phase} |")
    lines.extend(['', '## MVP 후보', '',
                  '아래는 구현 후보이며 현재 수집 성공 보증이 아니다. 기술 단순성과 공개 웹 본문 제공을 우선한 순서다.',
                  '업무상 우선순위는 원본 목록만으로 확정할 수 없어 별도 확인이 필요하다.', '',
                  '| 순위 | 수집원 | 근거 및 조건 |', '|---:|---|---|'])
    for s in sorted(sites, key=lambda s: s['mvp_priority'] or 999):
        if s['mvp_priority']:
            lines.append(f"| {s['mvp_priority']} | {s['institution']} / {s['name']} | {s['mvp_notes']} |")
    lines.extend(['', 'KAIA R&D는 표본의 핵심 본문이 PDF 뷰어 중심이라 우선 제외했다. KIPA 입찰은 공개 조회가 가능하나 설명이 짧아 예비 후보로만 둔다.',
                  'KIPA IP 디딤돌과 SMTECH는 페이지 요청 재검증이 필요한 조건부 후보다.', '',
                  '## 사이트별 상세와 근거', ''])
    for s in sites:
        lines.extend([f"<a id=\"{s['source_id']}\"></a>", f"### {s['source_id']} — {s['institution']} / {s['name']}", '',
                      f"- 접근 판정: {s['access_status']}. {s['evidence'][0]['result']}",
                      f"- 결정: {s['content_type']} / {s['recommended_strategy']} / {s['risk']['level']}."])
        for u in s['source_urls']:
            lines.append(f"- 원본: [URL]({u['url']}) — {', '.join(u['references'])}.")
        lines.append(f"- 확인된 목록: {('[목록](' + s['list_url'] + ')') if s['list_url'] else '미확인'}.")
        lines.append(f"- 상세 구조: `{s['detail_url_pattern']}`." if s['detail_url_pattern'] else '- 상세 구조/ID: 미확인.')
        lines.append(f"- 상세 본문: {s['detail']['notes']}")
        lines.append(f"- 페이지네이션: {s['pagination']['type']}. {s['pagination']['notes']}")
        lines.append(f"- HTML: {s['html']['notes']}")
        lines.append('- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).')
        lines.append(f"- 로그인: {s['auth']['notes']}")
        lines.append(f"- CAPTCHA/봇 차단: {s['anti_bot']['notes']}")
        lines.append(f"- 제한/후속: {s['blocker'] or '표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.'}")
        lines.append('- 직접 확인 근거:')
        for e in s['evidence']:
            lines.append(f"  - [{e['method']}]({e['url']}): {e['result']}")
        lines.append('')
    lines.extend(['## 재개/인계', '',
                  '- 원본 미제공 blocker는 해소되었다. 전체 47개 수집원을 유지하고 개별 제한 항목을 우선 재확인한다.',
                  '- 공개 웹 본문이 충분한 후보의 페이지 요청을 로컬 네트워크 가능한 환경에서 재현한다.',
                  '- 현재 URL/도구 오류가 있는 사이트는 정상 브라우저와 공식 메뉴에서 확인하고 결과만 갱신한다.',
                  '- 이 단계에서 scraper/모델/정규화/배포 코드는 구현하지 않는다. M02는 별도 요청으로 진행한다.', ''])
    (AUDIT / 'SITE_INVENTORY.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    compose()
