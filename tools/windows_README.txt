공고 · 로컬 실적 매칭 — Windows 배포본

notice_crawling.exe를 더블클릭합니다. Python/가상환경 설치가 필요 없습니다.
exe와 _internal 폴더를 함께 보관하세요. exe만 복사하면 실행되지 않습니다.

이 프로그램은 기존 M15 읽기 전용 로컬 UI입니다. 인터넷 수집/다운로드나
새 실적 DB/cache 생성을 하지 않습니다. 기존 정상 데이터를 준비해야 합니다.

기본 사용자 데이터 위치:
  %LOCALAPPDATA%\NoticeCrawling\cache\snapshot.json
  %LOCALAPPDATA%\NoticeCrawling\performance.db

다른 위치의 기존 파일은 화면 위의 M12 snapshot 파일/M13 실적 DB 경로에
입력한 뒤 '파일 다시 읽기'를 누르세요. 파일이 없으면 상태 오류가 표시됩니다.
명령줄/바로가기의 --cache, --db 경로 지정도 그대로 지원합니다.

공고 선택 → 기준 연도 직접 입력 → TOP N 입력 → 매칭 실행 → 추천 선택.
총점과 규칙별 점수/근거/합계를 확인합니다. 기준 연도 자동 선택은 없습니다.

개인 DB/cache/개발용 테스트 데이터는 배포본에 포함되지 않습니다.
사용자 파일을 _internal 폴더 안에 저장하지 마세요.
