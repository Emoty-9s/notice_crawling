# M16 contract samples — NOT captured HTTP fixtures

원본 HTML/JavaScript/목록 XHR 응답을 확보하지 못했다. 이 디렉터리는 live scraper 검증 증거가 아니다.
공식 웹 도구에서 관찰한 표 컬럼/텍스트/상세 URL을 최소 HTML로 **재구성**한 계약 테스트 표본이다.
태그/링크 배치, pagination의 `contractPage` 인자, 두 번째 페이지의 공고, 첨부파일 경로는 합성 테스트 데이터다.
실제 목록의 onclick/form/AJAX 구현과 일치한다고 주장하지 않는다. `.contract.html` 이름으로 원본 캡처와 구분한다.
특히 RIPC 첫 공고 행은 관찰된 상세 표본을 목록 형태에 배치한 합성 행이며, 실제 목록 행을 확보했다는 뜻이 아니다.
개인정보/세션/cookie/인증 정보는 없다. 실제 DOM을 확보하면 별도의 검증된 fixture로 교체·보완해야 한다.

확인 출처(2026-11-02):

- https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do
- https://pms.ripc.org/pms/biz/partner/tenderNotice/info.do?bizYear=2026&noticeSeq=553
- https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceList.do?DepthCode1=3&DepthCode2=1&bbsType=ac
- https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?DepthCode1=3&DepthCode2=1&annId=3&annYy=2026&bbsType=ac

RIPC 웹 목록은 데이터 없는 틀만 보였다. KISTA의 페이지 2 링크는 웹 도구에서 첫 페이지를 반환했다.
RIPC는 사용자 정정에 따라 협력기관 입찰 7컬럼(배정예산 포함)으로 다시 구성했다.
상세 공고명/공고기간/단위사업/수요기관/예산 및 짧은 본문 발췌는 위 입찰 상세 표본 기준이다.
목록 사업형태는 상세 단위사업 값을 배치한 합성 값으로 실제 행은 미확보다. 첨부 URL도 여전히 합성이다.
HTTP smoke/DNS 실패와 원본 DOM·실제 pagination·AJAX 미확정은 M16 PARTIAL blocker다.
