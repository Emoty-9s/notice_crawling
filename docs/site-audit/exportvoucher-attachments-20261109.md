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
  `ftFile2.js`의 `cache:false`에 맞춰 jQuery GET의 `_={밀리초 nonce}`도 붙인다.
  이는 공식 호출 규칙 재현이며, 특정 헤더/nonce만으로 연결 오류가 해결됐다는
  주장은 하지 않는다.
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

## 최종 결과: 완료 기준 미충족

- 최종 구현 커밋: `6844e0ef2c88929391844b08b33c52245a5f7947`.
- 공식 cache:false 요청을 포함한 최종 로컬 수집도 34건 PASS.
  첨부 있는 공고 19건, 파일 메타데이터 43개, 실제 원문 다운로드는 **3개**다.
  43개 모두를 다운로드했다고 주장하지 않는다.
- 최종 코드 전체 unittest 재검증: 735개 PASS, 1개 skip (237.375초).
  신규 수출바우처 테스트 6개와 기존 기관 회귀 테스트를 포함한다.
- 별도 재빌드 EXE:
  `dist/notice_crawling_exportvoucher_verified/notice_crawling_exportvoucher_verified.exe`.
  실제 공개 수집 결과를 루프백 서버로 공급하여 격리된 임시 캐시에서
  UPDATED → UNCHANGED, 수출바우처 34건/텍스트 47503자 동기화 PASS.
  A 분석 SUCCESS 34건, 판정 EXCLUDE 30건/INSUFFICIENT 4건.
  기본 목록 0건, 제외 포함 현재 3건/마감 31건으로 공통 정책을 유지했다.
  사용자 DB를 열거나 생성하지 않았다. 배포된 중앙 Pages에서 수출바우처가
  동기화됐다는 뜻은 아니다.
- [최종 실제 Actions 42580372030](https://github.com/Emoty-9s/notice_crawling/actions/runs/42580372030)
  **FAIL**. 목록 1/2페이지와 첫 상세/첨부 목록 조회는 성공했으나 다음 상세에서
  `Connection reset by peer`가 반복됐다. 후속 진단은 기존/신규 익명 세션 모두
  상세 단계에서 연결 재설정 또는 TLS handshake timeout으로 실패했다.
  GitHub-hosted runner의 실제 첨부 다운로드/추출/OCR 성공은 확인하지 못했다.
  서버 또는 네트워크의 정확한 원인은 확인되지 않았다.
- 앞선 실패 실행: 42579413238, 42579557091, 42579672202, 42579905043, 42580171687.
  이 중 42579557091은 검증 도구의 임시 제목 때문에 기존 제목 일치 검사에서
  실패했고 수정했다. 나머지는 공개 HTTP 연결 실패다.
- 중앙 workflow의 활성 소스 집합은 변경하지 않았다. 기존 9개 수집과 생산
  history/OCR 캐시/사용자 설정/회사 DB를 대체하지 않았다. 다른 신규 사이트는
  수정하지 않았다. 수출바우처의 정식 중앙 활성화와 배포 feed 기반 Windows
  검증은 **보류**다.

메타데이터와 해시만 포함한 상세 증거:
[exportvoucher-attachments-20261109.json](exportvoucher-attachments-20261109.json).

후속 Actions 연결 진단/제한 재시도 결과:
[exportvoucher-actions-stability-20261109.md](exportvoucher-actions-stability-20261109.md).
5초 간격에서도 HTTP 응답 전 연결 재설정이 재현돼 중앙 비활성 상태를 유지했다.
