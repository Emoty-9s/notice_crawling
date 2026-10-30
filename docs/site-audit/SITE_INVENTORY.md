# Site Inventory

## 상태와 집계

**PASS** — 이번 요청의 M01 완료 기준 4개를 충족했다. 모든 사이트의 운영/접근 성공을 뜻하지 않는다.
보완 확인일: 2026-10-30 (Asia/Seoul). web 조회는 수집본/캐시를 포함한다.

- 원본 49개 정규화 URL coverage 유지, 수집원 47개/기관·서비스 그룹 30개/호스트 35개 유지.
- 기존 충분히 검증된 6개를 전수 재조사하지 않고, 결정에 필요한 5개만 추가 확인했다.
- 최종 MVP는 7개: 기존 경로 검증 완료 5개 + KISTA 협력기관 모집공고(페이지 이동 대기) + RIPC 협력기관 입찰공고(목록/페이지 검증 대기).
- 사용자 업무 범위 정정: 당사는 특허법인이다. KIPA IP 디딤돌은 수혜기업 대상 게시판이므로 모니터링 및 예비 후보에서 제외한다. SMTECH만 예비 후보로 유지한다.
- 목록·상세·2페이지 확인 6개는 유지. 이 조건을 모두 충족하지 않는 수집원은 41개다.
  이 수에는 인증 전용/옛 경로/수동 보류도 포함하며, 41개 모두에 사유와 MANUAL_ONLY fallback을 기록했다.
- 공통 API/JS 비활성 대조 미확인은 검증되지 않은 사실로 남긴다. API/JS를 쓰지 않는다는 뜻이 아니다.
- 현재 집계/판정의 기준은 sites.yaml과 이 문서다. AUDIT_SUMMARY.json/build_inventory.py는 초기 스냅샷이므로 현행 상태 재생성에 사용하지 않는다.

## 추출과 중복 처리

- 설치 없이 `zipfile`, `struct`, `xml.etree.ElementTree`로 XLSB의 sharedStrings/worksheet 레코드와 관계 XML을 읽었다.
- Sheet1 문자열 셀 403개/하이퍼링크 37개, Sheet2 문자열 셀 27개/하이퍼링크 27개를 확인했다.
- 기관명은 Sheet1 B열의 병합 셀 범위를 적용했다. C31의 3개 URL을 모두 추출했으며 하이퍼링크 대상만 읽어 누락하지 않았다.
- 셀 텍스트와 하이퍼링크가 같은 셀에서 같은 URL이면 1건으로 합쳤다. 같은 셀의 KIAT fragment 변형은 원본 참조를 보존한 채 정규화했다.
- fragment와 과거 PHPSESSID를 제거했다. 세션값은 원본 파일 외 산출물에서 가리고 요청에 재사용하지 않았다.
- KHIDI `siteId=null` 변형, 수출바우처 `active_menu_cd` 변형은 실제 같은 게시판 구조를 확인한 뒤 각각 통합했다.
- 보건산업진흥원/한국보건산업진흥원 이름은 정리했다. KIPA 원본 기관 셀의 대시는 응답의 기관명을 근거로 보완했다.
- 같은 기관이라도 사업정보/입찰/로그인 시스템/다른 게시판 URL은 합치지 않았다. 과거 도메인 동등성도 추정하지 않았다.
- 셀별 원본 URL/표시명/위치는 `SOURCE_EXTRACT.json`, 분류와 상세 근거는 `config/sites.yaml`에 보존한다.

## 조사 방법과 해석 제한

- HTML 직접 수집 가능성은 web 도구가 반환한 `text/html`의 목록/본문을 근거로 잠정 판단했다. 로컬 Python HTTP는 DNS 오류로 실패했다.
- browser host가 없고 native Chrome 제어도 현재 URL 검증 실패로 중단되어 DevTools/XHR, JS 비활성 비교는 수행하지 못했다.
- 따라서 API 미확인 ≠ API 없음, 빈 텍스트 ≠ JS 필수, 로그인 메뉴 존재 ≠ 공고 열람 로그인 필수다.
- 도구의 400/502/Timeout/Cache miss는 사이트의 실제 HTTP 응답 코드나 영구 장애로 단정하지 않는다. 404도 해당 옛 URL에 한정한다.
- SPECIAL은 대기열/인증 전환/미확인 접근을 포함하는 보류 분류다. DYNAMIC/PLAYWRIGHT를 근거 없이 부여하지 않았다.
- CAPTCHA/봇 차단은 성공 표본에서 미관찰 또는 미확인으로 기록한다. 대기열을 CAPTCHA라고 부르지 않는다.
- 미지원/보류는 MANUAL_ONLY로 기록하고, 모든 enabled는 false다. 로그인/접근 통제 우회와 첨부 본문 분석은 하지 않았다.

## 분류 요약

| 분류 | 수집원 수 |
|---|---:|
| STATIC_HTML | 24 |
| JSON_API | 0 |
| DYNAMIC | 0 |
| LOGIN | 1 |
| SPECIAL | 21 |
| UNSUPPORTED | 1 |

## 전체 수집원

