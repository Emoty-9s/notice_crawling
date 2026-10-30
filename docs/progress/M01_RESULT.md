# M01 Result

## Status
PASS

보완 확인일: 2026-10-30 (Asia/Seoul).

이번 사용자 지정 완료 기준인 전체 coverage, 전 수집원 분류/전략/위험도,
구현 경로가 검증된 MVP 5개, 확인 불가 사유와 fallback 기록을 충족했다.
모든 사이트의 자동수집 성공이나 모든 기술 특성 확인을 뜻하지 않는다.
이전 PARTIAL에서 남았던 항목 중 조건부 후보를 검증된 MVP로 잘못 승격하지 않았다.

## Implemented
- 기존 문서와 config를 읽고, 충분히 검증된 6개 사이트를 전수 재조사하지 않았다.
- 추가 확인 대상은 5개: KIPA IP 디딤돌, SMTECH, KAIA 옛 입찰 경로,
  TIPA 옛 입찰 경로, RIPC PMS.
- 원본 URL 49개 / 수집원 47개 / 기관·서비스 30개 그룹의 coverage와 원본 셀 참조를 유지했다.
- KIPA IP 디딤돌: 공개 목록은 열리지만 기존 offset=10 링크 및 축약 인자 2종은
  Cache miss/도구 접근 불가. 상세의 기존 본문 근거는 유지하고 최종 MVP에서 제외했다.
- SMTECH: 공개 목록은 열리지만 pageIndex=2 단독/검색 인자 포함 요청은 접근 불가.
  기존 상세 근거를 유지하고 최종 MVP에서 제외했다. 정확한 GET/POST 방식은 미확정이다.
- KAIA: 공식 메뉴에서 현행 K30300000000 입찰 목록 738건/74페이지와 상세 2개를 확인했다.
  과거 URL 404 이력을 보존하면서 현행 경로 기준 STATIC_HTML / REQUESTS / MEDIUM으로 보완했다.
  2페이지는 Cache miss, 표본 본문은 HWP 뷰어 중심이므로 MVP 제외.
- TIPA: 검색에 있는 목록/상세를 직접 조회하면 /eng로 이동한다.
  인덱스와 직접 응답이 달라 SPECIAL / MANUAL_ONLY / HIGH를 유지했다.
- 이전 RIPC 기업회원 지원공고 조사: 공개 상세의 실질 HTML 본문은 확인했다. 세션값을 제외한 목록 및
  IP디딤돌 목록에는 공고 행이 없어 전체 탐색 경로는 미확정이다. SPECIAL / MANUAL_ONLY 유지.
- 모든 수집원에 구체적인 사유/공식 확인 URL/수동 fallback을 기록했다.
- 최종 MVP는 7개: 기존 구현 경로 검증 완료 5개 + KISTA 협력기관 모집공고 + RIPC 협력기관 입찰공고. 추가 2개는 자동수집 검증 대기다. 사용자 업무 범위 정정 후 KIPA IP 디딤돌은 모니터링/예비 후보에서 제외했으며 SMTECH만 예비 후보로 유지한다.

## Final MVP
| 순위 | 수집원 | 기존 확인된 구현 경로 | 본문 범위 |
|---:|---|---|---|
| 1 | khidi_business — KHIDI 사업공고 | linkId / pageNum | 지원대상/규모/신청기간 본문 |
| 2 | kised_bid_public — 창업진흥원 공개 입찰 | list_no / nPage | 용역명/기간/짧은 웹 설명 |
| 3 | rda_bid — 농촌진흥청 입찰 | dataNo / currPage | 납품기한/장소/입찰방법 |
| 4 | seoul_rnd_notice — 서울 R&D 공지 | seqNo / cPage | 설명/일정 웹 본문 |
| 5 | kipa_bid — 한국발명진흥회 입찰 | article_no / pager.offset | 용역명/등록일/짧은 웹 설명 |
| 6 | kista_ippro — KISTA IP-R&D 협력기관 모집공고 | annId / annYy / bbsType=ac, 페이지 이동 미확인 | 사용자 지정 MVP. 목록·표본 상세 메타데이터 확인, 2페이지/상세 설명 범위 후속 확인 |
| 7 | ripc_pms — RIPC 협력기관 입찰공고 | bizYear / noticeSeq, 목록/페이지 이동 미확인 | 변리업체 참여 표본 상세 확인. 자동수집 검증 대기, 현재 MANUAL_ONLY / HIGH |

기존 1~5번 항목의 실제 목록/상세/2페이지 URL은 SITE_INVENTORY.md 및 sites.yaml에 유지했다.
KIPA 입찰/창업진흥원/농촌진흥청 표본의 세부 조건은 첨부 또는 외부 원문에 있을 수 있다.
향후 구현은 확보한 웹 텍스트까지만 처리하며 없는 자격 요건을 추론하지 않아야 한다.
패키지 설치 또는 scraper 구현은 이번 범위에 없다.

## Files Added
없음.

## Files Modified
- docs/site-audit/SITE_INVENTORY.md
- config/sites.yaml
- docs/progress/M01_RESULT.md
- docs/progress/CURRENT_STATE.md

