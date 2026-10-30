# M05 Fixture Status

## khidi_business

- LIST_FIXTURE: YES
- DETAIL_FIXTURE: YES
- source URL:
  - 목록: https://www.khidi.or.kr/board?menuId=MENU01108
  - 상세 표본: https://www.khidi.or.kr/board/view?boardStyle=&categoryId=&continent=&country=&linkId=48951946&maxIndex=00489508879998&menuId=MENU01108&minIndex=00489499069998&no1=9999999998&pageNum=1&rowCnt=10&schEndDate=&schStartDate=&schText=&schType=0
- 확보 방법: 사용자가 fixture 수집 도구 실행 후 저장한 실제 HTML. tests/fixtures/khidi_business/list.html 및 detail.html을 UTF-8로 읽어 DOM 확인. 원본은 수정하지 않음. 원문 hash는 M05_RESULT.md에 기록.
- 남은 blocker: fixture blocker 없음. 사이트별 목록 1개/상세 1개 표본에 한정되며 실제 네트워크 smoke는 미실행.

## kised_bid_public

- LIST_FIXTURE: YES
- DETAIL_FIXTURE: YES
- source URL:
  - 목록: https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000
  - 상세 표본: https://www.kised.or.kr/board.es?act=view&bid=0005&list_no=4648&mid=a10303000000&nPage=1&tag=
- 확보 방법: 사용자가 fixture 수집 도구 실행 후 저장한 실제 HTML. tests/fixtures/kised_bid_public/list.html 및 detail.html을 UTF-8로 읽어 DOM 확인. 원본은 수정하지 않음. 원문 hash는 M05_RESULT.md에 기록.
- 남은 blocker: fixture blocker 없음. 사이트별 목록 1개/상세 1개 표본에 한정되며 실제 네트워크 smoke는 미실행.

## rda_bid

- LIST_FIXTURE: YES
- DETAIL_FIXTURE: YES
- source URL:
  - 목록: https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry
  - 상세 표본: https://www.rda.go.kr/board/board.do?boardId=bidancm&currPage=1&dataNo=100000813836&menu_id=ofc&mode=updateCnt&prgId=bid_bidancmEntry&searchKey=&searchVal=
- 확보 방법: 사용자가 fixture 수집 도구 실행 후 저장한 실제 HTML. tests/fixtures/rda_bid/list.html 및 detail.html을 UTF-8로 읽어 DOM 확인. 원본은 수정하지 않음. 원문 hash는 M05_RESULT.md에 기록.
- 남은 blocker: fixture blocker 없음. 사이트별 목록 1개/상세 1개 표본에 한정되며 실제 네트워크 smoke는 미실행.

## seoul_rnd_notice

- LIST_FIXTURE: YES
- DETAIL_FIXTURE: YES
- source URL:
  - 목록: https://seoul.rnbd.kr/client/c030200/c030200_00.jsp
  - 상세 표본: https://seoul.rnbd.kr/client/c030200/c030200_04.jsp?cPage=1&sField=&sWord=&seqNo=1129
- 확보 방법: 사용자가 fixture 수집 도구 실행 후 저장한 실제 HTML. tests/fixtures/seoul_rnd_notice/list.html 및 detail.html을 UTF-8로 읽어 DOM 확인. 원본은 수정하지 않음. 원문 hash는 M05_RESULT.md에 기록.
- 남은 blocker: fixture blocker 없음. 사이트별 목록 1개/상세 1개 표본에 한정되며 실제 네트워크 smoke는 미실행.

## kipa_bid

- LIST_FIXTURE: YES
- DETAIL_FIXTURE: YES
- source URL:
  - 목록: https://www.kipa.org/kipa/notice/kw_0402.jsp
  - 상세 표본: https://www.kipa.org/kipa/notice/kw_0402.jsp?article_no=134746&board_no=15&board_wrapper=/kipa/notice/kw_0402.jsp&mode=view&pager.offset=0
- 확보 방법: 사용자가 fixture 수집 도구 실행 후 저장한 실제 HTML. tests/fixtures/kipa_bid/list.html 및 detail.html을 UTF-8로 읽어 DOM 확인. 원본은 수정하지 않음. 원문 hash는 M05_RESULT.md에 기록.
- 남은 blocker: fixture blocker 없음. 사이트별 목록 1개/상세 1개 표본에 한정되며 실제 네트워크 smoke는 미실행.
