# 공고문 이미지 OCR

중앙 수집은 `수집 → 직접 추출 + OCR → 사전 필터 → feed v3 → Windows A/B` 순서다. 회사 DB는 OCR 입력이 아니며 중앙으로 전송하지 않는다.

## 실행 환경

GitHub Actions Python 3.13 CPU에서 Tesseract 5의 `kor+eng`, PSM 6을 사용한다. PaddleOCR의 별도 추론 런타임·모델 배포 대신 배포판의 Tesseract 한국어/영어 패키지를 사용한다. 설치 이후 OCR은 오프라인이다. 외부 OCR API와 Gemini는 호출하지 않는다.

`requirements-ocr.txt`의 Pillow, PyMuPDF, olefile은 중앙 추출 전용이다. 모델 파일, 원본 다운로드, OCR 캐시는 Pages allowlist에 포함되지 않는다. 공개 feed 계약은 v3 그대로이며 Windows에는 OCR 엔진 설치가 필요 없다.

## 추출 및 상태

- HTML 본문과 텍스트 PDF/HWP/HWPX는 직접 추출한다.
- 본문·첨부 이미지, PDF 포함 이미지, 스캔 페이지, HWP/HWPX 내부 이미지는 본문 텍스트 양과 관계없이 OCR한다.
- 사이트별 본문 영역에서 이미지를 찾고 첨부 영역 링크를 함께 확인한다. 명확한 logo/icon/btn/spacer 파일만 제외하고 나머지는 보수적으로 포함한다. 숨겨진 편집기 HTML, lazy image, srcset, inline CSS 이미지도 탐색한다.
- 본문에는 `[HTML 원문 직접 추출]`, `[첨부 원문 직접 추출]`, `[OCR 추출: 날짜·참가 자격은 원문 대조 필요]`와 파일 SHA256 앞 16자·페이지/내부 파일명을 표시한다. OCR 문장은 교정·보완 생성하지 않는다. 동일 문장을 제거하되 날짜·숫자·자격이 다른 문장은 유지한다.
- 원본 공고의 `apply_end`는 OCR로 변경하지 않는다. Windows A는 OCR 자격을 검토 대상으로 표시하며 직접 추출된 명시적 참가 제외 조건을 보존한다.
- 내부 Notice의 `extraction`에는 전체 SHA256, 직접/OCR 텍스트, 각 파일·페이지 상태, 원본 본문, 재시도 링크를 기록한다. 이 필드는 공개 feed에 투영하지 않는다.
- 실패/미지원/부분 처리/시간 초과는 숨기지 않고 `[추출 미완료: 원문 확인 필요]`로 표시한다. 미완료 공고는 정보 부족만으로 사전 필터에서 제외하지 않는다. 기관 수집 상태와 OCR 진단은 별도 파일이다.

## 제한과 캐시

첨부 25 MiB, 디코딩 이미지 총 32 MP, 다중 프레임 이미지 20프레임, HWPX 내부 2,000개 파일/총 100 MiB, PDF 파일당 실행별 신규 20페이지를 상한으로 한다. 다운로드는 15초 소켓 제한·45초 경과 확인, Tesseract 호출 45초, 파일 파서 프로세스 120초, 중앙 OCR 작업 예산은 720초다. 한도를 넘긴 자료는 미완료로 남는다.

`data/ocr_cache/<extractor-policy>/`에 SHA256 기준 성공 결과를 저장한다. 성공 페이지와 이미지 단위 결과도 체크포인트로 남아 큰 PDF의 다음 실행이 이어진다. 실패 결과는 성공 캐시로 저장하지 않는다. 신규·변경 → 미완료 → 성공 이력 순으로 기관들을 번갈아 처리한다. 동일 URL도 파일 내용을 확인해 변경을 탐지하지만, 동일 바이트의 OCR은 재실행하지 않는다. 목록에서 사라진 미완료 HTTP 첨부도 다음 실행에서 재시도한다. 미관측 inline 이미지는 새 원문을 확보해야 재시도할 수 있다.

`ocr_diagnostics.json`은 기관별 자료 대상/성공/실패/부분/미지원/유예, OCR 단위 대상/성공/실패, 캐시 적중, 인식 문자 수, 경과 시간을 기록한다. 중앙 state artifact에서 캐시와 함께 복구하며 Pages에는 게시하지 않는다.

## 검증

`python -m unittest discover -s tests`는 공통 추출·7개 기관·feed v3·로컬 A/B 회귀를 수행한다. Tesseract 설치 환경에서는 실제 한국어 검증 PNG를 격리 프로세스에서 인식한다.

`python -m tools.ocr_quality_check`는 실제 KHIDI 공고 이미지·PDF·HWP, 실제 이미지로 만든 스캔 PDF/HWPX와 한국어 정답 이미지를 검증한다. Windows에서는 `--docker-image <Tesseract-image>`로 같은 CPU 엔진을 사용할 수 있다. 보고서는 `.run/ocr-quality`에 생성되며 공개 feed에 섞이지 않는다.

Windows에서 기존 EXE가 실행 중이라 기본 배포 폴더가 잠긴 경우 `build_windows.ps1 -OutputName notice_crawling_ocr`로 별도 배포 폴더를 만든다.

근거: [Tesseract 설치와 언어 데이터](https://tesseract-ocr.github.io/tessdoc/Installation.html), [Tesseract 실행 옵션](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html), [PyMuPDF 텍스트·이미지 처리](https://pymupdf.readthedocs.io/en/latest/page.html).