| ID | 기관/서비스 | 대상 | 분류 | 전략 | 위험도 | 조사 단계 |
|---|---|---|---|---|---|---|
| [khidi_business](#khidi_business) | 한국보건산업진흥원 | 사업공고 | STATIC_HTML | REQUESTS | LOW | 목록/상세/2페이지 확인 |
| [koat_bid](#koat_bid) | 한국농업기술진흥원 | 입찰정보 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [ipnavi_legacy_board](#ipnavi_legacy_board) | 한국지식재산보호원 | IP-NAVI 기존 게시판 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [ripc_pms](#ripc_pms) | 한국발명진흥회 | 지역지식재산센터 PMS 협력기관 입찰공고 | SPECIAL | MANUAL_ONLY | HIGH | MVP 대상·목록/페이지 검증 대기 |
| [kipa_bid](#kipa_bid) | 한국발명진흥회 | 입찰공고 | STATIC_HTML | REQUESTS | MEDIUM | 목록/상세/2페이지 확인 |
| [kipa_ip_didimdol](#kipa_ip_didimdol) | 한국발명진흥회 | IP 디딤돌 사업공고 | STATIC_HTML | REQUESTS | MEDIUM | 업무 범위 제외 |
| [exportvoucher_notice](#exportvoucher_notice) | 수출바우처 | 수출지원기반활용사업 공지사항 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [mssmiv_notice](#mssmiv_notice) | 제조중소기업혁신바우처 | 중소기업혁신바우처 공지사항 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kista_biz_portal](#kista_biz_portal) | 한국특허전략개발원 | IP통합지원포털 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kista_business_board](#kista_business_board) | 한국특허전략개발원 | 사업정보 게시판 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kista_bid_board](#kista_bid_board) | 한국특허전략개발원 | 입찰공고 게시판 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kista_ipams](#kista_ipams) | 한국특허전략개발원 | 산업재산진단기관 관리시스템 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kista_ippro](#kista_ippro) | 한국특허전략개발원 | IP-R&D 협력기관 모집공고 | STATIC_HTML | REQUESTS | MEDIUM | MVP 선정·페이지 이동 확인 대기 |
| [kista_ipas](#kista_ipas) | 한국특허전략개발원 | 국가 R&D 특허동향 심층분석 사업 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kabit_home](#kabit_home) | 한국BI기술사업화협회 | 대표 홈페이지 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kautm_home](#kautm_home) | 한국대학기술이전협회 | 대표 홈페이지 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [ketep_home](#ketep_home) | 한국에너지기술평가원 | 대표 홈페이지 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [gbsa_bid](#gbsa_bid) | 경기도경제과학진흥원 | 입찰정보 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kist_general](#kist_general) | 한국과학기술연구원 | 일반공지 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kfrm_home](#kfrm_home) | 범부처재생의료기술개발사업단 | 대표 홈페이지 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [yongin_support](#yongin_support) | 용인기업지원시스템 | 지원사업 공고 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kaips_ip_business](#kaips_ip_business) | 한국지식재산서비스협회 | IP사업 게시판 기존 경로 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [smtech_announcements](#smtech_announcements) | 중소기업기술개발사업 종합관리시스템 | R&D 사업공고 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [iris_announcements](#iris_announcements) | 범부처통합연구지원시스템 | IRIS 사업공고 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [g2b_legacy](#g2b_legacy) | 나라장터 | 나라장터 기존 진입점 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [hsbiz_home](#hsbiz_home) | 화성산업진흥원 | 대표 홈페이지 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [rda_bid](#rda_bid) | 농촌진흥청 | 입찰공고 | STATIC_HTML | REQUESTS | MEDIUM | 목록/상세/2페이지 확인 |
| [seoul_rnd_notice](#seoul_rnd_notice) | 서울경제진흥원 | 서울 R&D 지원센터 공지사항 | STATIC_HTML | REQUESTS | MEDIUM | 목록/상세/2페이지 확인 |
| [tipa_legacy_bid](#tipa_legacy_bid) | 중소기업기술정보진흥원 | 입찰구매정보 기존 경로 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [snip_bid](#snip_bid) | 성남산업진흥원 | 입찰공고 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kised_home](#kised_home) | 창업진흥원 | 대표 포털 진입점 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kised_ebid](#kised_ebid) | 창업진흥원 | 계약관리시스템 8443 포트 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kaia_rnd](#kaia_rnd) | 국토교통과학기술진흥원 | 국토교통 R&D 공고 | STATIC_HTML | REQUESTS | MEDIUM | 목록/상세/2페이지 확인 |
| [kiat_home](#kiat_home) | 한국산업기술진흥원 | 대표 홈페이지 공고 미리보기 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [mss_business](#mss_business) | 중소벤처기업부 | 사업공고 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [technopark_main](#technopark_main) | 한국테크노파크진흥회 | 사업공고 및 TP 공고 집계 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [kier_ebid](#kier_ebid) | 한국에너지기술연구원 | 전자입찰 공고 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [krict_bid](#krict_bid) | 한국화학연구원 | 입찰공고 | STATIC_HTML | REQUESTS | MEDIUM | 제한/후속 확인 |
| [hipa_legacy_notice](#hipa_legacy_notice) | 화성산업진흥원 | 과거 hscity 공고·공시 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kised_bid_public](#kised_bid_public) | 창업진흥원 | 공개 입찰공고 | STATIC_HTML | REQUESTS | MEDIUM | 목록/상세/2페이지 확인 |
| [kaia_legacy_bid](#kaia_legacy_bid) | 국토교통과학기술진흥원 | 현재 공식 입찰공고 | STATIC_HTML | REQUESTS | MEDIUM | 현행 목록/상세 확인, 2페이지 미확인 |
| [kaips_ip_business_alt](#kaips_ip_business_alt) | 한국지식재산서비스협회 | IP사업 게시판 별도 경로 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [ipnavi_ipds_login](#ipnavi_ipds_login) | 한국지식재산보호원 | IPDS 전문기관 수행관리 | LOGIN | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [kautm_tlo_news](#kautm_tlo_news) | 한국대학기술이전협회 | TLO 뉴스 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [ketep_legacy_bid](#ketep_legacy_bid) | 한국에너지기술평가원 | 입찰공고 기존 경로 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [khidi_bioagora](#khidi_bioagora) | 한국보건산업진흥원 | 바이오 아고라 | SPECIAL | MANUAL_ONLY | HIGH | 제한/후속 확인 |
| [technopark_legacy_domain](#technopark_legacy_domain) | 한국테크노파크진흥회 | 과거 technopark.kr 도메인 | UNSUPPORTED | MANUAL_ONLY | HIGH | 제한/후속 확인 |

## MVP 후보

최종 MVP는 아래 7개다. 기존 1~5번은 목록/상세/2페이지 검증 근거를 재사용했다.
6번 KISTA는 목록/표본 상세 확인, 페이지 이동은 미확인이다.
7번 RIPC는 입찰 상세와 업무 적합성을 확인했지만 목록/페이지 요청은 미확정으로 MANUAL_ONLY를 유지한다.
6~7번도 MVP 대상이며 구현 경로 검증 완료 5개와는 구분한다.
REQUESTS는 권장 전략명이며 라이브러리를 설치하거나 scraper를 구현하지 않았다.

| 순위 | 수집원 | 상세 식별 / 페이지 이동 | 본문 및 구현 한계 |
|---:|---|---|---|
| 1 | khidi_business — KHIDI 사업공고 | linkId / pageNum | 지원대상/규모/신청기간 웹 본문 확인 |
| 2 | kised_bid_public — 창업진흥원 공개 입찰 | list_no / nPage | 용역명/접수기간/짧은 설명. 자격 세부조건은 첨부/나라장터 참조 |
| 3 | rda_bid — 농촌진흥청 입찰 | dataNo / currPage | 납품기한/장소/입찰방법 텍스트. 세부 규격은 첨부 참조 |
| 4 | seoul_rnd_notice — 서울 R&D 공지 | seqNo / cPage | 설명/일정 웹 본문. 첫 표본 Timeout 이력 고려 |
| 5 | kipa_bid — 한국발명진흥회 입찰 | article_no / pager.offset | 용역명/등록일/짧은 웹 설명. 본문에 없는 상세 자격을 추론하지 않음 |
| 6 | kista_ippro — KISTA IP-R&D 협력기관 모집공고 | annId / annYy / bbsType=ac, 페이지 이동 미확인 | 사용자 지정 MVP. 목록·표본 상세 메타데이터 확인, 2페이지/상세 설명 범위 후속 확인 |
| 7 | ripc_pms — RIPC 협력기관 입찰공고 | bizYear / noticeSeq, 목록/페이지 이동 미확인 | 변리업체 참여 표본 상세 확인. 자동수집 검증 대기, 현재 MANUAL_ONLY / HIGH |

### 예비 후보 (최종 7개에 포함하지 않음)

- SMTECH: 공개 목록/상세는 기존에 확인했지만 정확한 페이지 이동 요청은 재검증에서도 미확정이다.
- SMTECH의 예비 지위는 페이지 요청 성공 증거가 추가될 때만 해제한다. 현재 fallback은 공식 페이지 수동 확인이다.
- KIPA IP 디딤돌은 기술 검증 대기가 아니라 업무 범위 제외다. 수혜기업 전용 게시판이라는 사용자 확인을 근거로 예비 후보에서도 삭제했다.
- KAIA 현재 입찰 게시판은 찾았으나 표본 본문이 HWP 뷰어 중심이고 2페이지 Cache miss이므로 최종 MVP 제외.

## 사이트별 상세와 근거

<a id="khidi_business"></a>
### khidi_business — 한국보건산업진흥원 / 사업공고

- 접근 판정: READABLE_LIST. text/html 목록: 931건, 페이지 1/94, 제목/등록일과 상세 링크 확인.
- 결정: STATIC_HTML / REQUESTS / LOW.
- 원본: [URL](https://www.khidi.or.kr/board?menuId=MENU01108) — Sheet1!R6C3.
- 원본: [URL](https://www.khidi.or.kr/board?menuId=MENU01108&siteId=null) — Sheet1!R72C3, Sheet2!R13C1.
- 확인된 목록: [목록](https://www.khidi.or.kr/board?menuId=MENU01108).
- 상세 구조: `/board/view?menuId=MENU01108&linkId={linkId}`.
- 상세 본문: 표본 상세에서 지원대상/지원규모/신청기간을 웹 텍스트로 확인. 첨부 열지 않음.
- 페이지네이션: QUERY. 목록 링크를 따라 pageNum=2 조회 성공.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 비로그인 웹 조회로 목록/상세/2페이지 열람.
- CAPTCHA/봇 차단: 표본 응답에서 CAPTCHA/차단 화면 미관찰. 장기 수집 허용 여부는 별도.
- 제한/후속: 표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.
- 직접 확인 근거:
  - [web.open](https://www.khidi.or.kr/board?menuId=MENU01108): text/html 목록: 931건, 페이지 1/94, 제목/등록일과 상세 링크 확인.
  - [web.open/click](https://www.khidi.or.kr/board/view?boardStyle=&categoryId=&continent=&country=&linkId=48951946&maxIndex=00489508879998&menuId=MENU01108&minIndex=00489499069998&no1=9999999998&pageNum=1&rowCnt=10&schEndDate=&schStartDate=&schText=&schType=0): 상세 웹 본문과 첨부 링크가 분리되어 있음.
  - [web.open/click](https://www.khidi.or.kr/board?boardStyle=&categoryId=&continent=&country=&maxIndex=00489508879998&menuId=MENU01108&minIndex=00489499069998&pageNum=2&rowCnt=10&schEndDate=&schStartDate=&schText=&schType=0&upDown=0): 2페이지 응답 확인.
  - [web.open](https://www.khidi.or.kr/board?menuId=MENU01108&siteId=null): 동일 MENU01108 사업공고 HTML, 489줄. 원본 URL과 같은 게시판 제목/목록 구조.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.khidi.or.kr/board?menuId=MENU01108). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="koat_bid"></a>
### koat_bid — 한국농업기술진흥원 / 입찰정보

- 접근 판정: READABLE_LIST. text/html 목록 121건, 제목/날짜/첨부 표시. 제목 링크가 도구에서 동일 목록으로 해석됨.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.koat.or.kr/board/bid/list.do) — Sheet1!R11C3.
- 확인된 목록: [목록](https://www.koat.or.kr/board/bid/list.do).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UI_NUMERIC_UNRESOLVED. 1~10/다음/마지막 UI 관찰. 실제 이동 요청 미검증.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 목록은 비로그인 열람; 상세 미확인.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세 링크/페이지 이동 실제 요청 인자 미확인.
- 직접 확인 근거:
  - [web.open](https://www.koat.or.kr/board/bid/list.do): text/html 목록 121건, 제목/날짜/첨부 표시. 제목 링크가 도구에서 동일 목록으로 해석됨.
  - [web.open/click](https://www.koat.or.kr/board/bid/list.do): 제목 링크 클릭 결과 동일 목록. 상세 성공으로 집계하지 않음.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.koat.or.kr/board/bid/list.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="ipnavi_legacy_board"></a>
### ipnavi_legacy_board — 한국지식재산보호원 / IP-NAVI 기존 게시판

- 접근 판정: EMPTY_LIST_SHELL. text/html 응답에 메뉴/검색/표 헤더만 보이고 목록 행과 총 건수가 비어 있음.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.ip-navi.or.kr/ipnavi/board/boardList.navi?boardCode=B00013) — Sheet1!R12C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 게시판 코드 유효성/실제 데이터 로딩 경로 미확인. 빈 행만으로 DYNAMIC 판단 불가.
- 직접 확인 근거:
  - [web.open](https://www.ip-navi.or.kr/ipnavi/board/boardList.navi?boardCode=B00013): text/html 응답에 메뉴/검색/표 헤더만 보이고 목록 행과 총 건수가 비어 있음.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.ip-navi.or.kr/ipnavi/board/boardList.navi?boardCode=B00013). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="ripc_pms"></a>
### ripc_pms — 한국발명진흥회 / 지역지식재산센터 PMS 협력기관 입찰공고

- MVP: **7순위 대상에 추가, 자동수집 검증 대기**. 업무 적합성과 자동수집 구현 가능 검증을 구분한다.
- 결정: SPECIAL / MANUAL_ONLY / HIGH. 목록 데이터 요청 확인 후 자동수집 전략을 재결정한다. 빈 목록만으로 DYNAMIC/LOGIN을 단정하지 않는다.
- 원본: [PMS 진입 URL](https://pms.ripc.org/) — Sheet1!R21C3, Sheet2!R18C1. 원본 추적은 보존한다.
- 사용자 지정 목록: [협력기관 입찰사업 공고](https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do). 기존 기업회원 지원사업 공고와 구분한다.
- 목록 근거(2026-10-30 web.open): 협력기관 메뉴/검색/공고번호/센터/공고제목/기간/예산/상태 헤더 확인. 공고 행과 페이지 이동은 확보하지 못함.
- 상세 구조: `/pms/biz/partner/tenderNotice/info.do?bizYear={year}&noticeSeq={id}`.
- [공개 표본 상세](https://pms.ripc.org/pms/biz/partner/tenderNotice/info.do?bizYear=2026&noticeSeq=553)(web.search 후 web.open): 경기센터 소상공인 IP출원지원 상표(B과제)의 공고명/기간/예산/용역 내용과 변리업체 참여 조건을 비로그인 HTML 텍스트에서 확인. 협력기관 입찰이라는 업무 적합성 근거이며 개별 공고 참여 자격 판단을 대신하지 않는다.
- 첨부: PDF/HWP 링크 존재. 파일 자체는 열지 않음. 표본은 지난 공고이며 현재 접수 중이라는 의미가 아니다.
- 페이지네이션: UNVERIFIED. 공고 행/페이지 UI 및 요청 인자 미확인. 임의 ID 순회는 하지 않음.
- HTML: 표본 상세는 본문 존재. web 수집본/캐시를 포함하며 로컬 HTTP 원문 재현은 미검증. 로컬 urllib는 DNS getaddrinfo failed로 실패했으며 사이트 장애 근거가 아니다.
- JSON/API/JS 필수 여부: 미확인. API/PLAYWRIGHT 필요성을 추측하지 않는다.
- 로그인: 목록 화면/표본 상세는 비로그인 조회. 목록 데이터 인증 필요 여부는 미확인. 표본의 협력기관 회원가입 필수 안내는 제안서 제출에 해당한다.
- CAPTCHA/봇 차단: 이번 응답에서 미관찰.
- 구현 전 확인: 목록 공고 탐색 경로, 데이터 로딩 및 페이지 이동 요청. 자동수집 검증 완료 수에는 미포함.
- 이전 조사: 기업회원 지원공고의 공개 상세/빈 목록 근거는 sites.yaml의 previous_assessment 및 evidence에 역사적 기록으로 보존하며 현재 입찰 목록 검증으로 전용하지 않는다.
- Fallback: **MANUAL_ONLY** — [공식 입찰 목록](https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do) 및 공식 원문 수동 확인. 접근통제를 우회하지 않는다.

<a id="kipa_bid"></a>
### kipa_bid — 한국발명진흥회 / 입찰공고

- 접근 판정: READABLE_LIST. text/html 목록 2081건, 페이지 1/209. 상세와 pager.offset=10 조회 성공.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.kipa.org/kipa/notice/kw_0402.jsp) — Sheet1!R24C3, Sheet2!R17C1.
- 확인된 목록: [목록](https://www.kipa.org/kipa/notice/kw_0402.jsp).
- 상세 구조: `/kipa/notice/kw_0402.jsp?mode=view&article_no={id}&board_no=15`.
- 상세 본문: 표본 상세는 용역명/나라장터 안내 중심으로 짧음. 핵심 조건은 외부/첨부에 있어 본문만 판별 제약.
- 페이지네이션: OFFSET. 목록의 2페이지 링크가 offset=10이며 응답 열람 성공.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 목록/상세/2페이지 비로그인 열람.
- CAPTCHA/봇 차단: 표본 응답에서 CAPTCHA/차단 화면 미관찰.
- 제한/후속: 표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.
- 직접 확인 근거:
  - [web.open](https://www.kipa.org/kipa/notice/kw_0402.jsp): text/html 목록 2081건, 페이지 1/209. 상세와 pager.offset=10 조회 성공.
  - [web.open/click](https://www.kipa.org/kipa/notice/kw_0402.jsp?article_no=134746&board_no=15&board_wrapper=/kipa/notice/kw_0402.jsp&mode=view&pager.offset=0): 상세에 짧은 설명, 나라장터 링크, HWP 첨부 링크.
  - [web.open/click](https://www.kipa.org/kipa/notice/kw_0402.jsp?board_no=15&mode=list&pager.offset=10): 2페이지 조회 성공.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kipa.org/kipa/notice/kw_0402.jsp). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kipa_ip_didimdol"></a>
### kipa_ip_didimdol — 한국발명진흥회 / IP 디딤돌 사업공고

- 접근 판정: READABLE_LIST.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 분류 근거: HTML 응답의 텍스트에서 목록/본문을 확인한 기준의 잠정 분류. 로컬 HTTP 재현 검증은 남아 있음.
- 원본: [URL](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp) — Sheet1!R25C3.
- 확인된 목록: [목록](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp).
- 상세 구조: `/kipa/ip001/kw_business_1602.jsp?mode=view&article_no={id}&board_no=28&default:category_id=239`.
- 상세 본문: 표본 상세에 지원대상/지원내용/신청방법을 텍스트로 확인.
- 페이지네이션: OFFSET. pager.offset=10 링크와 파라미터 축약 URL 2종 재확인 실패. 페이지 이동 성공으로 판정하지 않음.
- HTML: web 변환 응답 기준이며 로컬 HTTP 원문 재현은 미검증.
- JSON/API 및 JS 필수 여부: 미확인. 빈 목록이나 도구 오류만으로 판단하지 않음.
- 로그인: 목록과 표본 상세는 비로그인 조회.
- CAPTCHA/봇 차단: 미확인
- 업무 범위 결정: **모니터링 대상 제외**. 사용자 확인에 따르면 당사는 특허법인이며 이 게시판은 수혜기업 대상이다. 예비 후보 및 추가 기술 검증 대상에서도 제외한다. 아래 기술 조사 이력은 원본 추적용으로만 유지한다.
- 직접 확인 근거 (초기 + 보완):
  - [초기 web.open](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp): 원본 기관 셀은 대시(-). 응답의 기관명과 IP 디딤돌 메뉴로 보완. 목록 23건/3페이지.
  - [초기 web.open/click](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?article_no=122253&board_no=28&board_wrapper=/kipa/ip001/kw_business_1602.jsp&default:category_id=239&mode=view&pager.offset=0): 2026 IP 디딤돌 사업 설명 텍스트 확인.
  - [초기 web.open/click](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?board_no=28&default:category_id=239&mode=list&pager.offset=10): 도구 Cache miss. 성공으로 집계하지 않음.
  - [보완 web.open](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp): 보완 조사: 목록 HTML 응답과 23건/3페이지 표시 확인. 상세의 기존 확인 근거는 유지.
  - [보완 web.open](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?board_no=28&default:category_id=239&mode=list&pager.offset=10): 보완 조사: Cache miss. 목록 페이지 이동 미검증.
  - [보완 web.open](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?pager.offset=10): 보완 조사: 도구 접근 불가. 우회/추가 반복 없이 보류.
  - [보완 web.open](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp?board_no=28&mode=list&pager.offset=10): 보완 조사: 도구 접근 불가. 우회/추가 반복 없이 보류.
- 범위 제외 처리: 자동수집/수동 모니터링/예비 후보로 운영하지 않는다. 원본 URL coverage만 유지하며, 사용자 범위 변경 시에만 재검토한다.

<a id="exportvoucher_notice"></a>
### exportvoucher_notice — 수출바우처 / 수출지원기반활용사업 공지사항

- 접근 판정: READABLE_LIST. text/html 목록 905건과 페이지 1~10/다음 표시. 제목에 이동 가능한 링크가 노출되지 않음.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1) — Sheet1!R27C3.
- 원본: [URL](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1&active_menu_cd=EZ005004000) — Sheet2!R26C1.
- 확인된 목록: [목록](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UI_NUMERIC_UNRESOLVED. 페이지 UI 확인, 인자/전송방식 미확인.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 목록 비로그인 조회. 로그인 메뉴 자체는 로그인 필수 근거가 아님.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세 URL/본문 및 페이지 요청 검증 필요.
- 직접 확인 근거:
  - [web.open](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1): text/html 목록 905건과 페이지 1~10/다음 표시. 제목에 이동 가능한 링크가 노출되지 않음.
  - [web.open](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1&active_menu_cd=EZ005004000): active_menu_cd 변형에서 동일 공지사항 905건/제목/페이지 구조 확인.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="mssmiv_notice"></a>
### mssmiv_notice — 제조중소기업혁신바우처 / 중소기업혁신바우처 공지사항

- 접근 판정: QUEUE_PAGE. 요청이 /_queue/index.html 대기열로 이동하고 순차 접속 안내를 표시.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.mssmiv.com/portal/board/BoardList?bbsId=1) — Sheet1!R29C3, Sheet2!R21C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 접속 대기열은 관찰했으나 CAPTCHA나 봇 차단으로 확정하지 않음.
- 제한/후속: 대기열 때문에 실제 목록/상세 미확인.
- 직접 확인 근거:
  - [web.open](https://www.mssmiv.com/portal/board/BoardList?bbsId=1): 요청이 /_queue/index.html 대기열로 이동하고 순차 접속 안내를 표시.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.mssmiv.com/portal/board/BoardList?bbsId=1). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kista_biz_portal"></a>
### kista_biz_portal — 한국특허전략개발원 / IP통합지원포털

- 접근 판정: READABLE_PORTAL. text/html 포털에 여러 사업 공고/기간과 상세 링크를 제공. 공개 상세도 확인.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://biz.kista.re.kr/main.do) — Sheet1!R31C3.
- 확인된 목록: [목록](https://biz.kista.re.kr/main.do).
- 상세 구조: `/ippro/com/iprndMain/selectBusinessAnnounceView.do?annId={id}&annYy={year}&bbsType={type}`.
- 상세 본문: 표본 상세는 공고명/접수기간/사업구분 메타데이터. 대상과제는 비어 있음.
- 페이지네이션: PORTAL_PREVIEW. 포털은 미리보기. 사업별 전체 목록 페이지 이동은 미확인.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 표본 공고 상세는 로그인 없이 열림. 사업 신청은 별도.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 사업별 공고 전체 범위와 페이지 이동 미확정.
- 직접 확인 근거:
  - [web.open](https://biz.kista.re.kr/main.do): text/html 포털에 여러 사업 공고/기간과 상세 링크를 제공. 공개 상세도 확인.
  - [web.open/click](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?DepthCode1=3&DepthCode2=1&annId=3&annYy=2026&bbsType=ac): 협력기관 풀 공고명과 접수기간 열람.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://biz.kista.re.kr/main.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kista_business_board"></a>
### kista_business_board — 한국특허전략개발원 / 사업정보 게시판

- 접근 판정: READABLE_LIST. text/html 목록 859건. 표에 제목/등록일이 보이나 상세 링크가 도구에 노출되지 않음.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000382) — Sheet1!R31C3.
- 확인된 목록: [목록](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000382).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: QUERY_CONTEXT_REQUIRED. 2 링크는 /user/board.do?pageIndex=2로 해석되어 메인으로 이동. bbsId 보존 필요성만 관찰, 동작 미검증.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세 ID/요청 방식과 bbsId 유지 페이지 요청 검증 필요.
- 직접 확인 근거:
  - [web.open](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000382): text/html 목록 859건. 표에 제목/등록일이 보이나 상세 링크가 도구에 노출되지 않음.
  - [web.open/click](https://www.kista.re.kr/user/board.do?pageIndex=2): 메인 /main.do로 이동, 유효한 게시판 2페이지가 아님.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000382). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kista_bid_board"></a>
### kista_bid_board — 한국특허전략개발원 / 입찰공고 게시판

- 접근 판정: READABLE_LIST. text/html 목록 1279건. 제목/진행상태가 있으나 상세 URL 미확인.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000442) — Sheet1!R31C3, Sheet2!R25C1.
- 확인된 목록: [목록](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000442).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: QUERY_CONTEXT_REQUIRED. 2 링크 조회에서 bbsId 없이 메인으로 이동. 1/5 표시는 전체 페이지수로 신뢰하지 않음.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세/페이지 요청 컨텍스트 추가 확인 필요.
- 직접 확인 근거:
  - [web.open](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000442): text/html 목록 1279건. 제목/진행상태가 있으나 상세 URL 미확인.
  - [web.open/click](https://www.kista.re.kr/user/board.do?pageIndex=2): 메인으로 이동.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000442). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kista_ipams"></a>
### kista_ipams — 한국특허전략개발원 / 산업재산진단기관 관리시스템

- 접근 판정: READABLE_PORTAL. 원본 /ipams/는 현재 IEPMS 제목과 공개 공지 제목/날짜를 표시. 로그인 폼도 존재.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://biz.kista.re.kr/ipams/) — Sheet1!R33C3.
- 확인된 목록: [목록](https://biz.kista.re.kr/ipams/).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 로그인 폼과 공개 미리보기 공존. 공고 열람 로그인 필수 여부 미확인.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 모집공고/공지의 실제 전체 목록, 상세/페이지 이동 미확인.
- 직접 확인 근거:
  - [web.open](https://biz.kista.re.kr/ipams/): 원본 /ipams/는 현재 IEPMS 제목과 공개 공지 제목/날짜를 표시. 로그인 폼도 존재.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://biz.kista.re.kr/ipams/). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kista_ippro"></a>
### kista_ippro — 한국특허전략개발원 / IP-R&D 협력기관 모집공고

- MVP: **사용자 지정으로 선정(6순위)**. 예비 후보가 아니며 페이지 이동 검증 완료와는 구분한다.
- 결정: STATIC_HTML / REQUESTS / MEDIUM. 공개 HTML 조회를 우선 재현하되 실제 수집 코드는 구현하지 않았다.
- 원본: [기존 진입 URL](https://biz.kista.re.kr/ippro/uat/uia/egovLoginUsr.do) — Sheet1!R34C3, Sheet2!R19C1. 원본 추적은 보존한다.
- 사용자 지정 목록: [협력기관 모집공고](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac). bbsType=ac로 수집 범위를 지정한다.
- 목록 확인: 2026-10-30 web.open 응답에서 총 773건, 첫 페이지 20개 행, 공고명/구분/접수기간 확인. 수집본/캐시를 포함한다.
- 상세 구조: `/ippro/com/iprndMain/selectBusinessAnnounceView.do?annId={id}&annYy={year}&bbsType=ac`.
- [표본 상세](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?DepthCode1=3&DepthCode2=1&annId=3&annYy=2026&bbsType=ac): 비로그인으로 공고명/담당부서/연도/접수기간 확인. 상세 설명 및 첨부 내용은 확보하지 못했으며 신청 자격은 추론하지 않는다.
- 페이지네이션: UI_NUMERIC_UNRESOLVED. 숫자 2~20 UI가 있지만 web.click의 2 링크는 같은 URL/첫 페이지 목록을 반환했다. 실제 2페이지 성공으로 집계하지 않으며 요청 인자는 미확인이다.
- HTML: web text/html 변환 결과 기준. 로컬 HTTP 원문 재현은 미검증.
- JSON/API 및 JS 필수 여부: 미확인. 클릭 해석 한계만으로 DYNAMIC이나 PLAYWRIGHT 필수로 단정하지 않는다.
- 로그인: 목록/표본 상세 조회에는 불필요. 신청 절차 인증 여부와 구분한다.
- CAPTCHA/봇 차단: 이번 표본 응답에서 미관찰. 운영 안정성 검증을 의미하지 않는다.
- 구현 전 확인: 페이지 이동 요청, 상세 설명/첨부 제공 범위, 로컬 HTTP 재현.
- Fallback: **MANUAL_ONLY** — [공식 목록](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac)에서 수동 확인. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kista_ipas"></a>
### kista_ipas — 한국특허전략개발원 / 국가 R&D 특허동향 심층분석 사업

- 접근 판정: READABLE_PORTAL. 로그인 URL에서 text/html에 공고 제목/상태/날짜가 보임.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://biz.kista.re.kr/ipas/uat/uia/egovLoginUsr.do) — Sheet1!R37C3.
- 확인된 목록: [목록](https://biz.kista.re.kr/ipas/uat/uia/egovLoginUsr.do).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 공개 미리보기와 로그인 폼 공존. 상세 열람의 로그인 필요 여부 미확인.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세/전체 목록/페이지 이동 미확인.
- 직접 확인 근거:
  - [web.open](https://biz.kista.re.kr/ipas/uat/uia/egovLoginUsr.do): 로그인 URL에서 text/html에 공고 제목/상태/날짜가 보임.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://biz.kista.re.kr/ipas/uat/uia/egovLoginUsr.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kabit_home"></a>
### kabit_home — 한국BI기술사업화협회 / 대표 홈페이지

- 접근 판정: TOOL_ERROR. 원본 HTTP 조회와 HTTPS 재확인 모두 웹 도구 Timeout.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.kabit.or.kr/) — Sheet1!R42C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 도구 접근 실패. 사이트 폐쇄/로그인/JS 여부로 해석하지 않음.
- 직접 확인 근거:
  - [web.open](http://www.kabit.or.kr/): 원본 HTTP 조회와 HTTPS 재확인 모두 웹 도구 Timeout.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.kabit.or.kr/). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kautm_home"></a>
### kautm_home — 한국대학기술이전협회 / 대표 홈페이지

- 접근 판정: TOOL_ERROR. 원본 HTTP 요청의 HTTPS 조회에서 웹 도구 502 Bad Gateway.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.kautm.net/) — Sheet1!R43C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 본문과 목록 경로 확인 불가. 실제 서버 상태와 도구 오류를 구분해야 함.
- 직접 확인 근거:
  - [web.open](http://www.kautm.net/): 원본 HTTP 요청의 HTTPS 조회에서 웹 도구 502 Bad Gateway.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.kautm.net/). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="ketep_home"></a>
### ketep_home — 한국에너지기술평가원 / 대표 홈페이지

- 접근 판정: TOOL_ERROR. 웹 도구 Timeout. 원본의 별도 입찰 경로도 접근 제한.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.ketep.re.kr/) — Sheet1!R45C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 공개 목록/상세/페이지 이동 미확인.
- 직접 확인 근거:
  - [web.open](https://www.ketep.re.kr/): 웹 도구 Timeout. 원본의 별도 입찰 경로도 접근 제한.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.ketep.re.kr/). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="gbsa_bid"></a>
### gbsa_bid — 경기도경제과학진흥원 / 입찰정보

- 접근 판정: TOOL_ERROR. 원본 게시판과 홈페이지 직접 조회는 웹 도구 Bad Request. 공식 도메인 검색 결과에는 입찰 제목 존재.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.gbsa.or.kr/board/bid_info.do) — Sheet1!R46C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 검색 인덱스는 직접 게시판 조회 성공 증거가 아님. 목록/상세 요청 재확인 필요.
- 직접 확인 근거:
  - [web.open](https://www.gbsa.or.kr/board/bid_info.do): 원본 게시판과 홈페이지 직접 조회는 웹 도구 Bad Request. 공식 도메인 검색 결과에는 입찰 제목 존재.
  - [web.open/click](https://www.gbsa.or.kr/): 공식 도메인 검색 인덱스에 입찰정보가 있으나 web.open은 Bad Request.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.gbsa.or.kr/board/bid_info.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kist_general"></a>
### kist_general — 한국과학기술연구원 / 일반공지

- 접근 판정: TOOL_ERROR. 원본은 웹 도구 Bad Request. mode=list 추가 조회도 도구 접근 불가.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.kist.re.kr/ko/notice/general-notice.do) — Sheet1!R47C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 원본 게시판 접근 검증 필요.
- 직접 확인 근거:
  - [web.open](https://www.kist.re.kr/ko/notice/general-notice.do): 원본은 웹 도구 Bad Request. mode=list 추가 조회도 도구 접근 불가.
  - [web.open/click](https://www.kist.re.kr/ko/notice/general-notice.do?mode=list): 웹 도구 접근 불가.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kist.re.kr/ko/notice/general-notice.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kfrm_home"></a>
### kfrm_home — 범부처재생의료기술개발사업단 / 대표 홈페이지

- 접근 판정: TOOL_ERROR. 원본 경로와 도메인 루트 재조회 모두 웹 도구 502 Bad Gateway.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.kfrm.org/doc/html/main/main.asp) — Sheet1!R48C3, Sheet2!R11C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 원본 및 대체 루트에서 목록 접근 불가.
- 직접 확인 근거:
  - [web.open](http://www.kfrm.org/doc/html/main/main.asp): 원본 경로와 도메인 루트 재조회 모두 웹 도구 502 Bad Gateway.
  - [web.open/click](http://www.kfrm.org/): HTTPS 조회로 도구 502.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.kfrm.org/doc/html/main/main.asp). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="yongin_support"></a>
### yongin_support — 용인기업지원시스템 / 지원사업 공고

- 접근 판정: ALTERNATIVE_LIST. 포털 공개 사업 제목/기간 확인. 더보기에서 /application.do 목록 398건 확인.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://ybs.ypa.or.kr/portal.do) — Sheet1!R49C3, Sheet2!R10C1.
- 확인된 목록: [목록](https://ybs.ypa.or.kr/application.do).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UI_UNRESOLVED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 로그인 안내는 있으나 목록은 공개. 상세/신청은 구분 필요.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세 URL 및 페이지 이동 요청 미확인.
- 직접 확인 근거:
  - [web.open](https://ybs.ypa.or.kr/portal.do): 포털 공개 사업 제목/기간 확인. 더보기에서 /application.do 목록 398건 확인.
  - [web.open/click](https://ybs.ypa.or.kr/application.do): 지원사업 제목/기간 목록 398건 열람.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://ybs.ypa.or.kr/application.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kaips_ip_business"></a>
### kaips_ip_business — 한국지식재산서비스협회 / IP사업 게시판 기존 경로

- 접근 판정: TOOL_ERROR. 원본 HTTP의 HTTPS 조회에서 웹 도구 502 Bad Gateway.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.kaips.or.kr/bbs/kaips_12) — Sheet1!R50C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 원본 목록 접근 실패. 별도 Sheet2 경로도 Timeout.
- 직접 확인 근거:
  - [web.open](http://www.kaips.or.kr/bbs/kaips_12): 원본 HTTP의 HTTPS 조회에서 웹 도구 502 Bad Gateway.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.kaips.or.kr/bbs/kaips_12). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="smtech_announcements"></a>
### smtech_announcements — 중소기업기술개발사업 종합관리시스템 / R&D 사업공고

- 접근 판정: ALTERNATIVE_LIST.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 분류 근거: HTML 응답의 텍스트에서 목록/본문을 확인한 기준의 잠정 분류. 로컬 HTTP 재현 검증은 남아 있음.
- 원본: [URL](https://www.smtech.go.kr/front/ifg/no/notice02_intro.do) — Sheet1!R51C3.
- 확인된 목록: [목록](https://www.smtech.go.kr/front/ifg/no/notice02_list.do).
- 상세 구조: `/front/ifg/no/notice02_detail.do?ancmId={id}&aplySn={n}&dtlAncmSn={n}&buclCd={code}`.
- 상세 본문: 표본 수출지원프로그램 상세에서 사업 설명/시작일/종료일 확인. 세부 조건은 첨부 참조.
- 페이지네이션: UI_NUMERIC_UNRESOLVED. 페이지 UI와 상세 ID는 기존 근거 유지. pageIndex=2 및 검색 인자 포함 URL은 재확인 실패; 확인되지 않은 GET/POST 방식을 확정하지 않음.
- HTML: web 변환 응답 기준이며 로컬 HTTP 원문 재현은 미검증.
- JSON/API 및 JS 필수 여부: 미확인. 빈 목록이나 도구 오류만으로 판단하지 않음.
- 로그인: 로그인 안내 모달 텍스트와 별개로 표본 공고 목록/상세 비로그인 조회 가능.
- CAPTCHA/봇 차단: 미확인
- 미확인/보류 사유: 보완 조사에서도 pageIndex=2 단독/검색 인자 포함 URL 모두 도구 접근 불가. 정확한 페이지 요청의 메서드/필터/세션 요구 미확정. 최종 MVP 제외.
- 직접 확인 근거 (초기 + 보완):
  - [초기 web.open](https://www.smtech.go.kr/front/ifg/no/notice02_intro.do): 원본은 연간 일정표. /notice02_list.do에서 공고/접수기간 목록, 표본 상세 웹 본문 확인.
  - [초기 web.open/click](https://www.smtech.go.kr/front/ifg/no/notice02_list.do): 공고 목록 HTML 텍스트 확인.
  - [초기 web.open/click](https://www.smtech.go.kr/front/ifg/no/notice02_detail.do?ancmId=S02881&aplySn=1&buclCd=S9121&buclYy=&dtlAncmSn=1&pageIndex=1&schdSe=MO5005&searchCondition=&searchKeyword=): URL 내 세션 식별자를 제외하고 공개 상세 열람 성공.
  - [초기 web.open/click](https://www.smtech.go.kr/front/ifg/no/notice02_list.do?pageIndex=2): 도구 접근 불가. 페이지 이동 성공으로 집계하지 않음.
  - [보완 web.open](https://www.smtech.go.kr/front/ifg/no/notice02_list.do): 보완 조사: 목록 text/html 응답 열림. 상세는 기존 공개 표본 근거 유지.
  - [보완 web.open](https://www.smtech.go.kr/front/ifg/no/notice02_list.do?pageIndex=2): 보완 조사: 도구 접근 불가. 페이지 이동 성공으로 집계하지 않음.
  - [보완 web.open](https://www.smtech.go.kr/front/ifg/no/notice02_list.do?pageIndex=2&searchCondition=&searchKeyword=): 보완 조사: 도구 접근 불가. 페이지 이동 성공으로 집계하지 않음.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.smtech.go.kr/front/ifg/no/notice02_list.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="iris_announcements"></a>
### iris_announcements — 범부처통합연구지원시스템 / IRIS 사업공고

- 접근 판정: ALTERNATIVE_LIST. 메인 사업공고 링크에서 공개 목록 /contents/retrieveBsnsAncmBtinSituListView.do 확인. 17건/2페이지.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.iris.go.kr/main.do) — Sheet1!R52C3, Sheet2!R16C1.
- 확인된 목록: [목록](https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UI_UNRESOLVED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 사업공고 목록은 공개. 연구업무 로그인과 분리.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 상세 식별자/클릭 요청 및 페이지 이동 미확인.
- 직접 확인 근거:
  - [web.open](https://www.iris.go.kr/main.do): 메인 사업공고 링크에서 공개 목록 /contents/retrieveBsnsAncmBtinSituListView.do 확인. 17건/2페이지.
  - [web.open/click](https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do): 제목/공고일/공고번호 및 1/2 페이지 표시.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="g2b_legacy"></a>
### g2b_legacy — 나라장터 / 나라장터 기존 진입점

- 접근 판정: SSO_REDIRECT. 원본 /index.jsp 요청이 sso.g2b.go.kr OIDC 인증 흐름으로 이동하며 웹 도구에서 열리지 않음.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.g2b.go.kr/index.jsp) — Sheet1!R53C3, Sheet2!R14C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: SSO 리다이렉트 관찰. 모든 공개 공고가 로그인 필수라는 의미는 아님.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 이 진입점으로 비로그인 공고 조회를 확인하지 못함. 공개 API/새 화면은 별도 검증 필요.
- 직접 확인 근거:
  - [web.open](https://www.g2b.go.kr/index.jsp): 원본 /index.jsp 요청이 sso.g2b.go.kr OIDC 인증 흐름으로 이동하며 웹 도구에서 열리지 않음.
  - [web.open/click](https://www.g2b.go.kr/index.jsp): 동적 OIDC state/nonce 값은 기록/재사용하지 않음.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.g2b.go.kr/index.jsp). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="hsbiz_home"></a>
### hsbiz_home — 화성산업진흥원 / 대표 홈페이지

- 접근 판정: TOOL_ERROR. 원본 루트는 웹 도구 Timeout. 공식 검색에 새 /bbs/.../view.do 상세는 있으나 직접 열기는 Cache miss.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.hsbiz.or.kr/) — Sheet1!R63C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 현재 공식 목록/상세 직접 검증 필요. 첨부 다운로드 API의 존재만으로 JSON_API 분류하지 않음.
- 직접 확인 근거:
  - [web.open](https://www.hsbiz.or.kr/): 원본 루트는 웹 도구 Timeout. 공식 검색에 새 /bbs/.../view.do 상세는 있으나 직접 열기는 Cache miss.
  - [web.open/click](https://www.hsbiz.or.kr/bbs/BBSMSTR_000000000041/view.do?nttId=B000000002215Hs8cN5): 검색 인덱스에는 입찰 상세, 직접 조회는 도구 Cache miss.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.hsbiz.or.kr/). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="rda_bid"></a>
### rda_bid — 농촌진흥청 / 입찰공고

- 접근 판정: READABLE_LIST. 공개 HTML 목록 3859건, 표본 상세와 currPage=2 조회 성공.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry) — Sheet1!R64C3, Sheet2!R2C1.
- 확인된 목록: [목록](https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry).
- 상세 구조: `/board/board.do?mode=updateCnt&boardId=bidancm&prgId=bid_bidancmEntry&dataNo={id}`.
- 상세 본문: 표본에 입찰 대상/납품기한/장소/방법 텍스트 존재. 세부 규격은 첨부에만 있어 본문 판별 범위 제한.
- 페이지네이션: QUERY. 목록 2 링크의 currPage=2 응답 확인.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 비로그인 목록/상세/2페이지 열람.
- CAPTCHA/봇 차단: 표본 응답에서 CAPTCHA/차단 미관찰.
- 제한/후속: 표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.
- 직접 확인 근거:
  - [web.open](https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry): 공개 HTML 목록 3859건, 표본 상세와 currPage=2 조회 성공.
  - [web.open/click](https://www.rda.go.kr/board/board.do?boardId=bidancm&currPage=1&dataNo=100000813836&menu_id=ofc&mode=updateCnt&prgId=bid_bidancmEntry&searchKey=&searchVal=): 공고 설명 웹 본문 확인.
  - [web.open/click](https://www.rda.go.kr/board/board.do?boardId=bidancm&catgId=&currPage=2&mode=list&prgId=bid_bidancmEntry&searchEDate=&searchKey=&searchOrgDeptKey=&searchOrgDeptVal=&searchSDate=&searchVal=): 2페이지 열람 성공.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="seoul_rnd_notice"></a>
### seoul_rnd_notice — 서울경제진흥원 / 서울 R&D 지원센터 공지사항

- 접근 판정: READABLE_LIST. 공개 HTML 제목/등록일 목록. 첫 상세 seqNo=1130은 Timeout, 다른 표본 seqNo=1129는 성공.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://seoul.rnbd.kr/client/c030200/c030200_00.jsp) — Sheet1!R65C3, Sheet2!R3C1.
- 확인된 목록: [목록](https://seoul.rnbd.kr/client/c030200/c030200_00.jsp).
- 상세 구조: `/client/c030200/c030200_04.jsp?seqNo={id}`.
- 상세 본문: 표본 선정 결과 안내에서 웹 설명/일정/문의 내용 확인. 첫 표본 Timeout 이력 있음.
- 페이지네이션: QUERY. 목록의 2 링크 cPage=2 응답 확인.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 공개 공지 목록/상세 조회 성공. 신청/과제번호 확인의 로그인 요구와 구분.
- CAPTCHA/봇 차단: 성공한 표본에서 CAPTCHA/차단 미관찰.
- 제한/후속: 표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.
- 직접 확인 근거:
  - [web.open](https://seoul.rnbd.kr/client/c030200/c030200_00.jsp): 공개 HTML 제목/등록일 목록. 첫 상세 seqNo=1130은 Timeout, 다른 표본 seqNo=1129는 성공.
  - [web.open/click](https://seoul.rnbd.kr/client/c030200/c030200_04.jsp?cPage=1&sField=&sWord=&seqNo=1129): 대체 표본 상세 웹 본문 열람.
  - [web.open/click](https://seoul.rnbd.kr/client/c030200/c030200_00.jsp?cPage=2&sField=&sWord=): 2페이지 열람 성공.
  - [web.open/click](https://seoul.rnbd.kr/client/c030200/c030200_04.jsp?cPage=1&sField=&sWord=&seqNo=1130): 첫 상세는 도구 Timeout.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://seoul.rnbd.kr/client/c030200/c030200_00.jsp). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="tipa_legacy_bid"></a>
### tipa_legacy_bid — 중소기업기술정보진흥원 / 입찰구매정보 기존 경로

- 접근 판정: REDIRECT_OTHER.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 분류 근거: 직접 조회와 검색 인덱스가 불일치하므로 SPECIAL/보류 유지. 로그인 또는 JS 필수라고 추정하지 않음.
- 원본: [URL](https://www.tipa.or.kr/s040305) — Sheet1!R66C3, Sheet2!R4C1.
- 확인된 목록: 미확인.
- 상세 구조: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 변환 응답 기준이며 로컬 HTTP 원문 재현은 미검증.
- JSON/API 및 JS 필수 여부: 미확인. 빈 목록이나 도구 오류만으로 판단하지 않음.
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 미확인/보류 사유: 공식 도메인 검색에는 입찰 목록/상세가 있으나 실제 목록·2페이지·상세 직접 조회는 모두 /eng로 이동. 검색 결과만으로 STATIC_HTML로 승격하지 않고 MANUAL_ONLY 유지.
- 직접 확인 근거 (초기 + 보완):
  - [초기 web.open](https://www.tipa.or.kr/s040305): 원본 /s040305가 /eng로 이동하고 읽을 수 있는 본문 0줄.
  - [초기 web.open/click](https://www.tipa.or.kr/eng): 원본 조회의 도착 URL. 목록/상세 미확인.
  - [보완 web.open](https://tipa.or.kr/s040305): 보완 조사: 직접 조회는 /eng로 이동, 본문 0줄.
  - [보완 web.open](https://tipa.or.kr/s040305/index/page/2): 보완 조사: 검색에서 발견한 목록 2페이지 경로를 직접 열었으나 /eng로 이동.
  - [보완 web.open](https://tipa.or.kr/s040305/view/id/17776): 보완 조사: 검색에서 발견한 공고 상세를 직접 열었으나 /eng로 이동.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.tipa.or.kr/s040305). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="snip_bid"></a>
### snip_bid — 성남산업진흥원 / 입찰공고

- 접근 판정: TOOL_ERROR. 원본 게시판은 웹 도구 접근 불가. 루트는 text/html이나 본문 0줄.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.snip.or.kr/SNIP/contents/notice12.do) — Sheet1!R67C3, Sheet2!R5C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 게시판 접근/렌더링 확인 필요. 원본만으로 STATIC 또는 DYNAMIC 단정 불가.
- 직접 확인 근거:
  - [web.open](https://www.snip.or.kr/SNIP/contents/notice12.do): 원본 게시판은 웹 도구 접근 불가. 루트는 text/html이나 본문 0줄.
  - [web.open/click](https://www.snip.or.kr/): 본문 0줄.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.snip.or.kr/SNIP/contents/notice12.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kised_home"></a>
### kised_home — 창업진흥원 / 대표 포털 진입점

- 접근 판정: ALTERNATIVE_LIST. 기관/K-Startup 선택 화면. 원본 Sheet2 입찰 안내 경로에서 별도 공개 입찰 게시판 확인.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.kised.or.kr/) — Sheet1!R68C3.
- 확인된 목록: [목록](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 실제 조사 상세는 kised_bid_public 항목 참조. 원본 루트 자체는 공고 목록이 아님.
- 직접 확인 근거:
  - [web.open](https://www.kised.or.kr/): 기관/K-Startup 선택 화면. 원본 Sheet2 입찰 안내 경로에서 별도 공개 입찰 게시판 확인.
  - [web.open/click](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000): 기관 공개 입찰 목록. 대표 루트와 별도 경로.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kised_ebid"></a>
### kised_ebid — 창업진흥원 / 계약관리시스템 8443 포트

- 접근 판정: TOOL_UNSUPPORTED_URL. 웹 도구가 원본 8443 URL을 invalid ref_id/arguments로 처리해 본문 조회 자체가 불가.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://ebid.kised.or.kr:8443/opro/main/emgncLoginForm.do) — Sheet1!R69C3, Sheet2!R6C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 8443 포트 접근 도구 제약. 로그인 필요 여부 미확인. 공개 대안 kised_bid_public 존재.
- 직접 확인 근거:
  - [web.open](https://ebid.kised.or.kr:8443/opro/main/emgncLoginForm.do): 웹 도구가 원본 8443 URL을 invalid ref_id/arguments로 처리해 본문 조회 자체가 불가.
  - [web.open/click](https://www.kised.or.kr/menu.es?mid=a10313000000): 공식 안내에 계약관리시스템 링크 존재. 조회 오류를 로그인 증거로 보지 않음.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kaia_rnd"></a>
### kaia_rnd — 국토교통과학기술진흥원 / 국토교통 R&D 공고

- 접근 판정: READABLE_LIST. HTML 목록 1224건/123페이지. 상세와 page=2 조회 성공.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.kaia.re.kr/KAIA/contents/K30101000000.do) — Sheet1!R70C3.
- 확인된 목록: [목록](https://www.kaia.re.kr/KAIA/contents/K30101000000.do).
- 상세 구조: `/KAIA/contents/K30101000000.do?schM=view&id={id}`.
- 상세 본문: 표본 상세는 제목/기간과 PDF 본문 문서뷰어 중심. 핵심 설명의 HTML 본문 확보 실패. 첨부 분석 제외 정책상 MVP 우선 제외.
- 페이지네이션: QUERY. 2페이지 링크 page=2 응답 확인.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 목록/상세/2페이지는 공개.
- CAPTCHA/봇 차단: 표본에서 CAPTCHA/차단 미관찰.
- 제한/후속: 표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.
- 직접 확인 근거:
  - [web.open](https://www.kaia.re.kr/KAIA/contents/K30101000000.do): HTML 목록 1224건/123페이지. 상세와 page=2 조회 성공.
  - [web.open/click](https://www.kaia.re.kr/KAIA/contents/K30101000000.do?id=20260820101844013278&schM=view): PDF 본문 뷰어 링크, 제목/기간만 확인.
  - [web.open/click](https://www.kaia.re.kr/KAIA/contents/K30101000000.do?page=2): 2페이지 열람 성공.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kaia.re.kr/KAIA/contents/K30101000000.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kiat_home"></a>
### kiat_home — 한국산업기술진흥원 / 대표 홈페이지 공고 미리보기

- 접근 판정: READABLE_PORTAL. text/html 메인에 사업공고 제목/기간과 새소식 미리보기. 더보기/제목 URL은 도구에서 구분되지 않음.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://kiat.or.kr/front/user/main.do) — Sheet1!R71C3, Sheet2!R9C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 원본은 메인. 정확한 전체 목록/상세 ID/페이지 이동 미확인.
- 직접 확인 근거:
  - [web.open](https://kiat.or.kr/front/user/main.do): text/html 메인에 사업공고 제목/기간과 새소식 미리보기. 더보기/제목 URL은 도구에서 구분되지 않음.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://kiat.or.kr/front/user/main.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="mss_business"></a>
### mss_business — 중소벤처기업부 / 사업공고

- 접근 판정: ALTERNATIVE_LIST. 원본 searchRltnYn=A URL은 Timeout. 해당 인자를 뺀 동일 cbIdx=310 목록은 HTML 2224건/223페이지.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310&searchRltnYn=A) — Sheet1!R73C3, Sheet2!R15C1.
- 확인된 목록: [목록](https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UI_NUMERIC_UNRESOLVED. 페이지 UI 관찰. 상세 링크 클릭은 동일 목록으로 돌아옴.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 대체 목록은 도구에서 공개 열람. 메뉴에 로그아웃 문구가 있어도 인증 세션으로 단정하지 않음.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 원본 필터와 대체 목록의 범위 동등성, 상세 요청/페이지 이동 미검증.
- 직접 확인 근거:
  - [web.open](https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310&searchRltnYn=A): 원본 searchRltnYn=A URL은 Timeout. 해당 인자를 뺀 동일 cbIdx=310 목록은 HTML 2224건/223페이지.
  - [web.open/click](https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310): 목록 확인, 제목 클릭은 동일 목록으로 해석됨.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="technopark_main"></a>
### technopark_main — 한국테크노파크진흥회 / 사업공고 및 TP 공고 집계

- 접근 판정: ALTERNATIVE_LIST. 메인에 외부 TP 공고 링크. TP진흥회 사업공고는 5건/1페이지, TP 집계 목록은 Timeout.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.technopark.or.kr/www/main.do) — Sheet1!R74C3.
- 확인된 목록: [목록](https://www.technopark.or.kr/www/bbsPost/72/list.do?mid=1008).
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: SINGLE_PAGE_OBSERVED. 진흥회 게시판은 5건/1페이지. TP 집계는 별도 목록으로 유지해야 함.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 진흥회 게시판 상세 클릭과 외부 TP별 본문/집계 페이지를 추가 확인해야 함.
- 직접 확인 근거:
  - [web.open](https://www.technopark.or.kr/www/main.do): 메인에 외부 TP 공고 링크. TP진흥회 사업공고는 5건/1페이지, TP 집계 목록은 Timeout.
  - [web.open/click](https://www.technopark.or.kr/www/bbsPost/72/list.do?mid=1008): 진흥회 공고 5건, 표/접수기간 확인.
  - [web.open/click](https://www.technopark.or.kr/www/linkBoard/list.do?mid=1012&type=P): TP별 사업공고 집계 목록은 Timeout.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.technopark.or.kr/www/bbsPost/72/list.do?mid=1008). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kier_ebid"></a>
### kier_ebid — 한국에너지기술연구원 / 전자입찰 공고

- 접근 판정: TOOL_ERROR. 원본 noticeList.do 조회에서 웹 도구 502 Bad Gateway.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://ebid.kier.re.kr/noticeList.do?boardGbn=3) — Sheet1!R75C3.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 목록/상세/로그인/페이지 요청 미확인.
- 직접 확인 근거:
  - [web.open](https://ebid.kier.re.kr/noticeList.do?boardGbn=3): 원본 noticeList.do 조회에서 웹 도구 502 Bad Gateway.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://ebid.kier.re.kr/noticeList.do?boardGbn=3). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="krict_bid"></a>
### krict_bid — 한국화학연구원 / 입찰공고

- 접근 판정: ALTERNATIVE_LIST. 원본 쿼리 URL은 도구 접근 불가. 쿼리 없는 같은 목록 경로는 0건/1페이지의 빈 입찰 표를 반환.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do?pageIndex=1&bidStatus=A&searchStartDate=&searchEndDate=) — Sheet1!R76C3.
- 확인된 목록: [목록](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do).
- 상세 구조/ID: 미확인.
- 상세 본문: 현재 표본 공고가 0개라 웹 상세 본문 유무를 판단할 수 없음.
- 페이지네이션: SINGLE_PAGE_EMPTY. 현재 진행 공고 없음, 1/1 표시. 여러 페이지 요청 미확인.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 공고가 있는 시점의 상세와 상태/검색 필터 및 과거 공고 경로 재검증 필요.
- 직접 확인 근거:
  - [web.open](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do?pageIndex=1&bidStatus=A&searchStartDate=&searchEndDate=): 원본 쿼리 URL은 도구 접근 불가. 쿼리 없는 같은 목록 경로는 0건/1페이지의 빈 입찰 표를 반환.
  - [web.open/click](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do): 공고문/사양서 컬럼과 현재 공고 없음 안내 확인.
  - [web.open/click](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do?bidStatus=B): 다른 상태 조회도 도구 접근 불가.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="hipa_legacy_notice"></a>
### hipa_legacy_notice — 화성산업진흥원 / 과거 hscity 공고·공시

- 접근 판정: TOOL_ERROR. Sheet2의 hipa.hscity.go.kr/support/notice/list는 웹 도구 접근 불가.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://hipa.hscity.go.kr/support/notice/list) — Sheet2!R1C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 과거 도메인 목록 접근 불가. hsbiz와 동일 게시판인지 확인되지 않아 자동 통합하지 않음.
- 직접 확인 근거:
  - [web.open](https://hipa.hscity.go.kr/support/notice/list): Sheet2의 hipa.hscity.go.kr/support/notice/list는 웹 도구 접근 불가.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://hipa.hscity.go.kr/support/notice/list). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kised_bid_public"></a>
### kised_bid_public — 창업진흥원 / 공개 입찰공고

- 접근 판정: ALTERNATIVE_LIST. 원본 안내 페이지의 입찰공고 바로가기에서 공개 board.es 목록 835건/84페이지 발견.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 원본: [URL](https://www.kised.or.kr/menu.es?mid=a10313000000) — Sheet2!R7C1.
- 확인된 목록: [목록](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000).
- 상세 구조: `/board.es?act=view&bid=0005&mid=a10303000000&list_no={id}`.
- 상세 본문: 표본 상세에 용역명/접수기간/설명 텍스트. 세부 자격은 나라장터/첨부를 참조하므로 판단 범위 제한.
- 페이지네이션: QUERY. 공식 목록의 2 링크 nPage=2 조회 성공.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 8443 계약관리시스템 로그인 없이 별도 기관 공개 게시판 열람.
- CAPTCHA/봇 차단: 공개 목록/상세/2페이지에서 CAPTCHA/차단 미관찰.
- 제한/후속: 표본 경로는 확인. 실제 HTTP 재현/운영 정책 검증은 구현 전 필요.
- 직접 확인 근거:
  - [web.open](https://www.kised.or.kr/menu.es?mid=a10313000000): 원본 안내 페이지의 입찰공고 바로가기에서 공개 board.es 목록 835건/84페이지 발견.
  - [web.open/click](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000): 공식 안내의 링크를 통해 공개 목록 확인.
  - [web.open/click](https://www.kised.or.kr/board.es?act=view&bid=0005&list_no=4648&mid=a10303000000&nPage=1&tag=): 상세 웹 텍스트 확인.
  - [web.open/click](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000&nPage=2): 2페이지 응답 확인.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kaia_legacy_bid"></a>
### kaia_legacy_bid — 국토교통과학기술진흥원 / 입찰공고 (현재 공식 경로 확인)

- 접근 판정: ALTERNATIVE_LIST.
- 결정: STATIC_HTML / REQUESTS / MEDIUM.
- 분류 근거: 과거 URL의 404 이력은 보존. 공식 메뉴에서 현재 입찰 목록/상세 HTML을 확인하여 현행 수집 경로 기준 STATIC_HTML로 보완. R&D 공고와 별도 게시판이며 과거 데이터 동등성을 주장하지 않음.
- 원본: [URL](https://www.kaia.re.kr/portal/bbs/list/B0000054.do?menuNo=200786) — Sheet2!R8C1.
- 확인된 목록: [목록](https://www.kaia.re.kr/KAIA/contents/K30300000000.do).
- 상세 구조: `/KAIA/contents/K30300000000.do?schM=view&id={id}`.
- 상세 본문: 확인 표본은 공고명/등록일과 HWP 본문 문서뷰어/첨부 중심. 실질 본문 텍스트는 확보하지 못함. 첨부 분석 없이 상세 자격을 판별할 수 없음.
- 페이지네이션: QUERY. 공식 목록의 2페이지 링크에서 page=2를 확인했으나 조회는 Cache miss. 성공으로 집계하지 않음.
- HTML: web 변환 응답 기준이며 로컬 HTTP 원문 재현은 미검증.
- JSON/API 및 JS 필수 여부: 미확인. 빈 목록이나 도구 오류만으로 판단하지 않음.
- 로그인: 공식 목록과 표본 상세는 비로그인 web 조회 가능. 내부 업무 로그인과 분리.
- CAPTCHA/봇 차단: 미확인
- 미확인/보류 사유: 현재 공식 입찰 경로를 찾았으나 2페이지 재현 및 첨부 없는 본문 적합성은 미확인. 최종 MVP 제외.
- 직접 확인 근거 (초기 + 보완):
  - [초기 web.open](https://www.kaia.re.kr/portal/bbs/list/B0000054.do?menuNo=200786): 원본 /portal/bbs/list/B0000054.do?menuNo=200786는 웹 도구가 404 Not Found 보고.
  - [초기 web.open/click](https://www.kaia.re.kr/KAIA/contents/K30101000000.do): 동일 기관의 새 R&D 공고는 열림. 입찰 게시판과 다른 종류이므로 대체로 간주하지 않음.
  - [보완 web.click](https://www.kaia.re.kr/KAIA/contents/K30300000000.do): 공식 KAIA 메뉴의 입찰공고 링크로 열람: 738건/74페이지 HTML 목록, 게시물별 id 링크 확인.
  - [보완 web.click](https://www.kaia.re.kr/KAIA/contents/K30300000000.do?id=20261019180300941761&schM=view): 공개 상세 응답 확인. 제목/등록일과 HWP 본문 문서뷰어, 첨부 링크 제공.
  - [보완 web.click](https://www.kaia.re.kr/KAIA/contents/K30300000000.do?id=20261014181744115765&schM=view): 두 번째 자체입찰 상세 URL도 text/html 응답 열림. 본문 제공 범위를 일반화하지 않음.
  - [보완 web.click](https://www.kaia.re.kr/KAIA/contents/K30300000000.do?page=2): 공식 2페이지 링크 조회는 Cache miss.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.kaia.re.kr/KAIA/contents/K30300000000.do). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kaips_ip_business_alt"></a>
### kaips_ip_business_alt — 한국지식재산서비스협회 / IP사업 게시판 별도 경로

- 접근 판정: TOOL_ERROR. 원본 /bbs_shop/list.htm?board_code=kaips_4 조회는 웹 도구 Timeout.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.kaips.or.kr/bbs_shop/list.htm?board_code=kaips_4) — Sheet2!R12C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 기존 kaips_12와 게시판 동등성/상세/페이지 이동 미확인. 별도 원본 URL 유지.
- 직접 확인 근거:
  - [web.open](http://www.kaips.or.kr/bbs_shop/list.htm?board_code=kaips_4): 원본 /bbs_shop/list.htm?board_code=kaips_4 조회는 웹 도구 Timeout.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.kaips.or.kr/bbs_shop/list.htm?board_code=kaips_4). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="ipnavi_ipds_login"></a>
### ipnavi_ipds_login — 한국지식재산보호원 / IPDS 전문기관 수행관리

- 접근 판정: LOGIN_PAGE. 로그인 화면이 기업용 공동인증서 또는 이메일 로그인, 로그인 후 기업정보 등록 필요를 명시.
- 결정: LOGIN / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.ip-navi.or.kr/cooperationLogin/loginForm.navi) — Sheet2!R20C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: NOT_APPLICABLE_LOGIN. 인증 화면만 확인. 내부 목록 조사/접근 안 함.
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 공동인증서/이메일 로그인 후 기업정보 등록 안내를 실제 확인. 로그인하지 않음.
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 전문기관 전용 인증 서비스. 공개 공고 수집 대상으로 자동화하지 않음.
- 직접 확인 근거:
  - [web.open](https://www.ip-navi.or.kr/cooperationLogin/loginForm.navi): 로그인 화면이 기업용 공동인증서 또는 이메일 로그인, 로그인 후 기업정보 등록 필요를 명시.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.ip-navi.or.kr/cooperationLogin/loginForm.navi). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="kautm_tlo_news"></a>
### kautm_tlo_news — 한국대학기술이전협회 / TLO 뉴스

- 접근 판정: TOOL_ERROR. 원본 과거 PHPSESSID를 제거한 공개 URL을 조회했으나 웹 도구 502 Bad Gateway.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.kautm.net/bbs/?so_table=tlo_news) — Sheet2!R22C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 공개 목록/상세 접근 불가. 과거 세션 식별자는 재사용하지 않음.
- 직접 확인 근거:
  - [web.open](http://www.kautm.net/bbs/?so_table=tlo_news): 원본 과거 PHPSESSID를 제거한 공개 URL을 조회했으나 웹 도구 502 Bad Gateway.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.kautm.net/bbs/?so_table=tlo_news). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="ketep_legacy_bid"></a>
### ketep_legacy_bid — 한국에너지기술평가원 / 입찰공고 기존 경로

- 접근 판정: TOOL_ERROR. Sheet2 /brdartcl/boardarticleView.do 경로는 웹 도구 접근 불가.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.ketep.re.kr/brdartcl/boardarticleView.do?srch_menu_nix=616nZhv3&brd_id=BDIDX_Zgq9d8l5n51206Rzap0658) — Sheet2!R23C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 목록인지 상세인지도 원본 이름만으로 확정 불가. 공식 현재 입찰 경로 재확인 필요.
- 직접 확인 근거:
  - [web.open](https://www.ketep.re.kr/brdartcl/boardarticleView.do?srch_menu_nix=616nZhv3&brd_id=BDIDX_Zgq9d8l5n51206Rzap0658): Sheet2 /brdartcl/boardarticleView.do 경로는 웹 도구 접근 불가.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.ketep.re.kr/brdartcl/boardarticleView.do?srch_menu_nix=616nZhv3&brd_id=BDIDX_Zgq9d8l5n51206Rzap0658). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="khidi_bioagora"></a>
### khidi_bioagora — 한국보건산업진흥원 / 바이오 아고라

- 접근 판정: EMPTY_HTML. text/html 응답이나 읽을 수 있는 본문 0줄. 도구는 수개월 전 수집본으로 표시.
- 결정: SPECIAL / MANUAL_ONLY / HIGH.
- 원본: [URL](https://www.khidi.or.kr/bioagora) — Sheet2!R24C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 현재 상태/실제 공고 기능/iframe/JS/API 여부 미확인. 캐시만으로 운영 상태 판단 불가.
- 직접 확인 근거:
  - [web.open](https://www.khidi.or.kr/bioagora): text/html 응답이나 읽을 수 있는 본문 0줄. 도구는 수개월 전 수집본으로 표시.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](https://www.khidi.or.kr/bioagora). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다.

<a id="technopark_legacy_domain"></a>
### technopark_legacy_domain — 한국테크노파크진흥회 / 과거 technopark.kr 도메인

- 접근 판정: LEGACY_404. 원본 HTTP의 HTTPS 조회에서 웹 도구가 404 Not Found 보고.
- 결정: UNSUPPORTED / MANUAL_ONLY / HIGH.
- 원본: [URL](http://www.technopark.kr/) — Sheet2!R27C1.
- 확인된 목록: 미확인.
- 상세 구조/ID: 미확인.
- 상세 본문: 미확인
- 페이지네이션: UNVERIFIED. 목록/페이지 이동을 검증하지 못함
- HTML: web 도구의 text/html 변환 결과 기준. 원본 HTML 바이트/JS 비활성 비교는 미검증.
- JSON/API: 미확인. JS 필수 여부: 미확인 (network/JS 비활성 검증 못함).
- 로그인: 미확인
- CAPTCHA/봇 차단: 미확인
- 제한/후속: 과거 루트는 현재 조사 경로로 지원 불가. technopark.or.kr과 자동 리다이렉트/동등성 미확인.
- 직접 확인 근거:
  - [web.open](http://www.technopark.kr/): 원본 HTTP의 HTTPS 조회에서 웹 도구가 404 Not Found 보고.
  - [web.open/click](https://www.technopark.or.kr/www/main.do): 원본의 다른 도메인 technopark.or.kr은 열림. 별도 기관 사이트 항목 참조.
- Fallback: **MANUAL_ONLY** — [공식 확인 경로](http://www.technopark.kr/). 공식 원문/공식 메뉴에서 수동 확인하고 결과를 기록한다. 로그인·CAPTCHA·접근통제를 우회하지 않는다. 원본 목록의 별도 technopark.or.kr 수집원을 참고하되 과거 도메인 동등성을 가정하지 않는다.

## 재개/인계

- M01은 이번 사용자 지정 완료 기준으로 PASS다. 미확인 수집원은 사유와 fallback을 기록한 보류 대상이며 M01 공통 blocker가 아니다.
- 최초 MVP 5개는 각 상세 섹션의 원본/목록/상세/2페이지 증거를 구현 입력으로 사용한다.
- 보완 대상은 KIPA IP 디딤돌, SMTECH, KAIA 옛 입찰 경로, TIPA 옛 입찰 경로, RIPC PMS의 5개였다.
- 비선정 수집원 41개는 세부경로 검증이 남아 있다. 필요한 수집원을 도입할 때 해당 항목만 재검증한다.
- API/JS 필수 여부, 로컬 HTTP 재현은 미확인 사실로 유지한다. 운영 성공이나 전체 사이트 자동수집 완료를 주장하지 않는다.
- 현재 판정은 이 문서/config/sites.yaml/M01_RESULT.md/CURRENT_STATE.md가 기준이다.
  초기 AUDIT_SUMMARY.json/build_inventory.py는 보완을 반영하지 않아 재생성에 사용하면 안 된다.
- M02는 별도 요청 후 진행한다. 이번에는 scraper/모델/정규화/배포 구현이나 패키지 설치를 하지 않았다.

## 사용자 업무 범위 정정

- 당사는 특허법인이다. 수행기관·협력기관 참여와 입찰 관점에서 대상 적합성을 판단한다.
- KIPA IP 디딤돌 게시판은 수혜기업 대상이라는 사용자 확인에 따라 모니터링/예비 후보에서 제외한다.
- 원본 coverage 49개 URL/47개 기록은 유지한다. 원본 기준 세부경로 미검증 41개에는 범위 제외 1개가 포함되며, 이를 뺀 업무 범위 내 미검증은 40개다.
- 기존 다른 수집원의 기술 검증 결과는 유지한다. 이번 정정은 다른 게시판 전체의 특허법인 대상 적합성 검토를 수행했다는 뜻이 아니다.

## 사용자 지정 MVP 추가 — KISTA 협력기관 모집공고 (2026-10-30)

- [사용자 지정 목록](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac)을 기존 `kista_ippro` 수집원의 MVP 대상으로 추가했다. 별도 중복 수집원을 만들지 않았다.
- KISTA 추가 당시 MVP 선정 6개 / 구현 경로 검증 완료 5개 / 페이지 이동 확인 대기 1개였다. 이후 RIPC 추가로 현재 선정은 7개다.
- 원본 URL 49개 및 셀 참조, 수집원 47개는 유지했다. 사용자 추가 URL은 별도 출처로 기록했다.
- KISTA 목록/표본 상세는 비로그인 HTML에서 확인했다. 2 링크 클릭은 첫 페이지를 반환했으므로 2페이지 성공으로 기록하지 않았다. 전체 검증 완료 수집원 6개/미충족 41개 집계는 변하지 않는다.
- 문서/config만 갱신했다. 자동 수집 활성화, scraper 구현, 패키지 설치, Git 및 M02 작업은 수행하지 않았다.

## 사용자 지정 MVP 추가 — RIPC 협력기관 입찰공고 (2026-10-30)

- [사용자 지정 입찰 목록](https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do)을 기존 ripc_pms의 모니터링 대상으로 지정하고 MVP에 추가했다. 원본 PMS 진입 URL/셀 참조 및 이전 기업회원 조사 이력은 보존했다.
- 현재 MVP 선정 **7개 / 구현 경로 검증 완료 5개 / 자동수집 검증 대기 2개(KISTA, RIPC)**. M01 PASS 유지.
- [공개 입찰 상세 표본](https://pms.ripc.org/pms/biz/partner/tenderNotice/info.do?bizYear=2026&noticeSeq=553)에서 상표출원 용역과 변리업체 참여 조건을 확인했다. 목록은 검색/표 헤더만 보여 공고 탐색/페이지 요청 방식은 미확인이다.
- RIPC는 SPECIAL / MANUAL_ONLY / HIGH 유지. 자동수집 구현 가능 검증 완료로 집계하지 않는다. 현재는 공식 페이지 수동 확인이며 로그인/JS 필수 여부를 추측하지 않는다.
- 기존 수집원 47개/원본 URL 49개 coverage 및 분류 집계, 전체 경로 검증 6개/미충족 41개는 변하지 않는다. 별도 중복 수집원은 추가하지 않았다.
- 지정한 문서/config 4개만 갱신했으며 Git/패키지 설치/scraper/M02 작업은 수행하지 않았다.
