# 수출바우처 첨부 복구 검증 (2026-11-09)

대상은 `exportvoucher_notice` 하나다. 기존 목록/상세/페이지 규칙, 증분 정책,
feed v3, 추출/OCR 엔진과 Windows A/B 판정은 재사용한다. 외부 AI 호출은 없다.

## 공개 동작 재현

- 공식 목록: https://www.exportvoucher.com/portal/board/boardList?bbs_id=1
- 첨부 표본: `ntt_id=13038` (수행기관 모집, HWP/PDF), `8410` (PDF), `13034` (JPG).
- 첨부 없음 표본: `ntt_id=13047` (상세 내 첨부 위젯 없음).
- `.bbsViewArea [data-file-download]`의 `data-doc-id`가 파일 그룹이다.
  13038의 그룹은 `DOC_000000003940343`이다.
- 상세의 `file-access-token` 속성을 확인했지만, `ftFile2.js?v=3`의 공식
  목록 요청에는 이 값을 인자로 전달하지 않는다. 별도 hidden field를 추측하지 않는다.
- 익명 상세를 연 CookieJar로 `/common/File2List?docId={data-doc-id}`를 호출한다.
  공식 AJAX의 X-Requested-With/Referer/Accept를 재현한다.
  헤더를 각각 비교할 때 상세를 매번 다시 열면 모두 2건이므로 특정 헤더가
  필수라는 주장은 하지 않는다. 상세 재접속 없는 반복 조회에서는 `[]`가 관찰됐다.
  따라서 세션 없는 독립 API 요청의 `[]`를 첨부 없음으로 취급하지 않는다.
- 응답의 `fileId`, `fileName`, `fileSize`, `secCode`를 검증하고
  `/common.FileDownload.do?file_id={fileId}&sec_code={secCode}`로 다운로드한다.
  secCode는 재조회 시 달라져 OCR 작업 식별자는 fileId만 사용한다.
  다운로드 시 공식 상세와 목록을 새 익명 세션에서 다시 해석한다.
- 원문 파일은 메모리/기존 자동 삭제 임시공간에서만 처리한다.
  0바이트, HTML 오류 응답, 확장자별 시그니처/크기 불일치는 실패다.
  그룹이 있는데 빈 배열인 경우도 실패로 보존한다.

## 로컬 검증

- 목록 1/2/3페이지 각 14행, 고정 공고 중복 제거 후 34건 수집.
- 실제 다운로드: HWP 185856바이트, PDF 498122바이트, JPG 43166바이트.
- HWP 직접 텍스트 12676자, PDF 12271자. 로컬 OCR은 실패하여 전체 추출은
  PARTIAL이다. 로컬 OCR 성공으로 보고하지 않는다.
- 신규 단위 테스트 6개 PASS. 전체 735개 PASS (Windows 전용 1개 skip).
- 공개 HTML/JSON fixture만 저장하며, 발급 secCode/세션 속성은 제거했다.

중앙 활성화는 별도 read-only Actions에서 실제 첨부 OCR 검증 후 진행한다.
최종 Actions/Windows/커밋 증거는 검증 완료 후 아래에 기록한다.
