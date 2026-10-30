# M05 Result

## Status
PASS — 사용자 지정 fixture 기반 구현/오프라인 검증 범위.

검증 시각: 2026-10-30T14:55:35+09:00. 기존 FAIL 기록은 실제 fixture 부재 당시 결과이며 이번 결과로 대체한다.
실제 네트워크 smoke는 이번 요청에 따라 수행하지 않았다. 운영 사이트 접속 성공을 뜻하지 않는다.

## Implemented
- 사용자 저장 list.html/detail.html 10개의 실제 DOM을 읽어 지정한 scraper 5개를 구현했다.
- 목록 parsing, 실제 href 기반 절대 상세 URL 생성/검증, 본문 parsing 및 Notice 생성을 제공한다.
- 표준 HTMLParser 기반 공통 tree/탐색/StructureError와 BoardScraper/TableBoardScraper를 분리했다.
- BaseScraper의 HTTP/timeout/retry/예외 경계를 재사용하고 M03 날짜/텍스트/기관명/URL/ID/hash 함수를 사용한다.
- Registry의 build_mvp_registry가 정확히 5개 adapter를 등록한다. config.enabled는 보존하고 등록만으로 실행하지 않는다.
- KISTA/RIPC adapter, Storage/Gemini/Actions/M06 이후 구현 없음. Git/패키지 설치/실제 네트워크 호출 없음.

## Files Added
- src/scrapers/_html.py
- src/scrapers/_board.py
- src/scrapers/khidi_business.py
- src/scrapers/kised_bid_public.py
- src/scrapers/rda_bid.py
- src/scrapers/seoul_rnd_notice.py
- src/scrapers/kipa_bid.py
- tests/_site_cases.py
- tests/test_khidi_business.py
- tests/test_kised_bid_public.py
- tests/test_rda_bid.py
- tests/test_seoul_rnd_notice.py
- tests/test_kipa_bid.py
- tests/test_mvp_registry.py

## Files Modified
- src/scrapers/registry.py: 기존 동작을 유지하고 명시적인 MVP factory 추가.
- docs/progress/M05_RESULT.md
- docs/progress/CURRENT_STATE.md
- docs/progress/M05_FIXTURE_STATUS.md: 실제 확보 상태로 갱신.

사용자 생성 fixture 원본 10개는 그대로 보존했다. config/sites.yaml, models.py,
normalizer.py, base.py, src.main 및 의존성은 변경하지 않았다.

## Actual DOM Evidence
| source_id | 목록 범위 | 상세 제목/본문 범위 |
|---|---|---|
| khidi_business | table.tstyle_list / tbody / td.ellipsis a | article.news_view / h1.newsTitle / div.viewContent |
| kised_bid_public | div#panel_2.tstyle_list / div#listView / ul / li.title a | table.tbl-basic.tbl-row / th.board_tit / td.left[colspan=4] |
| rda_bid | table.tbl.data + caption 입찰공고 안내 / tbody / td[aria-label] | div#title.community-page-title / h2.tit / div#contents.g-description-area |
| seoul_rnd_notice | div.board_list / table.tabW100 / tbody / td.t1 a | div.board_view / td.tit / td.view.smartOutput |
| kipa_bid | table.list_table / tbody / a[article_no query] | table.view_table / td.title / div#article_text |

- KHIDI는 공지 고정행 포함 14개, 나머지는 각각 10개 목록 항목을 파싱했다(합계 54개).
- RDA 주소검색 팝업에도 table.tbl.data가 있으므로 입찰공고 안내 caption으로 목록을 구분한다.
- KISED의 title 속성으로 새글 아이콘 텍스트를 제외한다. 실제 최초작성일의 YYYY/MM/DD HH:MM에서 날짜만 명시적으로 읽는다.
- KHIDI/KISED/서울 R&D는 상세 hidden ID와 목록 ID를 비교한다.
  모든 사이트에서 목록/상세 제목 불일치도 명시적으로 실패시켜 잘못된 fixture 연결을 방지한다.
- RDA는 실제 기관명/분야/종료일을, KISED는 접수 시작/종료일을 읽는다.
  그 밖에 날짜 정보가 없는 필드는 None이며 제목/본문에서 일자를 추정하지 않는다.
- 본문 컨테이너만 처리하며 첨부 목록, 인접 글, 메뉴/스크립트는 본문에 포함하지 않는다.

## Tests
- command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- result: **129 tests, OK**, failures/errors 0, exit code 0.
- 신규 M05 59개: 사이트별 11개 × 5 + Registry 4개.
- 기존 70개: M00~M04 61개 + fixture 다운로드 도구 9개 모두 회귀 통과.
- 필수 목록/URL/상세/Notice/빈 목록/구조 변경, ID/hash 안정성 및 JSON round-trip 검증.
- 목록·본문 컨테이너 제거, 링크 구조 변경, 빈 본문, 잘못된 상세 응답을 정상 빈 결과로 숨기지 않고 StructureError로 처리함을 검증했다.
- 5개 실제 adapter를 fake transport로 run한 결과 list[Notice] 5개 및 오류 없음.
  한 사이트 실패 시 다른 4개가 계속 완료되는 것도 검증했다.
- 전체 목록 54개 parsing과 상세 표본 각 1개를 별도로 검증한다.
  run 테스트는 실제 목록 DOM에서 해당 상세 표본 행만 남긴 메모리 변형을 사용한다.
  같은 상세를 다른 공고에 재사용하지 않으며 원본 파일을 수정하지 않는다.
