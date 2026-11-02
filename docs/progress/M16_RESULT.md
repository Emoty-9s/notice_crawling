# M16 Result

## Status

**M16 PASS — 두 소스 각각 실제 HTTP Notice 1건 수집 및 전체 442 unittest OK.**
검증일: 2026-11-02 (Asia/Seoul). 근거는 사용자가 동일 PC의 일반 PowerShell에서 실행하여 제공한 실제 smoke/전체 테스트 결과다.
RIPC SUCCESS/notice_count=1/list_count=10, KISTA SUCCESS/notice_count=1/list_count=20, 양쪽 title_nonempty=true.
일반 PowerShell 전체 테스트: Ran 442 tests, OK, 40.192s. 기존 Notice/feed/matcher/dashboard 계약 변경 없음.
Codex 내부 DNS_ERROR/11001은 실행환경 제한이며, 일반 PowerShell의 실제 HTTP 검증은 성공했다. 이번 상태 갱신에서는 코드를 수정하거나 검증 명령을 재실행하지 않았다.

## 구현 대상 / URL

- RIPC 협력기관 입찰사업 공고: https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do
- RIPC 상세: /pms/biz/partner/tenderNotice/info.do?bizYear=2026&noticeSeq=553
- KISTA 협력기관 모집공고: https://biz.kista.re.kr/ippro//com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac
- KISTA 제공 상세와 대응되는 목록 URL: /ippro/com/iprndMain/selectBusinessAnnounceView.do?annYy=2026&annId=76&bbsType=ac

RIPC는 applicant 지원기업 공고를 수집하지 않는다. 현재 대상은 partner/tenderNotice다.
기존 source_id/47개 coverage/기본 enabled=false/기존 5개 MVP 등록 계약을 유지한다.

## 원본 확보 / 재구성 표본과 차이

이전 확인 시 파일이 없었던 것은 조사 이력이며, 이번 요청에서는 다음 **네 원본 파일을 실제로 읽었다**.

| 파일 (tests/fixtures/m16_live/ 아래) | 원본에서 확인한 사실 |
| --- | --- |
| ripc/ripc_list_page1.html | 공고번호/센터/사업형태/공고제목/공고기간/배정예산/공고상태 7컬럼 shell. 공고 행 없음. AJAX action/params/JSON keys/행 템플릿/페이징 JS 존재 |
| ripc/ripc_detail_1.html | frmParams의 bizYear=2026/noticeSeq=553, 공고명/수요기관/단위사업/공고기간, #elem의 실제 본문, 첨부 href 2개 |
| kista/kista_list_page1.html | 실제 20행, javascript:view('연도','ID'), POST frm, pageIndex pager |
| kista/kista_detail_1.html | 목록 3번째 annId=76과 제목 일치. infor-view 메타데이터, hidden contents의 이미지 HTML, DEXT5 파일 설정 3개 |

원본 URL에 들어 있던 세션 ID 91곳은 제거했다. 나머지 DOM/JS 구조는 유지했다.
HAR/Network 캡처, RIPC AJAX JSON 응답, 실제 2페이지 응답은 제공되지 않았다.
fixture provenance와 상세 차이는 tests/fixtures/m16_live/README.md에 기록했다.

m16_contract의 직접 href/contractPage/인접 본문/합성 attachment는 실제 DOM과 다르다.
이전 표본은 nullable/오류/결정성 등 회귀 검사로 유지하고 **실제 사이트 검증 근거로 사용하지 않는다**.
새 tests/test_m16_live.py는 원본을 직접 읽는다. 원본을 재구성 표본으로 바꾸지 않았다.

## Scraper 구조 / 구현 파일

- src/scrapers/ripc_pms.py: RIPC 원본 JS의 AJAX POST/JSON 행/유한 페이지/상세 identity/#elem 본문.
- src/scrapers/kista_ippro.py: KISTA JS view 해석/실제 form POST/POST pager/scoped metadata/encoded contents/DEXT5 경로.
- src/scrapers/_portal.py: 공통 robots/요청 경로 검증, site hook, nested table metadata 격리, URL session 제거.
- src/scrapers/base.py: 기존 GET 계약 유지. form POST를 추가하고 기존 timeout/retry/User-Agent/실패 정책을 공유.
- src/scrapers/registry.py / src/pipeline.py: 기존 M16 선택적 등록/지원 소스 연결 유지. 이번 원본 보정에서 추가 변경 없음.
- config/sites.yaml: 두 소스 비활성 유지, 원본/HTTP 검증 상태 기록.
- tools/m16_smoke.py: 원본 흐름을 호출하는 최소 probe. notice_count는 실제 정규화한 1건, list_count는 목록 행 수로 구분.
- tests/test_m16_live.py: 원본 기반 및 명시적 mock 기반 신규 28개.
- tests/fixtures/m16_live/: 세션 ID를 제거한 사용자 제공 네 HTML 및 provenance.
- README.md / docs/progress/CURRENT_STATE.md / docs/progress/M16_RESULT.md.

