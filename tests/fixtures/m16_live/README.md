# M16 user-saved original HTML

2026-11-02 사용자 제공 브라우저 저장본이다. m16_contract 재구성 표본과 구분한다.
원본 저장 HTML의 DOM/JS를 유지하되 URL의 `;jsessionid=...` 91곳을 제거했다.
세션을 재사용하거나 쿠키/credential을 저장하지 않는다. HTML/JS를 실행하지 않고 파싱한다.

| 파일 | 실제 확인 범위 |
| --- | --- |
| ripc/ripc_list_page1.html | 7컬럼 shell, POST getNoticeList.do, 검색 필드/JSON 키/행 템플릿/pagination JS. 실제 공고 행·AJAX 응답 없음 |
| ripc/ripc_detail_1.html | bizYear=2026/noticeSeq=553 hidden input, 제목/기관/단위사업/기간, 숨김 #elem 본문, 첨부 href 2개 |
| kista/kista_list_page1.html | 20행, javascript:view(annYy,annId), POST frm, pageIndex onclick. 페이지 2~21/마지막 39 링크 |
| kista/kista_detail_1.html | 목록 3번째 annYy=2026/annId=76과 제목 일치. 실제 상세 메타데이터, hidden contents의 이미지 본문, DEXT5 첨부 메타데이터 3개 |

## 재구성 표본과 차이

- RIPC 실제 목록에는 직접 href나 tbody 공고가 없다. 데이터는 POST AJAX로 가져온다.
- RIPC 실제 상세의 본문은 공고 내용 셀 옆이 아니라 숨김 `#elem`에 있고, 공통 메뉴의 bizYear와 상세 `frmParams.bizYear`를 구분해야 한다.
- RIPC 첨부는 `/kms/tenderNotice/attachFileDown.do?attachSeq=1722/1723`이다.
- KISTA 실제 목록의 제목 링크는 JS view 호출이며 상세와 페이지 이동은 form POST다. contractPage GET을 실제 요청으로 사용하지 않는다.
- KISTA 제공 상세는 contract 표본 annId=3이 아닌 annId=76이다. 대상과제의 사업구분 표와 공고 메타데이터를 구분한다.
- KISTA 본문은 hidden contents의 entity-encoded HTML을 표시하는 구조다. 저장 표본은 이미지뿐이므로 content_text는 빈 문자열이며 OCR하지 않는다.
- KISTA DEXT5 AddUploadedFile의 경로는 `/iprnd_data/RND-IP2_DATA/AN/FILE_...` 3개다. 이는 설정에 노출된 파일 경로이며 실제 다운로드 handler/HTTP 성공을 확인한 URL이라는 뜻은 아니다.

## 증거의 한계

HAR/Network 캡처, RIPC AJAX JSON 응답, 두 사이트의 실제 두 번째 페이지 응답은 제공되지 않았다.
tests/test_m16_live.py의 RIPC JSON은 실제 상세 값과 실제 JS 필드로 만든 **mock**이고,
페이지 2 응답은 pageIndex/JSON metadata만 바꾼 **mock**이다. 실수집 증거로 집계하지 않는다.
통합 테스트 KISTA 목록은 제공 상세와 대응되는 원본 1행만 남긴 subset이며 전체 원본 20행 parsing은 별도로 검증한다.
기존 m16_contract는 합성 입력에 대한 nullable/오류/결정성/회귀 검사로만 유지한다.
실제 robots/목록/상세 HTTP 수집 및 2페이지 응답/첨부 download는 별도 검증이 필요하다. M16 PARTIAL 유지.
