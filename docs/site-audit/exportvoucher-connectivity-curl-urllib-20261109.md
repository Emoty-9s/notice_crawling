# 수출바우처 curl / urllib 접속 진단 (2026-11-09)

접속은 실행별로 불안정했다. curl과 urllib 모두 성공 이력이 있으나 최종 실행에서는
두 클라이언트 모두 DNS/TCP 성공 뒤 TLS 연결 오류가 발생했다. Python만의 오류,
상세 URL만의 차단, 고정 IP 차단 또는 WAF 차단은 확정하지 않는다.

## 실행과 방법

- 최종 [Actions 42587883923](https://github.com/Emoty-9s/notice_crawling/actions/runs/42587883923),
  workflow 커밋 `a29998d01f44e6227c3eb8e289f2736c49800ae8`.
- 비교용 [Actions 42587471945](https://github.com/Emoty-9s/notice_crawling/actions/runs/42587471945).
- 기준 실패: [42584359750](https://github.com/Emoty-9s/notice_crawling/actions/runs/42584359750),
  기준 프로젝트 커밋 `e53c535`.
- 목록: https://www.exportvoucher.com/portal/board/boardList?bbs_id=1
- 상세: https://www.exportvoucher.com/portal/board/boardView?bbs_id=1&ntt_id=13038
- 별도 수동 workflow, Ubuntu GitHub-hosted runner, curl와 Python 3.13 urllib의
  기본 GET. 인증서 검증 유지. 리다이렉션은 따라가지 않고 상태만 기록했다.
- 각 클라이언트에서 독립 목록/상세, 새 쿠키 세션의 상세→목록,
  새 쿠키 세션의 목록→상세를 비교했다. 요청 사이 5초, DNS/TCP/TLS 연결 예산
  15초, 논리 요청의 재시도·대기를 포함한 전체 예산 30초, 최대 재시도 1회다.
- curl 쿠키는 메모리 파이프로 다음 요청에 전달하고, urllib은 같은 CookieJar를
  재사용했다. 각 순서 시나리오 사이에는 새 쿠키 저장소를 사용했다.
  같은 세션은 쿠키 상태 공유를 뜻하며 TCP 연결 재사용을 뜻하지 않는다.
- 본문은 curl `/dev/null`, urllib 메모리 청크로 버렸다. 본문·쿠키·토큰·첨부는
  파일/로그/artifact에 저장하지 않았다. artifact는 아래 숫자·오류 분류뿐이다.
  프록시·VPN·지정 IP·CAPTCHA 우회는 사용하지 않았다.
- 최종 실행은 논리 GET 12개, 재시도 포함 22회다. 모든 항목에 유효한 지표가
  있으며, 진단 완료 자체를 모든 접속 성공으로 해석하지 않는다.

## 최종 비교 요약

모든 시도의 DNS/TCP는 성공했다. HTTP 상태가 없는 실패는 TLS 단계 실패,
수신 0바이트이며 타임아웃과 리다이렉션은 전부 없었다.

|클라이언트|대상|시도 수|HTTP 200|TLS 실패|성공 응답 바이트|
|---|---|---:|---:|---:|---:|
|curl|list|5|1|4|53450|
|curl|detail|6|0|6|없음|
|urllib|list|6|2|4|53450|
|urllib|detail|5|1|4|48662|

## 최종 실행 전체 요청 비교표

`direct_*`는 독립 쿠키 세션, `detail_first`는 상세→목록,
`same_session_list_detail`은 목록→상세다. 시도 2는 해당 요청의 유일한 재시도다.
DNS/TCP/TLS의 S는 성공, F는 실패다. 시간은 해당 시도의 실제 경과 시간이다.
클라이언트와 시나리오는 한 runner에서 순차 실행했으므로, 새 쿠키 세션의
상세 우선 호출이 runner 전체의 첫 접속은 아니다. 시점·누적 요청 이력을
통제한 실험이 아니므로 순서나 세션만의 인과관계를 단정할 수 없다.

|#|클라이언트|시나리오|대상|시도|HTTP|DNS/TCP/TLS|바이트|초|오류|시간초과|리다이렉션|
|---:|---|---|---|---:|---|---|---:|---:|---|---|---|
|1|curl|direct_list|list|1|200|S/S/S|53450|1.855|없음|아니오|아니오|
|2|urllib|direct_list|list|1|없음|S/S/F|0|0.745|CONNECTION_RESET|아니오|아니오|
|3|urllib|direct_list|list|2|200|S/S/S|53450|1.945|없음|아니오|아니오|
|4|curl|direct_detail|detail|1|없음|S/S/F|0|0.712|TLS_CONNECT|아니오|아니오|
|5|curl|direct_detail|detail|2|없음|S/S/F|0|0.672|TLS_CONNECT|아니오|아니오|
|6|urllib|direct_detail|detail|1|없음|S/S/F|0|0.286|CONNECTION_RESET|아니오|아니오|
|7|urllib|direct_detail|detail|2|없음|S/S/F|0|0.272|CONNECTION_RESET|아니오|아니오|
|8|curl|detail_first|detail|1|없음|S/S/F|0|0.293|TLS_CONNECT|아니오|아니오|
|9|curl|detail_first|detail|2|없음|S/S/F|0|0.679|TLS_CONNECT|아니오|아니오|
|10|curl|detail_first|list|1|없음|S/S/F|0|0.702|TLS_CONNECT|아니오|아니오|
|11|curl|detail_first|list|2|없음|S/S/F|0|0.271|TLS_CONNECT|아니오|아니오|
|12|urllib|detail_first|detail|1|없음|S/S/F|0|0.685|CONNECTION_RESET|아니오|아니오|
|13|urllib|detail_first|detail|2|없음|S/S/F|0|0.257|CONNECTION_RESET|아니오|아니오|
|14|urllib|detail_first|list|1|없음|S/S/F|0|0.672|CONNECTION_RESET|아니오|아니오|
|15|urllib|detail_first|list|2|200|S/S/S|53450|2.032|없음|아니오|아니오|
|16|curl|same_session_list_detail|list|1|없음|S/S/F|0|0.268|TLS_CONNECT|아니오|아니오|
|17|curl|same_session_list_detail|list|2|없음|S/S/F|0|0.267|TLS_CONNECT|아니오|아니오|
|18|curl|same_session_list_detail|detail|1|없음|S/S/F|0|0.268|TLS_CONNECT|아니오|아니오|
|19|curl|same_session_list_detail|detail|2|없음|S/S/F|0|0.711|TLS_CONNECT|아니오|아니오|
|20|urllib|same_session_list_detail|list|1|없음|S/S/F|0|0.713|CONNECTION_RESET|아니오|아니오|
|21|urllib|same_session_list_detail|list|2|없음|S/S/F|0|0.252|CONNECTION_RESET|아니오|아니오|
|22|urllib|same_session_list_detail|detail|1|200|S/S/S|48662|2.649|없음|아니오|아니오|

curl의 `TLS_CONNECT`는 종료 코드 35이며, HTTP 000은 응답 상태 없음으로 정규화했다.
urllib의 `CONNECTION_RESET`은 TLS handshake 중 `ConnectionResetError`다.
curl의 단계 판정은 name lookup/connect/appconnect 완료 시간, urllib은 DNS/TCP/TLS
호출의 완료/예외 계측을 사용한다. 서버의 패킷 캡처나 방화벽 정책 로그는 아니다.

## 직전 실행과의 비교 및 진단 도구 보정

42587471945에서는 독립 목록·상세 모두 curl/urllib HTTP 200이었다.
상세 우선의 첫 상세도 양쪽 모두 200이었다. 같은 세션의 목록→상세는 curl
양쪽 모두 200, urllib은 목록에서 TLS reset 후 한 번의 재시도로 200,
이어 상세도 200이었다. 성공 목록은 53450바이트, 상세는 48662바이트였다.

이 실행의 curl 상세→목록 중 목록 1개는 HTTP 000의 숫자 파싱 오류로 지표가
불완전해 접속 판단에서 제외했다. `000`을 문자열로 받은 뒤 정규화하도록
고치고 위 최종 실행에서 오류 상태까지 모두 재검증했다.
최초 42587274628은 curl의 큰 JSON과 쿠키 출력 파이프 혼합으로 진단 도구가
중단돼 비교 근거에서 제외했다. 메모리 쿠키(stdout)와 작은 숫자 지표(stderr)를
분리했다. 어느 실행에서도 실제 쿠키/본문을 로그로 출력하지 않았다.

## 원인 판단과 필요한 다음 조치

1. 최종 실행에서는 양쪽 클라이언트가 TLS 단계에서 실패했으므로 urllib의
   설정·세션 코드만을 원인으로 볼 수 없다. 네트워크 경로 또는 사이트 측의
   일시적인 연결 제한 가능성이 있다. IP/WAF 차단 여부는 확정할 수 없다.
2. 목록에도 같은 TLS 실패가 있고 일부 상세는 성공하므로 상세 URL에만
   한정된 고정 문제로 볼 근거가 부족하다. 상세 우선/목록 우선의 쿠키 상태만으로
   오류가 해소된다는 증거도 없다.
3. 두 클라이언트 모두 실제 성공한 실행이 있으므로 GitHub-hosted 환경에서
   항상 접속 불가능하다는 판단도 성립하지 않는다. 안정적인 운영 가능 여부와
   File2List/다운로드/OCR은 이번 진단 범위에서 검증하지 않았다.
4. 추가 개발 전에 해당 실행 시각의 서버/TLS·접근 정책 로그와 네트워크 경로를
   확인할 필요가 있다. 기존 크롤러와의 차이는 기본 User-Agent/공개 요청 헤더,
   CookieJar 상태·호출 순서만 동일 조건으로 제한 비교할 것을 제안한다.
   이 결과만으로 HTTP 클라이언트 교체, TLS 설정 변경, 재시도 확대는 제안하지 않는다.

## 변경 범위 확인

신규 진단 workflow와 이 보고서만 commit/push했다. `exportvoucher_notice`의
`enabled=false`, 전체 config, 기존 9개 기관, 중앙 workflow 및 src 코드는
`e53c535`와 동일하다. history/OCR 캐시/feed v3/Windows 프로그램을 실행하거나
변경하지 않았다. 별도의 오프라인 검사에서 workflow/Python 문법, 메모리 쿠키
전달, 비밀값 미출력, HTTP 000/TLS 오류 분류 및 최대 1회 재시도를 확인했다.