## RIPC 목록 / 상세 / Pagination

원본 JS에서 다음을 확인했다. JS를 실행하거나 URL을 추측하지 않는다.

- POST /pms/biz/partner/tenderNotice/getNoticeList.do.
- searchKeyword='', bizYear, recordCountPerPage=10, currentPageNo=1부터, noticeGroupCode=NGR002, noticeCode=NST000.
- chkCenter/chkBizCategory는 선택이 없으면 빈 배열이므로 jQuery form 직렬화처럼 생략한다. 추가 코드 목록/검색 요청은 하지 않는다.
- result.noticeList, totalRecordCount, recordCountPerPage, currentPageNo와 행 템플릿의 noticeSeq/bizYear/noticeTitle/centerName/bizCategory1Name/startDateStr/endDateStr를 사용한다.
- 작성중 NST002는 실제 템플릿처럼 제외한다. 알 수 없는 상태/응답 형식/페이지 불일치는 실패한다.
- 사업년도는 명시적 business_year 설정 또는 주입 clock의 연도다. 실제 사이트도 JS 현재 연도를 기본으로 사용한다. matcher의 reference_year 계약과 무관하다.
- totalRecordCount와 recordCountPerPage로 다음 currentPageNo를 결정한다. 반환 페이지/크기/행 개수 검증, max_pages 기본 3/범위 1~20, 한도 warning.
- 상세는 기존 canonical URL로 GET. frmParams로 identity를 검증하며 메뉴의 빈 bizYear input과 혼동하지 않는다.
- 상세 공고명/공고기간/단위사업/수요기관을 읽고 본문은 viewer에 주입되는 숨김 #elem에서 추출한다.

**실제 목록 AJAX JSON은 미제공이다.** JSON parser와 2페이지 순회 테스트의 JSON은 실제 상세 값과 원본 JS 필드로 만든 mock이다.
원본 상세 fixture 테스트와 실제 HTTP 검증은 구분한다. 이후 사용자 제공 일반 PowerShell smoke에서 목록 10건/Notice 1건 수집에 성공했다.

## KISTA 목록 / 상세 / Pagination

- table.infor-Board 실제 20행을 추출한다. javascript:view('annYy','annId')의 숫자 인자를 엄격히 읽고 ac 게시판 canonical URL을 만든다.
- 원본 view 함수에 명시된 POST /ippro/com/iprndMain/selectBusinessAnnounceView.do를 사용하며 frm의 필드를 보존하고 annYy/annId를 설정한다.
- pagination은 fn_egov_select_noticeList(pageNo) → frm.pageIndex → POST /ippro/com/iprndMain/selectBusinessAnnounceList.do.
- 보존 필드: pageIndex/DepthCode1/DepthCode2/bbsType/annYy/annId/searchGubunCd/searchWrd. 검색값은 원본 form 값 그대로.
- 실제 onclick에서 1~21/마지막 39를 읽는다. 방문 페이지 중복 제거/max_pages 한도/반환 pageIndex 검증. 반복 첫 페이지를 조용히 허용하지 않는다.
- 제공 상세는 annId=76이며 annId=3 상세로 사용하지 않는다. 제목 불일치 시 실패한다.
- table.infor-view 자체 메타데이터만 읽어 대상과제 안의 중복 사업구분 header를 구분한다.
- hidden contents의 HTML/entity를 디코딩한다. 해당 저장본은 이미지 본문이므로 content_text=''. OCR/AI/이미지 다운로드 없음.

실제 목록 20건 및 제공 상세의 Notice 1건 생성 성공.
**2페이지 원본 응답은 없다.** pageIndex만 바꾼 응답 mock으로 POST 전달/반복 페이지 방어를 검증했으며 실페이지 2 성공으로 집계하지 않는다.

## Notice 매핑 / Stable ID / Attachment

| 기존 필드 | 매핑 |
| --- | --- |
| source_id | ripc_pms / kista_ippro |
| title | 실제 공고명, 기존 whitespace/entity 정규화 |
| institution | RIPC 센터/수요기관, KISTA 기존 config 기관 |
| category | RIPC 목록 사업형태(JSON bizCategory1Name)/상세 단위사업, KISTA 구분/사업구분 |
| apply_start/apply_end | 실제 공고기간/접수기간 날짜. 없는 쌍은 None, 잘못된 날짜는 실패 |
| published_at | 미확인 시 None |
| url/notice_id | canonical 연도+sequence+게시판 URL, 기존 M03 stable URL 분기 |
| content_text/content_hash | 실제 선택 본문 또는 빈 문자열, 기존 M03 content hash |
| status/gemini/관측시각 | 기존 lifecycle/NOT_ANALYZED/주입 clock |

배정예산/조회수/모집상태를 위해 schema를 추가하지 않는다. 공고상태를 NEW/UPDATED/EXISTING에 덮어쓰지 않는다.
Notice/feed에는 attachment 계약이 없으므로 URL tuple 검증·반환만 제공하고 저장 필드/다운로드 시스템을 추가하지 않는다.

