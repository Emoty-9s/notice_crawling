Notice · Dark Night 업무 모니터링 대시보드 — Windows 배포본

notice_crawling.exe를 실행합니다. Python/가상환경 설치가 필요 없습니다.
exe와 _internal 폴더를 함께 보관하세요. exe만 복사하면 실행되지 않습니다.

화면 표시 후 GitHub 중앙 공고를 백그라운드로 확인합니다.
파랑: GitHub 연결 정상 / 노랑: 확인 중 또는 마지막 저장 데이터 사용 / 빨강: 연결 실패, cache 없음.
기관 카드의 점은 마지막 중앙 수집 결과입니다. 기관 사이트에 직접 접속하지 않습니다.
공개 상태 정보가 없으면 회색으로 표시합니다. 오류 원문/private state는 가져오지 않습니다.

공고 제목 → 앱 내부 상세 보기 → 원문 보기 버튼으로 기본 브라우저 열기.
공고 카드의 '실적 매칭 펼쳐보기'에서 순위·총점·규칙별 근거를 확인합니다.
매칭 기준 연도를 직접 입력하세요. TOP N 기본값은 5입니다.
추천 선택용 별도 화면은 없습니다.

실적은 로컬 DB를 읽기 전용으로 사용합니다. DB가 없어도 공고를 볼 수 있습니다.
개인 실적 DB를 생성·수정하거나 외부로 전송하지 않습니다.
상단 '설정 · 정보'에서 기존 DB/cache 경로를 지정할 수 있습니다.
기본 경로:
  %LOCALAPPDATA%\NoticeCrawling\cache\snapshot.json
  %LOCALAPPDATA%\NoticeCrawling\performance.db
--cache / --db / --base-url / --reference-year / --top-n 옵션도 지원합니다.
--offline은 네트워크 없이 기존 공고 cache만 표시합니다.
사용자 파일을 _internal 안에 저장하지 마세요. 개인 DB/cache는 배포본에 포함되지 않습니다.

명시적 배포본 점검:
  notice_crawling.exe --smoke-report C:\원하는경로\smoke.json --feed-url https://emoty-9s.github.io/notice_crawling/
임시 캐시에서 UPDATED/UNCHANGED, 실제 Tk 화면과 공고·아코디언·상세 이동을 점검합니다.
기존 검증 DB를 쓰려면 --smoke-db 경로를 추가합니다. 개인 DB를 새로 만들지 않습니다.
결과 JSON의 status=SUCCESS와 프로세스 종료 코드 0을 확인하세요.