- 정상 빈 목록 테스트는 실제 목록의 헤더/컨테이너를 보존하고 행만 메모리에서 제거한다.
- 테스트에서 모든 HTTP는 Mock transport다. urlopen 호출 금지 guard로 네트워크에 의존하지 않음을 확인했다.

## Manual Verification / Fixture Integrity
사용자 생성 실제 HTML이며 10개 모두 UTF-8로 정상 디코딩되었다.
원본/최소화 fixture를 추가 생성하지 않았고 기존 원본을 그대로 테스트한다.
확인한 파일의 크기와 SHA-256은 아래와 같다.

| fixture | bytes | SHA-256 |
|---|---:|---|
| khidi_business/list.html | 124392 | db6ba355e05e134326cedcda87b50de3b30591de90d59052778da3084179a23d |
| khidi_business/detail.html | 121486 | 8660c9f881a9ef6db61f0d0ea781f2c3ae2f5aefff856481314b5e3d89d98aca |
| kised_bid_public/list.html | 45847 | ee22aaef33ad6053d2ad5fec2df9de1f1c7b807fb88a49d853d3b6013507cb73 |
| kised_bid_public/detail.html | 41263 | 41546aae8b62d11b40f13f6e8148c4bc774d4ce7e63ae8c14315b3b94f782abb |
| rda_bid/list.html | 186230 | 864cf44343c8e88139774cc968ca466aeef9ee7d9e6c0a4a8fbdafb1d0237687 |
| rda_bid/detail.html | 177205 | 35f42c67ee8ff6e7bebbebe84db264b9de65352eabbf424628cb0ea80f61f229 |
| seoul_rnd_notice/list.html | 24303 | 067b1c60dc30ea5fa3b3d08f11d8e217821393ffa5ea28862048aa6080d8e3c5 |
| seoul_rnd_notice/detail.html | 43570 | a165d60c395c3fbcd89962677fd83c1c710c1f7f15b36df297a2e8d0e8b2fb7c |
| kipa_bid/list.html | 80032 | 9d920ab016bbf8b7a3f29e1611d4a2934554e36418479ebf9bfc8a2378734bb6 |
| kipa_bid/detail.html | 62063 | 3bc27ebf73e75cea69867a31402ecaf3b8a006e8c18e375c75533083f8ec2c6a |

## Acceptance Criteria
- [x] 대상 5개 사이트 adapter와 명시적 registry 등록 구현.
- [x] 실제 HTML 10개에 근거한 목록/상세 selector.
- [x] 상대 href를 절대 URL로 해석하고 origin/path/사이트 ID 검증.
- [x] Notice 생성 및 모델/normalizer/base 재사용.
- [x] 빈 목록/구조 변경 실패/5개 fake run 및 격리 검증.
- [x] 전체 기존 unittest 회귀 및 진행 문서 갱신.
- [x] 네트워크 의존 없이 검증, M06 이후 미구현.

## Known Issues
- fixture blocker 없음. 상세 표본은 사이트별 1개이므로 다른 유형 공고에 대한 fixture 범위는 제한된다.
- KIPA 본문은 나라장터 안내 중심의 짧은 텍스트이며 첨부/외부 원문을 추가 수집하거나 조건을 추론하지 않는다.
- 서울 R&D 상세에는 편집기에서 생성한 비정상 style 속성이 있지만 표본 본문은 표준 HTMLParser로 정상 추출되었다.
- 현재 run은 지정 목록 페이지의 항목을 처리한다. 자동 전 페이지 순회는 구현하지 않았다.
- 정상 빈 tbody/listView는 []다. 알려지지 않은 빈 목록 안내행/placeholder는 안전하게 StructureError로 실패한다.
- 제목이 목록 조회 직후 변경되어 상세와 불일치하면 실패하며 다음 실행에서 목록을 재수집해야 한다.
- 실제 네트워크 smoke 미실행. 기존 sandbox DNS 제약은 fixture 테스트 성공과 별개이며 사용자 환경의 운영 검증이 필요하다.
- config의 enabled=false를 일괄 변경하지 않았다. 테스트에서는 복사본만 활성화했다.

## Decisions
- 사이트별 모듈은 selector/필드 매핑만 맡고 HTML 탐색/날짜 필드/URL/Notice 생성은 공통 계층으로 분리한다.
- 안정 ID는 source별 고유 query ID(linkId/list_no/dataNo/seqNo/article_no)를 우선한다.
- 원래 href의 query 의미는 보존하며 첨부 링크나 다른 호스트/경로/ID 누락 링크를 수집하지 않는다.
- observation clock은 timezone-aware UTC가 기본이며 테스트에서는 고정 시각을 주입한다.
- 모델의 NEW/NOT_ANALYZED 기본값만 사용한다. 저장 데이터 비교/분석은 이번 범위가 아니다.

## Next Milestone Notes
- M05 완료. 다음 사용자 요청에서 M06 — Storage Layer만 진행한다. 이번에는 구현하지 않았다.
- `build_mvp_registry(site_configs, transport_factory=..., clock=...)`로 등록한다.
  site_configs는 디코딩된 site mapping 리스트다. 기존 enabled 설정을 존중한다.
- 실제 HTTP 실행과 모든 상세/다른 페이지 유형 검증은 별도의 운영 검증이며 이번 오프라인 PASS와 구분한다.
- KISTA/RIPC 도입은 이번 범위 밖이다.