- RIPC: 실제 href /kms/tenderNotice/attachFileDown.do?attachSeq=1722, 1723. 절대 URL화하고 세션 ID 제거.
- KISTA: DEXT5UPLOAD.AddUploadedFile의 문자열 literal 결합을 해석해 /iprnd_data/RND-IP2_DATA/AN/FILE_000000001295795, ...5794, ...5793 경로 3개를 확인한다.
- KISTA 경로는 DEXT5 설정에 노출된 경로이며 **실제 다운로드 handler/HTTP 성공 URL은 미검증**이다. JS 실행/handler 추측/파일 다운로드는 하지 않는다.

M03 ID/hash 알고리즘, Notice/enum/feed/cache/performance DB/matcher/dashboard 계약을 변경하지 않았다.

## 테스트 / 통합

실제 실행: python -m unittest discover -s tests
Codex 내부 회귀 이력: **442 tests OK**, 51.572초, exit 0. 기존 414개 유지 + 신규 28개.
최종 외부 회귀 근거: 사용자 제공 일반 PowerShell 결과 **Ran 442 tests / OK / 40.192s**.
M16 전체 신규 누계 90개(기존 contract/통합/probe 62 + 원본 보강 28), M15까지 352개.

신규 검증: 원본 shell/실제 20행/JS 상세 ID/form payload/pager indices/#elem/encoded body/첨부 2+3/
session 제거/nullable/identity·title·board 불일치/변경 JS·JSON 실패/반복 첫 페이지 방어/기존 POST UA·timeout·retry/한글 form encoding.
각 실제 상세에서 Notice를 만들고 validation/날짜/ID를 검증했다. 실제 외부 네트워크는 차단한 테스트다.

registry → pipeline → JsonStorage → public feed → M12 cache → 기존 matcher/dashboard 통합 재검증:
RIPC는 **원본 상세 + 원본 JS 기반 mock JSON**, KISTA는 **원본 목록에서 상세 대응 1행만 남긴 subset + 원본 상세**를 사용했다.
실제 20행 parser는 별도 검증했다. Gemini는 fake 응답만 사용했으며 실제 API 호출은 없다.
로컬 performance DB/cache는 UI 읽기 전후 bytes 불변이다. 기존 M14/M15 코드는 수정하지 않았다.

## Live smoke

명령: python -m tools.m16_smoke --source ripc_pms kista_ippro

최종 근거: 사용자가 동일 PC 일반 PowerShell에서 실행해 제공한 실제 결과.

| 소스 | status | notice_count | list_count | title_nonempty | apply_start | apply_end |
| --- | --- | --- | --- | --- | --- | --- |
| ripc_pms | SUCCESS | 1 | 10 | true | 2026-08-07 | 2026-08-21 |
| kista_ippro | SUCCESS | 1 | 20 | true | 2026-01-12 | 2026-12-31 |

각 사이트 실제 HTTP 수집 최소 1건 및 전체 unittest PASS 조건을 충족하여 M16 PASS로 판정했다.
다음 표는 이전 Codex 내부 실행 이력이며 외부 성공 결과와 구분한다.

| 소스 | status | stage | reason | errno | 실제 수집 |
| --- | --- | --- | --- | --- | --- |
| ripc_pms | BLOCKED | robots_or_list | DNS_ERROR | 11001 | 0 |
| kista_ippro | BLOCKED | robots_or_list | DNS_ERROR | 11001 | 0 |

exit 1. retry=0/timeout=10, max_pages=1. 최대 robots+목록 shell+RIPC AJAX+상세 1건이며 부가 JS/이미지/첨부 요청은 하지 않는다.
이전 Codex 실행은 robots URL DNS 단계에서 종료했다. DNS_ERROR/11001은 Codex 실행환경 제한이었고 일반 PowerShell에서는 실제 HTTP 수집에 성공했다.
추가 Session/로그인·CAPTCHA 우회/브라우저 자동화는 없다.

## Blocker / 남은 별도 작업 / Next

M16 종료 조건의 blocker 없음. Codex 내부 DNS 제한은 일반 PowerShell 외부 live 성공으로 분리 기록했다.
추가 관찰 사항: RIPC AJAX JSON/HAR 원본 보관, 실제 2페이지 응답, KISTA DEXT5 다운로드 handler 및 첨부 다운로드 성공은 미검증이다.
해당 항목을 검증 완료로 바꾸지 않는다. 이번 사용자 지정 종료 조건(각 live >=1/전체 unittest PASS/계약 유지)은 충족했다.

별도 잔여 작업은 기존과 동일하게 M11 배포 URL 확인 → 그 이후 M12 실제 GitHub HTTP 다운로드 검증이다.
M16 종료. 다음은 별도 잔여 작업 확인이며 M17 이후는 사용자 요청 없이 진행하지 않는다.
