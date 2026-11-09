# 신규 공고 사이트 확장 검증 결과

기준: 원본 엑셀 `전체 47개 수집원` 47행. 원본은 읽기 전용으로 사용했다. HTTP 응답, 실제 공고 수집, 공개 feed, Windows 표시를 구분한다.

기존 7개 유지. 신규 구현: TIPA, KIAT, GBSA. TIPA는 로컬 검증을 통과했으나 Actions에서 `/eng`로 이동해 중앙 목록 0건이므로 운영 비활성화했다. 나머지 미검증/미구현 수집원도 활성화하지 않았다. 모든 사이트를 연결했다고 보고하지 않는다.

최종 기준 중앙 실행: [42564213368](https://github.com/Emoty-9s/notice_crawling/actions/runs/42564213368). 기관별 성공 여부와 건수는 state artifact에서 직접 확인했다. 공고 수는 최신 3페이지 범위이며 전체 사이트 누적 게시물 수가 아니다.

| 최종 상태 | 수집원 수 |
|---|---:|
| 연결 완료 | 9 |
| 연결 가능하나 추가 개발 필요 | 22 |
| 접근·기술 검증 보류 | 10 |
| 업무 대상 제외·중복 | 6 |
| 현재 연결 불가능 | 0 |

엑셀의 조건부 검증 8개 + 접근 조건부 3개 = 11개이며, 대체 경로 검증 2개를 포함해 2차 대상 13개로 추적했다. 기존 7개, 공개 목록 11개, 접근 미확인 11개, 원본 제외·중복 5개와 합해 47개다. 용인 기업지원 게시판은 실제 본문에서 수혜기업 모집을 확인해 추가 제외했다.

| # | Source ID / 기관 | URL | 상태 | 로컬 상세 / 중앙 수집 / 중앙 feed | 코드 SHA | 미완료·실패 근거 |
|---:|---|---|---|---|---|---|
| 1 | `khidi_business`<br>한국보건산업진흥원 | [공식 주소](https://www.khidi.or.kr/board?menuId=MENU01108) | 연결 완료 | 미수집 / 36 / 34 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 2 | `koat_bid`<br>한국농업기술진흥원 | [공식 주소](https://www.koat.or.kr/board/bid/list.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 목록·상세·다른 2페이지 확인. 공식 다운로드 GET/POST 시도는 200/0바이트. 서명·폼·세션에 따른 정상 공개 다운로드 계약 추가 구현·검증 필요. |
| 3 | `ipnavi_legacy_board`<br>한국지식재산보호원 | [공식 주소](https://www.ip-navi.or.kr/ipnavi/board/boardList.navi?boardCode=B00013) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 원본 /ipnavi/ 경로는 빈 목록. 공식 메뉴의 /board/boardList.navi 대체 목록·2페이지는 확인했으나 상세 GET 연결 종료·POST 연결 재설정. 상세·첨부 검증 전 활성화 금지. |
| 4 | `ripc_pms`<br>한국발명진흥회 RIPC | [공식 주소](https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do) | 연결 완료 | 미수집 / 30 / 30 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 5 | `kipa_bid`<br>한국발명진흥회 | [공식 주소](https://www.kipa.org/kipa/notice/kw_0402.jsp) | 연결 완료 | 미수집 / 30 / 31 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 6 | `kipa_ip_didimdol`<br>한국발명진흥회 수혜기업 | [공식 주소](https://www.kipa.org/kipa/ip001/kw_business_1602.jsp) | 업무 대상 제외·중복 | 미수집 / 미수집 / 미수집 | — | 원본 엑셀 및 기존 범위 제외: 수혜기업용 IP 디딤돌 게시판. 추가 연결 금지. |
| 7 | `exportvoucher_notice`<br>수출바우처 | [공식 주소](https://www.exportvoucher.com/portal/board/boardList?bbs_id=1) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 수행기관 모집 본문·2페이지 확인. 공개 첨부 위젯의 공식 File2List API가 상시 모집 및 최근 모집 두 샘플 모두 [] 반환. 실제 공고 첨부 확보·전용 파일 계약 개발 필요; 페이지 공통 지침 파일을 공고 첨부로 오인하지 않음. |
| 8 | `mssmiv_notice`<br>제조중소기업혁신바우처 | [공식 주소](https://www.mssmiv.com/portal/board/BoardList?bbsId=1) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 실제 접속은 /_queue/index.html 대기열로 이동. 목록·상세 미확인. 대기열 우회하지 않음. |
| 9 | `kista_biz_portal`<br>한국특허전략개발원 사업포털 | [공식 주소](https://biz.kista.re.kr/main.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 IP 통합지원포털 공개 응답. 여러 시스템의 진입 허브이므로 별도 게시판으로 중복 등록하지 않음. 기존 IPPRO와 게시판별 범위·원문 동일성 정리 필요. |
| 10 | `kista_business_board`<br>한국특허전략개발원 사업공고 | [공식 주소](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000382) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 사업정보 공개 목록 및 협력·수행기관 모집 관찰. IPPRO·IPAS 및 같은 기관 입찰 게시판과 중복 여부, 상세·2페이지·첨부 계약 개발/검증 필요. |
| 11 | `kista_bid_board`<br>한국특허전략개발원 입찰공고 | [공식 주소](https://www.kista.re.kr/user/board.do?bbsId=BBSMSTR_000000000442) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 입찰공고 공개 목록·첨부 UI 관찰. 같은 기관 사업정보 게시판과 같은 수행기관 모집 항목이 보임. 원문 동일성과 신규 범위 확인 후 상세·페이징 개발 필요. |
| 12 | `kista_ipams`<br>한국특허전략개발원 IPAMS | [공식 주소](https://biz.kista.re.kr/ipams/) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 산업재산진단기관 관리시스템 홈·모집공고/공지 메뉴 공개. 로그인 화면만으로 전면 접근 불가라 단정하지 않음. 모집 전용 목록·상세·첨부·페이지 검증 필요. |
| 13 | `kista_ippro`<br>한국특허전략개발원 IPPRO | [공식 주소](https://biz.kista.re.kr/ippro//com/iprndMain/selectBusinessAnnounceList.do?bbsType=ac) | 연결 완료 | 미수집 / 60 / 60 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 14 | `kista_ipas`<br>한국특허전략개발원 IPAS | [공식 주소](https://biz.kista.re.kr/ipas/uat/uia/egovLoginUsr.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 로그인 URL에서도 공개 특허동향 협력기관 공고 요약·공지 관찰. 로그인 우회 금지. 공개 전용 경로·IPPRO/본원 사업정보와 중복·상세·첨부 검증 필요. |
| 15 | `kabit_home`<br>한국BI기술사업화협회 | [공식 주소](http://www.kabit.or.kr/) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 원주소는 현재 한국기술사업화협회로 표시됨. 엑셀의 한국BI기술사업화협회와 기관 동일성·변경 근거 및 공식 공고 범위를 먼저 확인해야 함. |
| 16 | `kautm_home`<br>한국대학기술이전협회 | [공식 주소](http://www.kautm.net/) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 협회 홈 공개 접속 복구. TLO 소식 요약 등 혼합 허브이므로 kautm_tlo_news와 별도 수집원으로 동시에 추가하지 않음. 대표 게시판·중복 범위 결정 필요. |
| 17 | `ketep_home`<br>한국에너지기술평가원 | [공식 주소](https://www.ketep.re.kr/) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 홈과 현 입찰 게시판 대체 URL 확인. 홈 자체를 게시판으로 수집하지 않음. ketep_legacy_bid와 단일 수집원으로 정리하고 상세·2페이지·첨부 개발 필요. |
| 18 | `gbsa_bid`<br>경기도경제과학진흥원 | [공식 주소](https://www.gbsa.or.kr/board/bid_info.do) | 연결 완료 | 30 / 30 / 30 | ec65abf | 실제 목록·상세·2/3페이지·첨부·feed v3·Windows A/B 검증. 중앙 기관별 수집 SUCCESS. |
| 19 | `kist_general`<br>한국과학기술연구원 | [공식 주소](https://www.kist.re.kr/ko/notice/general-notice.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 일반공지 목록 공개 응답 확인. 공동·위탁연구, 행사, 교육 등이 혼재. 전문용역·수행기관 모집 본문 판정 및 상세·페이지·첨부 구현 필요. |
| 20 | `kfrm_home`<br>범부처재생의료기술개발사업단 | [공식 주소](http://www.kfrm.org/doc/html/main/main.asp) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 원본 공식 홈 공개 응답 복구. IRIS 공고 및 자체 게시판의 업무 범위·원문 중복 확인과 전용 수집 구현 필요. |
| 21 | `yongin_support`<br>용인기업지원시스템 | [공식 주소](https://ybs.ypa.or.kr/application.do) | 업무 대상 제외·중복 | 미수집 / 미수집 / 미수집 | — | 공개 지원사업 목록과 IP 컨설팅 상세 검증: 지원대상은 용인특례시 소재 중소기업이며 참여기업 모집·지원금/기업부담금 구조. 수행기관 모집으로 취급하지 않음. 기업지원 전용 application 게시판 추가 제외. |
| 22 | `kaips_ip_business`<br>한국지식재산서비스협회 | [공식 주소](http://www.kaips.or.kr/bbs/kaips_12) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 원본 /bbs/kaips_12의 실제 제목·내용은 IP채용정보. 엑셀 명칭 IP사업과 불일치. 공식 IP사업정보 경로 및 kaips_ip_business_alt와 동일성 확인 필요. |
| 23 | `smtech_announcements`<br>SMTECH R&D 사업공고 | [공식 주소](https://www.smtech.go.kr/front/ifg/no/notice02_intro.do) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 원본은 R&D 일정표이며 공식 전용 notice02_list.do 공개 응답도 확인. 기업 R&D 지원과 전문 수행기관 모집의 업무 범위 및 IRIS 중복·상세·페이지·첨부 검증 미완료. 수혜기업 공고를 전문업무로 단정하지 않음. |
| 24 | `iris_announcements`<br>범부처통합연구지원시스템 IRIS | [공식 주소](https://www.iris.go.kr/main.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 사업공고 전용 목록 확인. 여러 부처의 R&D 지원 공고 집계이므로 원 기관과 중복·신청 주체·전문 수행기관 범위 분리 및 상세/첨부/페이지 전용 개발 필요. |
| 25 | `g2b_legacy`<br>나라장터 | [공식 주소](https://www.g2b.go.kr/index.jsp) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 옛 index.jsp는 실제 HTTP 200이지만 접근 가능 브라우저 안내 화면으로 이동. HTML 목록·상세·2페이지 수집 미검증. 공식 공개 검색/정식 API 계약 검증 필요; 브라우저 제한 우회 없음. |
| 26 | `hsbiz_home`<br>화성산업진흥원 | [공식 주소](https://www.hsbiz.or.kr/) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 홈 공개 접속 복구. 전용 게시판 선택·수혜기업/수행기관 구분과 상세·2페이지·첨부 검증 필요. |
| 27 | `rda_bid`<br>농촌진흥청 | [공식 주소](https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry) | 연결 완료 | 미수집 / 30 / 30 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 28 | `seoul_rnd_notice`<br>서울경제진흥원 | [공식 주소](https://seoul.rnbd.kr/client/c030200/c030200_00.jsp) | 연결 완료 | 미수집 / 30 / 19 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 29 | `tipa_legacy_bid`<br>중소기업기술정보진흥원 | [공식 주소](https://www.tipa.or.kr/s040305) | 접근·기술 검증 보류 | 30 / 0 / 0 | 807f27d | 로컬 3페이지 상세 30건·첨부·feed·Windows 검증 완료. 실제 Actions에서는 /eng로 리디렉션되고 목록 테이블 0개, 중앙 수집 0건. 운영 비활성화(fa2dc08), 중앙 성공으로 보고하지 않음. |
| 30 | `snip_bid`<br>성남산업진흥원 | [공식 주소](https://www.snip.or.kr/SNIP/contents/notice12.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 입찰 목록 공개 접속 복구. 전용 어댑터·상세·2페이지·첨부 수집과 중앙/Windows 검증 필요. |
| 31 | `kised_home`<br>창업진흥원 대표/입찰 | [공식 주소](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000) | 연결 완료 | 미수집 / 30 / 32 | 481e793 | 기존 연결 유지. 실제 중앙 수집 및 전체 회귀 테스트로 검증. |
| 32 | `kised_ebid`<br>창업진흥원 계약관리 | [공식 주소](https://ebid.kised.or.kr:8443/opro/main/emgncLoginForm.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 8443 공식 홈의 입찰 목록 요약 공개 응답. 로그인 서비스로만 단정하지 않음. 기존 kised_bid_public과 공고 동일성·상세·첨부·페이지 계약 검증 필요; 기존 공개 어댑터 유지. |
| 33 | `kaia_rnd`<br>국토교통과학기술진흥원 R&D | [공식 주소](https://www.kaia.re.kr/KAIA/contents/K30101000000.do) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 공개 R&D 목록은 확인. R&D 연구개발 지원과 특허법인 전문 수행기관 모집의 신청 범위가 미확정. 입찰 게시판과 별도 범위이며 상세·첨부·페이지 구현 검증 전 비활성. |
| 34 | `kiat_home`<br>한국산업기술진흥원 | [공식 주소](https://cont.kiat.or.kr/bidding/biddingList.do) | 연결 완료 | 45 / 45 / 45 | 816702e | 실제 목록·상세·2/3페이지·첨부·feed v3·Windows A/B 검증. 중앙 기관별 수집 SUCCESS. |
| 35 | `mss_business`<br>중소벤처기업부 사업공고 | [공식 주소](https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 사업공고 목록 공개 응답. 수혜기업·주관기관 모집 혼재 및 반응형 중복 DOM 관찰. 본문 자격 판정·ID/중복·페이지·첨부 개발 필요. |
| 36 | `technopark_main`<br>한국테크노파크진흥회 | [공식 주소](https://www.technopark.or.kr/www/main.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 메뉴로 TP진흥회 자체 목록(5건)과 지역 TP 통합 목록을 별도로 확인. 지역 통합 목록은 여러 외부 기관 원문을 연결하므로 외부 원문·첨부·페이징 및 중복 규칙 추가 개발 필요. |
| 37 | `kier_ebid`<br>한국에너지기술연구원 전자입찰 | [공식 주소](https://ebid.kier.re.kr/noticeList.do?boardGbn=3) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 전자구매 입찰 목록 공개 접속 복구. 상세·2페이지·첨부 및 물품/전문용역 범위 검증·어댑터 개발 필요. |
| 38 | `krict_bid`<br>한국화학연구원 입찰공고 | [공식 주소](https://www.krict.re.kr/prog/bidAnncm/kor/sub04_02/list.do) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 공식 입찰 목록 접근 성공이나 현재 진행중 상태는 0건. 전체/마감 상태 필터와 실제 상세·첨부·2페이지 표본 검증이 남아 있으므로 성공 수집원으로 활성화하지 않음. |
| 39 | `hipa_legacy_notice`<br>화성산업진흥원 예전 주소 | [공식 주소](https://hipa.hscity.go.kr/support/notice/list) | 업무 대상 제외·중복 | 미수집 / 미수집 / 미수집 | — | 엑셀의 옛 경로 제외. 현 화성산업진흥원과 별도 중복 연결 금지; 기존 판단 유지. |
| 40 | `kised_bid_public`<br>창업진흥원 공개 입찰 | [공식 주소](https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000) | 업무 대상 제외·중복 | 미수집 / 미수집 / 미수집 | — | 엑셀 행 기준으로 kised_home의 중복 항목. 실제 기존 어댑터 ID kised_bid_public은 유지하며 두 번 등록하지 않음. |
| 41 | `kaia_legacy_bid`<br>국토교통과학기술진흥원 입찰 | [공식 주소](https://www.kaia.re.kr/KAIA/contents/K30300000000.do) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공식 입찰 목록 공개 확인. KAIA R&D 사업공고와 다른 게시판. 상세·첨부·2페이지 전용 어댑터 개발/검증 필요. |
| 42 | `kaips_ip_business_alt`<br>한국지식재산서비스협회 예전 게시판 | [공식 주소](http://www.kaips.or.kr/bbs_shop/list.htm?board_code=kaips_4) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 옛 bbs_shop URL에서도 IP사업정보 목록 공개 응답. 원 기관 공고 재게시가 많아 기존 기관 원문 중복과 신규 범위 확인·상세/첨부/페이지 개발 필요. kaips_12는 현재 채용정보로 동일 게시판이라 단정하지 않음. |
| 43 | `ipnavi_ipds_login`<br>한국지식재산보호원 IPDS | [공식 주소](https://www.ip-navi.or.kr/cooperationLogin/loginForm.navi) | 업무 대상 제외·중복 | 미수집 / 미수집 / 미수집 | — | 엑셀의 전문기관 로그인 전용 서비스 제외 판단 유지. 공개 공고 게시판으로 추가하지 않음. |
| 44 | `kautm_tlo_news`<br>한국대학기술이전협회 TLO 게시판 | [공식 주소](http://www.kautm.net/bbs/?so_table=tlo_news) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 공개 TLO 목록에 전담 특허사무소·전담대리인 모집과 채용/행사 혼재. 본문·원 기관 중복 확인 및 상세·2페이지·첨부 개발 필요. 홈과 동시 중복 등록하지 않음. |
| 45 | `ketep_legacy_bid`<br>한국에너지기술평가원 예전 입찰 | [공식 주소](https://www.ketep.re.kr/brdartcl/boardarticleView.do?srch_menu_nix=616nZhv3) | 연결 가능하나 추가 개발 필요 | 미수집 / 미수집 / 미수집 | — | 구 상세 경로는 뒤로 화면. 공식 홈 메뉴의 현 입찰 목록 /board?menuId=MENU002080301000000&boardId=BOARD00023 대체 주소를 실제 검증. ketep_home과 단일 수집원으로 상세·페이징·첨부 구현 필요. |
| 46 | `khidi_bioagora`<br>보건산업진흥원 바이오아고라 | [공식 주소](https://www.khidi.or.kr/bioagora) | 접근·기술 검증 보류 | 미수집 / 미수집 / 미수집 | — | 실제 HTTP 200/965바이트 프레임/진입 셸, 공고 본문·목록 미확인. 기존 KHIDI와 범위·대체 대상 검증 전 활성화 금지. |
| 47 | `technopark_legacy_domain`<br>한국테크노파크진흥회 옛 주소 | [공식 주소](http://www.technopark.kr/) | 업무 대상 제외·중복 | 미수집 / 미수집 / 미수집 | — | 엑셀의 옛 도메인 제외 판단 유지. 현 technopark.or.kr 수집원과 중복 추가 금지. |

실제 상세·첨부·2페이지를 검증하지 못한 항목을 성공으로 집계하지 않았다. `미수집`은 0건 성공이 아니다. 상세 HTTP 응답의 크기·SHA-256·오류 근거와 공식 대체 주소는 [sources.json](sources.json)에 기록했다. 기관별 코드/로컬 검증 세부는 [TIPA](tipa_legacy_bid.json), [KIAT](kiat_home.json), [GBSA](gbsa_bid.json)에 있다.

기존 구조 재사용: BaseScraper/BoardScraper, 명시적 registry, pipeline, 공식 첨부 텍스트 추출 및 OCR 큐, feed v3, 공통 증분 수집. 기존 21일 마감과 사용자 수정/삭제/복원, 전문업무·수행기관 판정, 로컬 A/B·matcher 알고리즘을 변경하지 않았다. 게시일·공식 마감일을 확인하지 못한 경우 null이며 제목으로 추정하지 않는다. KIAT 접수 시작일은 게시일로 쓰지 않는다.

전체 Windows unittest 729개 중 728개 통과·환경 의존 1개 제외, 256.058초. 새 EXE의 실제 사이트별 feed와 로컬 A/B는 격리 캐시·합성 실적으로 검사했다. 회사 DB를 열거나 수정하지 않았고 외부 AI API 호출은 0건이다. OCR/첨부 검증은 샘플 기준이며 TIPA·GBSA 일부 PARTIAL/UNSUPPORTED를 성공 OCR로 바꾸지 않았다.

운영 state 보존: 확장 전 history 249건 → 324건; 기존 ID 누락 0건, first_seen 변경 0건. 이전 OCR 캐시 경로 1246개 중 누락 0개. 캐시 내용이 모두 동일하다는 주장은 하지 않는다(미완료 OCR 재시도는 갱신될 수 있음).

Windows 배포 폴더: `dist/notice_crawling_sites_20261109/` 전체를 사용한다. 기존 EXE와 사용자 DB·캐시·설정은 별도 위치에 유지된다. 신규 기관 상태 allowlist 확장 때문에 재빌드했다.

최종 공개 feed는 311건·18,350,338바이트다. 기존 EXE의 16MiB 다운로드 한도를 넘으므로 **이번 새 EXE로 업데이트해야 최신 동기화가 가능하다**. 새 클라이언트는 64MiB 상한을 유지하며 초과 응답 거부·원자적 last-good 캐시 동작을 보존했다(수정 `2ec71d0`). 실제 Pages에서 UPDATED→UNCHANGED, A 분석 311건 SUCCESS, 기관 상태 10개(운영 9개 + 비활성 TIPA 이력), 상세·카드·열람 이력 검증을 통과했다. [운영 검증](operations.json).

복사한 중앙 체크포인트와 캡처 목록으로 증분 재수집 검증: KIAT 45건·GBSA 30건 전부 재사용, 기관별 목록 HTTP 3회, 상세 HTTP 0회·첨부 큐 추가 0건. 운영 state는 변경하지 않았다. 실제 A/B·matcher·21일 정책은 유지됐다.

남은 개발은 위 표에 사이트별로 명시했다. 로그인·CAPTCHA·대기열·접근 제한 우회는 수행하지 않았다. 공개 목록의 존재만으로 업무 적합성을 확정하지 않으며, 같은 기관의 복수 게시판·재게시 공고는 원문 범위와 중복 정책을 검증한 후에만 추가한다.

최종 동기화 용량 수정 `2ec71d0`의 [읽기 전용 Actions 회귀 42567985120](https://github.com/Emoty-9s/notice_crawling/actions/runs/42567985120) SUCCESS: 728개 발견, 666개 통과·선택적 데스크톱/ONNX 의존 62개 제외, 실패 0개(93.027초). GBSA 공개 목록 10건 파싱도 통과했다. 데스크톱/ONNX 검증은 별도 Windows 전체 suite 및 frozen EXE에서 수행했다. 중앙 수집·배포 성공과 로컬/클라이언트 검증을 혼동하지 않는다.
