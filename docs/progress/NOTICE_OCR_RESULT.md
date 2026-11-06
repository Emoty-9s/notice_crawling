# 공고문 이미지 OCR 통합 검증 결과

구현·검증 코드 SHA: `5e6e7bd1f79e16128c913fb66930b342f9a8824f`.
실제 Actions: [42149263651](https://github.com/Emoty-9s/notice_crawling/actions/runs/42149263651) — build/deploy SUCCESS. 전체 1273초, 수집·추출·게시 준비 단계 1106초.

## 적용 엔진과 흐름

실제 Actions에서 Python 3.13.18, Tesseract 5.5.0 `kor+eng`, PSM 6을 Linux CPU에서 오프라인 실행했다. Pillow·PyMuPDF·olefile을 사용하며 Gemini·유료 OCR API를 호출하지 않는다.
HTML/PDF/HWP/HWPX 원문 직접 추출과 본문·첨부 이미지 OCR을 완료 가능한 범위까지 수행한 뒤 사전 필터를 실행한다. 충분한 HTML 텍스트가 있어도 이미지 OCR을 시도한다. 모델·캐시·내부 추출 메타데이터는 Pages 게시 대상에 포함하지 않는다.

PaddleOCR도 CPU와 한국어 모델을 지원하는 대안으로 검토했다. 이번에는 배포판 패키지로 한국어·영어 모델을 설치할 수 있는 Tesseract를 선택해 별도 Paddle 추론 런타임·모델 관리 의존성을 줄였다. 두 엔진의 정확도 우열을 비교한 벤치마크라는 뜻은 아니다. [PaddleOCR 공식 설치 안내](https://www.paddleocr.ai/main/en/version3.x/installation.html), [한국어 모델 안내](https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/blog/multi_languages.html), [Tesseract 설치 안내](https://tesseract-ocr.github.io/tessdoc/Installation.html).

## 기관별 실제 결과

| 기관 | 수집 공고 | 수집 상태 | OCR 단위 대상 | 성공 | 실패·미완료 | 인식 문자 |
|---|---:|---|---:|---:|---:|---:|
| 한국보건산업진흥원 | 34 | SUCCESS | 123 | 95 | 28 | 62,185 |
| 창업진흥원 | 30 | SUCCESS | 110 | 49 | 61 | 7,180 |
| 농촌진흥청 | 30 | SUCCESS | 31 | 22 | 9 | 3,794 |
| 서울 R&D | 30 | SUCCESS | 46 | 45 | 1 | 10,286 |
| 한국발명진흥회 | 30 | SUCCESS | 43 | 38 | 5 | 19,420 |
| RIPC | 30 | SUCCESS | 14 | 12 | 2 | 145 |
| 한국특허전략개발원 | 60 | SUCCESS | 11 | 11 | 0 | 78,960 |

OCR 단위는 발견된 이미지·PDF 페이지의 처리 결과이며 캐시 재사용을 포함한다. 고유 공고 수나 고유 SHA256 수와 다르다. 아직 다운로드하지 못한 첨부 내부의 이미지 수를 성공 수에 포함하지 않는다.

OCR 단위 합계는 대상 378, 성공 272, 실패·미완료 106이며 인식 문자는 181,970자다. 전체 자료는 812개 중 성공 122, 부분 28, 실패 27, 미지원 6, 시간 예산 유예 629개다. 파일 캐시 재사용은 37건이다.

| 기관 | 전체 자료 대상 | 성공 | 부분 | 실패 | 미지원 | 유예 | 파일 캐시 재사용 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 한국보건산업진흥원 | 123 | 34 | 4 | 0 | 0 | 85 | 9 |
| 창업진흥원 | 66 | 9 | 13 | 0 | 0 | 44 | 3 |
| 농촌진흥청 | 51 | 8 | 3 | 1 | 6 | 33 | 5 |
| 서울 R&D | 116 | 26 | 1 | 0 | 0 | 89 | 2 |
| 한국발명진흥회 | 65 | 11 | 5 | 0 | 0 | 49 | 5 |
| RIPC | 92 | 23 | 2 | 0 | 0 | 67 | 6 |
| 한국특허전략개발원 | 299 | 11 | 0 | 26 | 0 | 262 | 7 |

중앙 history 244건을 보존했다. 추출 상태: `{'SUCCESS': 29, 'PARTIAL': 215}`. 미완료 자료는 성공으로 저장하지 않으며 다음 실행에서 재시도한다.
오류·유예 코드 집계(자료/페이지 단위): `{'RUN_BUDGET_DEFERRED': 629, 'OCR_EMPTY': 101, 'IMAGE_PIXEL_LIMIT': 1, 'UnidentifiedImageError': 4, 'ConnectionResetError': 17, 'RemoteDisconnected': 9, 'UNSUPPORTED': 6, 'ATTACHMENT_BYTE_LIMIT': 1}`.

KISTA 일부 첨부는 원본 서버가 연결을 끊는 사례를 확인했다. 본문 이미지의 OCR 결과는 유지하되 해당 첨부는 미완료로 남긴다. 미지원 형식, 이미지 크기 제한, OCR 빈 결과, 일부 PDF 페이지만 처리한 경우도 기록한다.

## OCR로 보강된 업무 정보

직접 추출 텍스트만으로는 전문 업무를 판정하지 못했지만 OCR을 추가한 뒤 검토 가능한 업무 근거를 얻은 공고: 3건. 이번 3건은 모두 마감된 과거 공고이며, 현재 신청 가능한 기회 수로 해석하지 않는다.

| 기관 | 공고 | 직접 추출만 사용 | OCR 통합 후 | 원문 마감일 |
|---|---|---|---|---|
| 한국특허전략개발원 | [2026년 지재권 연계 연구개발 전략지원 사업 하반기 4차 협력기관 모집 공고](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?annYy=2026&annId=75&bbsType=ac) | INSUFFICIENT | REVIEW / CHECK_REQUIRED | 2026-09-14 |
| 한국특허전략개발원 | [2026년 지재권 연계 연구개발 전략지원 사업 하반기 3차 협력기관 모집 공고](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?annYy=2026&annId=68&bbsType=ac) | INSUFFICIENT | REVIEW / CHECK_REQUIRED | 2026-08-25 |
| 한국특허전략개발원 | [2026년 지재권 연계 연구개발 전략지원 사업 하반기 3차 협력기관 모집 공고](https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?annYy=2026&annId=67&bbsType=ac) | INSUFFICIENT | REVIEW / CHECK_REQUIRED | 2026-08-25 |

별도 실제 자료 비교에서는 KISTA 하반기 4차 공고(annId=75)의 기존 본문 268자에 이미지 OCR 14,504자를 추가해 특허·논문 분석 실무를 맡을 협력기관 선정 목적을 확인했다. 해당 공고는 2026-09-14 마감된 과거 공고다. 첨부 다운로드 실패는 별도로 남았다.

## 실제 OCR 품질과 필수 검증

| 검증 자료·경로 | 결과 |
|---|---|
| 실제 KHIDI 공고 PNG | SUCCESS, 598자 |
| 같은 실제 공고의 JPG | SUCCESS, 597자 |
| 실제 공고 이미지로 구성한 스캔 PDF | SUCCESS, 598자 |
| 서울 R&D 실제 원본 스캔 PDF | SUCCESS, 3페이지 직접 텍스트 0자 → OCR 1869자 |
| 실제 이미지가 포함된 HWPX 경로 | SUCCESS, 610자 |
| 실제 KHIDI 텍스트 PDF 직접 추출 | SUCCESS, 7281자 |
| 실제 KHIDI HWP 직접 추출 | SUCCESS, 8801자 |
| 한국어 정답 이미지 | 특허분석 수행기관 모집, 특허법인 또는 변리사 인식 |
| HTML+이미지, 로고 제외, 실패 격리, SHA256 재사용, PDF 이어 처리 | unittest PASS |
| RDA 실제 JavaScript 다운로드 첨부 | HWPX 2개 직접 추출+OCR 성공, 별도 미지원 자료 기록 |

실제 KISTA OCR에서 일부 연도가 2026 대신 2006으로 인식되는 오류도 확인했다. 이를 교정해 사실로 생성하지 않는다. OCR 텍스트는 출처를 표시하고 Windows는 자격·날짜를 원문 대조 대상으로 남긴다. HTML 원문에서 수집한 마감일 값은 OCR로 덮어쓰지 않았다.

## 테스트·feed·Windows 호환

- Windows 전체 unittest: 699개, PASS. 네이티브 Tesseract 항목 1개는 Linux에서 실제 실행했다.
- Actions 전체 unittest: 698개, PASS(선택적 데스크톱 의존 항목 62개 제외). 네이티브 한국어 OCR 격리 프로세스 검증은 실제 실행했다. 데스크톱 항목은 Windows 전체 실행에서 검증했다.
- 공개 feed schema v3, 239건, 3,575,531바이트. 영속 history에서 재생성한 feed와 게시된 JSON이 일치하고 Windows consumer 검증을 통과했다.
- 기존 공개 공고 중 본문이 보강·갱신된 항목 220건. history와 공개 projection의 건수 차이는 기존 사전 필터 정책 때문이다.
- 최신 EXE 실제 feed 동기화 UPDATED→UNCHANGED, 로컬 A 처리 239건, 7개 기관 상태 표시 SUCCESS.
- 실적 업로드, 로컬 A/B AI, matcher, 사용자 수정·삭제·취소, 재시작 후 보존, 원본 파일 불변, DB 무결성 검증 PASS. 회사 데이터 처리 경로 외부 호출 0건.
- 기존 공고 ID·중앙 history, 모든 기관 공통 21일 마감 규칙, 사용자 마감일 수정·공고 삭제/복원, 실적 DB와 matcher 회귀 PASS.

배포본: `dist/notice_crawling_ocr_verified/notice_crawling_ocr_verified.exe`. `_internal`을 포함한 폴더 전체를 사용한다. OCR 검토 정책을 적용하려면 이 새 EXE를 사용한다. 기존 feed v3 읽기 계약은 유지하며, Windows에 OCR 모델을 설치할 필요는 없다.

## 운영 제한

첨부 25 MiB, 이미지 총 32 MP, PDF 실행별 신규 20페이지, 파일 파서 120초, OCR 호출 45초, 수집 후 OCR 예산 720초, Actions 전체 상한 45분을 적용한다. 성공한 파일/이미지/페이지 캐시는 SHA256으로 재사용한다. 신규·변경 자료를 우선하고 남은 자료는 미완료 상태로 다음 실행에 넘긴다.

원문 정보가 미완료인 공고는 `PARTIAL`, OCR 근거는 `OCR_REVIEW`/`CHECK_REQUIRED`로 구분한다. 로컬 추론 실행 성공과 원문 수집·자격 확인 완료를 동일하게 취급하지 않는다.

남은 자료는 기존 매일 07:17 KST 예약 Actions에서 캐시를 복원해 재시도한다. 이번 통합·배포 검증 완료가 모든 과거 첨부의 OCR 완료를 뜻하지 않는다.