## Tests / Verification
- 표준 Python으로 config를 읽어 원본 URL 집합 49/49, 수집원 47개와 source_id 유일성,
  원본 셀 참조 불변, 분류/전략/위험도, 전 수집원 fallback을 확인했다.
- 기존 검증 완료 MVP 5개가 모두 LIST_DETAIL_PAGINATION_VERIFIED 상태이며
  상세 HTML 본문과 비로그인 접근, 검증된 페이지 예제가 있는지 확인했다.
- 원본 XLSB SHA-256 불변:
  08bdd298d4219349cbf9b5a0ae0ef23dd39d93e8c865687f2f4a11e05e24ee3a.
- 현재 집계: STATIC_HTML 24 / JSON_API 0 / DYNAMIC 0 / LOGIN 1 / SPECIAL 21 / UNSUPPORTED 1.
- 목록·상세·2페이지 확인 6개 유지. 이 조건을 모두 충족하지 않는 수집원은 41개.
- 이번 보완은 문서/config만 변경했다. 애플리케이션 코드와 의존성 변경 없음.
  M00 smoke test는 불필요하게 재실행하지 않았으며 직전 PASS 결과를 유지한다.
- 로컬 urllib의 KIPA/SMTECH 요청은 DNS getaddrinfo failed.
  이 오류를 대상 사이트의 접근 불가/로그인/JS 필수 근거로 사용하지 않았다.

## Acceptance Criteria
- [x] 원본 URL 전체 coverage 유지: 49/49, 셀 참조 유지
- [x] 모든 수집원에 분류/전략/위험도 존재: 47/47
- [x] 구현 가능한 수준의 MVP 5개: 공개 목록/상세/페이지 예제와 ID/페이지 인자 확인
- [x] 확인 불가 사이트에 사유와 fallback 기록: 전 수집원 MANUAL_ONLY fallback
- [x] 이번 추가 검증 5개만 수행, 이미 검증된 사이트 전수 재조사 없음
- [x] 지정한 4개 파일만 갱신, 파일 추가/패키지 설치/Git/scraper/M02 구현 없음

## Known Issues
M01 완료를 막는 공통 blocker는 없다. 아래는 개별 도입 시 고려할 제한이다.

- 세부 수집경로 미검증 수집원 41개는 목록/상세/2페이지 응답 검증을 모두 충족하지 않는 수다.
  로그인 전용/옛 경로/수동 보류도 포함하며, API/JS 미확인 필드 개수는 아니다.
- KIPA IP 디딤돌은 특허법인의 모니터링 범위에서 제외된다(수혜기업 대상 게시판이라는 사용자 확인). SMTECH는 페이지 요청 검증 전까지 예비 후보/수동 확인이다.
- 일부 사이트의 도구 접근 실패, 대기열, 로그인 전용, 빈 목록은 기존 사유를 유지한다.
- JSON/API 및 JS 필수 여부는 여전히 확인되지 않은 사실이다.
  0개 분류는 API/동적 사이트가 없다는 뜻이 아니다.
- web 응답은 수집본/캐시를 포함하며 로컬 HTTP 원문 재현/실제 운영 안정성은 별도 검증이다.
- KAIA의 현재 입찰 경로를 찾았어도 원본 과거 데이터와의 동등성을 주장하지 않는다.

## Decisions
- 사용자 지정 완료 기준에 따라 수동 fallback이 결정된 비선정 수집원의 추가 조사를 M01 공통 blocker로 두지 않는다.
- 확인 실패한 조건부 후보를 PASS로 바꾸지 않고, 이미 실제 경로가 확인된 KIPA 입찰을 최종 5번째로 선정했다.
- 자동 수집 설정은 전부 enabled=false로 유지했다. 이는 M01 조사/전략 결정이며 서비스 활성화가 아니다.
- 초기 AUDIT_SUMMARY.json과 build_inventory.py는 이번 보완을 반영하지 않는 역사적 스냅샷이다.
  현재 판정은 이 결과 문서, CURRENT_STATE.md, SITE_INVENTORY.md, sites.yaml이 기준이다.
  초기 builder를 재실행하면 최신 조사 결과가 덮어써지므로 사용하지 않는다.

## Next Milestone Notes
M01 완료. 다음 요청에서 M02 — Core Data Model을 진행할 수 있다.
이번에는 M02를 진행하지 않았다. 비선정 사이트의 추가 검증은 해당 사이트 도입 시 수행한다.

## 사용자 업무 범위 정정

- 사용자 확인: 당사는 특허법인이며 KIPA IP 디딤돌 게시판은 수혜기업 대상이다.
- 해당 게시판을 모니터링/예비 후보/추가 페이지 검증 대상에서 제외했다. 기술 접근성만으로 업무 후보를 선정하지 않는다.
- 원본 추적 기록/URL coverage 및 기존 기술 검증 결과는 보존했다. 기존 MVP 5개와 M01 기술 조사 PASS 판정은 유지했으며, 이후 KISTA와 RIPC 추가로 현재 선정 수는 7개다.
- 원본 기준 세부경로 미검증 41개 중 업무 범위 제외 1개를 뺀 미검증 수집원은 40개다.
- 다른 수집원 전체의 특허법인 대상 적합성을 이번에 새로 검증한 것은 아니다.

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
