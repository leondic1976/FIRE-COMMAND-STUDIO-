# 시험 계획·실행 기록

## 환경과 범위

Windows 로컬 개발, Python 3.14.3, Node 24.13.0, npm 11.11.0, SQLite, 단일 API 프로세스. React/TypeScript/Vite/Three.js 웹 빌드와 Pytest/Vitest를 사용한다. PostgreSQL·기관 LAN·기관 SOP·실제 명부/시설·지정 GPU/프로젝터는 제공되지 않았다.

실제 사용자와 자동 가상 계정을 엄격히 구분한다. 자동 시험에서 입력한 답안·구두 확인·승인 메모는 전부 합성 시험자료다.

최신 고정본 결과는 문서 마지막의 최종 로컬 검증 항목과 [버전별 증거](evidence/README.md)를 따른다. 아래 초기 MVP 수치는 당시 버전의 역사 기록이다.

## 실행 결과 (중간 기록)

| 실행 | 실제 결과 | 처리 |
|---|---|---|
| 최초 Pytest | 35 통과, 11 임시폴더 권한 오류 | 권한 요청 후 저장소 runtime/pytest 사용 |
| 초기 통합 | 46 passed / 17.17s | 역할·발행·원자성·폐루프·재생·AAR 검증 |
| 추가 권한·인계 | 57 통과, 1 기대값 실패 / 30.27s | URL 비허용의 405도 정상 차단으로 시험 수정 |
| 중간 회귀 | 60 passed / 34.19s | 동시 12명령·백업복구 포함 |
| 규칙·공급자 | 64 passed / 40.69s | 시간 자동 사건·비활성 공급자 포함 |
| 운영모드·퍼즈 | 80 passed / 50.90s | 인증·GLB·조건식·스트림 제한 |
| 독립 Solo | 81 passed / 51.84s | 참가자 자체 시작·모의 동료·개인 격리 |
| AAR·시작 게이트·암호 | 86 passed / 54.41s | 완료 증거·KST·만료 배치·버전 scrypt |
| 정적 웹 압축 | 86 통과, 1 시험 기대값 실패 | 스트리밍 gzip은 Content-Length가 없을 수 있음; 원시 바이트 해제 검증으로 수정 |
| 정적 웹 집중 재시험 | 1 passed / 0.78s | gzip 내용·압축률·아이콘·CSP 확인 |
| 손상 XLSX 퍼즈 | 15 통과, 1 파서 예외 재현 | 매니페스트·XML/.rels·파서 예외 처리 보완 |
| 입력 보완 후 전체 | 91 passed / 57.09s | JUnit: artifacts/tests/pytest.xml |
| CSV/XLSX 집중 재시험 | 18 passed / 6.89s | 긴 CSV 필드·정상 미리보기·과대 시트·XML 포함 |
| 계정 전환 보안 회귀 | 13 passed / 14.74s | 이전 쿠키 폐기·비공개 WS 종료 포함 |
| 최종 전체 회귀 | **93 passed, 3 skipped / 58.06s** | JUnit: artifacts/tests/pytest-final.xml; 3개는 승인 대기 브라우저 시험 |
| 웹 공통 규칙 | 2 files / 9 tests passed | 가상시각·KST·모드 문구·좌표/회전 |
| 웹 최종 규칙 | **3 files / 12 tests passed** | 기존 규칙 + 새 제작본 선택 유지3개 |
| TypeScript + Vite | 통과 | 3D 지연 로딩, 기본 JS 약339KB / 3D 약570KB; 실제 화면 실측과 구분 |
| 최종 TypeScript + Vite | **통과** | 기본 JS340.62KB(gzip105.14KB), 지연3D570.34KB(gzip148.84KB); 500KB 청크 경고 잔존 |
| Python 컴파일 | **통과** | apps/api·scripts·tests |
| 계약·합성 예시·계획 사본 | **통과** | 예시4개 모델 검증, 매니페스트 해시7개, 현재 원본과 사본 바이트 동일 |
| 브라우저 개선 후 API 회귀 | **93 passed / 61.55s** | 단위·통합·보안, artifacts/tests/pytest-browser-regression.xml |
| 최종 웹 규칙·정적 자산 | **12 tests passed, 정적 자산1 passed / 0.86s** | 선택/좌표/시각·gzip/보안 헤더 |
| 최종 빌드 | **통과** | 기본342.89KB(gzip106.03KB), 지연3D571.85KB(gzip149.43KB); 큰 청크 경고 유지 |

최종 회귀 결과와 장시간 시험 종료 수치는 작업 종료 전 아래에 추가한다. 중단·진행 중인 시험을 통과로 기록하지 않는다.

직접 Python 의존성13개의 핀/설치 버전과 JavaScript 잠금파일155항목의 선언을 `docs/evidence/dependency-inventory.json`에 기록했다. `scripts/dependency_inventory.py` 실행 통과이며 보안/라이선스 승인과 구분한다.

## 12접속·60분 시험

스크립트: `python scripts/perf_soak.py --duration 3600 --output artifacts/perf/soak-60min-verified.json`

진행자 1·평가관 1·가상 참가자 10의 실제 HTTP/WS 연결을 연다. 10개 사건과 장면 패치를 적용하고, 주기적으로 일시정지·재개를 수행한다. 매 명령 후 전 접속의 최신 버전 도달을 확인한다. 종료 때 사건 누락·중복, 연속 시퀀스, 최종 장면 상태, 시험 중 API 소스 변경 여부를 검사한다.

- 10초 예비 시험: 12접속·14명령·오류 0·최대 약0.32초, 실제 10.33초 유지.
- 1차 60분 시도: 약310초 지점까지 오류 0, 소스 보완을 위해 중단. `soak-attempt-01-incomplete.json`. 60분 통과 아님.
- 2차 60분 시도: 약401초 지점까지 오류 0, 명부 파서 보완을 위해 중단. `soak-attempt-02-incomplete.json`. 60분 통과 아님.
- 3차 60분 시도: 약989초 지점까지 오류 0, 계정 전환·선택 경합 보완을 위해 중단. `soak-attempt-03-incomplete.json`. 60분 통과 아님.
- 최종 실행: **통과 — 실제3,600.40초 / 12접속 / 246명령 / 오류0 / 최대 동기화0.458초 / P95 0.386초**. 각 접속은247개 스냅샷을 수신하고 최종 버전247에 도달했다. 사건10개 순서·중복/누락·연속 로그·최종 장면·API 소스 해시 검사 통과. 프로세스 종료코드0.
- 검토용 증거: [60분 결과](evidence/history/mvp-20261117/soak-60min.json), [최종 Pytest 요약](evidence/history/mvp-20261117/pytest-final.json), [소스 해시](evidence/history/mvp-20261117/source-sha256.json). `scripts/finalize_evidence.py`가 완료/통과/시간/접속 수/소스 일치를 재확인한 뒤 생성했다.

이 시험은 같은 PC의 loopback/SQLite 조건이다. GPU·3D FPS·실제 LAN·사람 10명의 토론 및 회의실 가독성을 검증하지 않는다.

## 브라우저·화면 검증 — 완료한 로컬 범위

사용자가 별도 백그라운드 검증을 명시적으로 지시했다. Playwright1.62.0의 독립 headless Chromium151.0.7922.34와 Firefox153.0을 사용했다. 기존 Chrome 프로필·탭·로그인은 사용하지 않았으며, 고정된 http://127.0.0.1:8010의 합성 데모만 검증했다.

**최종 Chromium6개 통과 / 95.70s, Firefox6개 통과 / 131.19s.** JavaScript 미처리 예외도 감시했다. 이 초기 버전의 검토용 집계는 `docs/evidence/history/mvp-20261117/browser-final.json`, 원본 JUnit·캡처·오류 기록은 Git에서 제외한 `artifacts/tests/`, `artifacts/browser/`에 있다.

이후2D 목록을 가리던3D 범례/성능 배지를 숨기고 스크롤 안내·키보드 초점을 보완했다. 관련 미지원 대안 시험을 두 엔진에서 집중 재검증해 **Chromium1개(5.54s),Firefox1개 통과**했다. 초기 전체12건과 별도 집중2건을 구분하며 `docs/evidence/history/mvp-20261117/browser-layout-final.json`에 기록한다.

| 시험 | 실제 확인한 흐름 |
|---|---|
| 제작→실행→AAR | 새 훈련 선택 유지, 건물명/층수/회전 편집·저장·새로고침 후 재조회,7역할 카드/문항/설명/구두확인, 리허설/발행,10사건,3D 시점/분리/원위치/드래그, 보고7단계/지휘결론, 대체6단계, 종료, 관찰/개선과제/완료 증거/AAR승인/JSON/인쇄 미리보기 |
| 개인 연습·격리 | 참가자 자체 생성·모의 동료 피드백·종료, 로그아웃/다른 참가자 전환 후 기존 개인 세션403 |
| 실행본·재접속·계정 | 과거 실행본 선택/복귀, 연결 종료 후 에뮬레이션 오프라인, 서버 상태 변경 후 재접속 최신 상태, 진행자→공동화면 권한 전환·새로고침에서 비공개 콘솔 없음 |
| 모바일·키보드 | 390×844 가로 넘침 없음, 새 훈련 대화상자 초점/Shift+Tab/ESC |
| 공용화면 | 공개 메시지2개, 비공개 사건/미래 후보/개인평가/용수 고장 사실이 공용 REST에 포함되지 않음, 진행자 제어 미노출 |
| WebGL 미지원 | WebGL 컨텍스트를 미지원으로 주입,2D 대안 표시, 연기3단계/화염2단계/인접동 주의/출입구 폐쇄 문장과 건물 선택 유지 |

AAR5쪽과 임무카드1쪽을 실제 앱의 인쇄 스타일로 PDF 생성하고 설치된 PyMuPDF1.27.2.3으로 모두 렌더링해 직접 확인했다. 한글·표·워터마크·단계별 인계 메모·머리말/쪽번호·필수 근거 텍스트를 확인했고 페이지 밖 텍스트는 없었다. PDF는 합성 검증 예시이며 기관 승인 보고서가 아니다.

추가 장면 표본은 인증된 headless Chromium,1920×1080,SwiftShader 소프트웨어 렌더러 조건이다. 장면 표시0.543초,20초간10회 표시 FPS 표본24~28·중앙26,7,344 triangles,2D 전환 없음이었다. 최초 로그인 전체 시간·기관 기준 PC/GPU/프로젝터·실제 LAN·장기 렌더링 성능 인증으로 확대하지 않는다. 이 초기 원시 표본은 `docs/evidence/history/mvp-20261117/scene-probe.json`에 보존한다.

### 실패와 개선 이력

- 첫3건:1통과/2실패. group/입력 요소 이름 중복을 구분하지 않은 시험 선택자와 WS/REST 응답 순서 가정을 수정했다. 수정 후3개 통과.
- 확장 전과정3건: Chromium61.41s,Firefox81.53s 통과.
- 추가5건 시도:3통과/2실패. 개인 세션의 문서화된403을404로 기대한 시험과, offline에서 close handshake 완료를 기다리지 않은 시험 조건을 수정했다. 실제 실행본 변경 시 연결 표시 초기화도 보완했다. 이후5개 통과.
- 실제 화면/인쇄 검토로 전체 실행본 선택, 한국어 타임라인·인계 메모/증거, 인쇄 머리말/쪽번호,2D의 상태 문장/회전/윤곽을 개선했다. 최종6건씩 양쪽 엔진에서 재검증했다.
- 기존 CUA Chrome 접근 승인 거절·호스트 부재는 과거 연결 실패다. 별도 headless 허용 후 해소한 검증 경로와 혼동하지 않는다. 추가 Chrome 설정은 현재 검증의 필요조건이 아니다.

### 재현

```powershell
python -m pip install -r requirements-browser.txt
python -m playwright install chromium firefox
$env:RUN_BROWSER_TESTS='1'
$env:BROWSER_ENGINE='chromium'
python -m pytest tests/e2e -q --basetemp=runtime/pytest-browser
$env:BROWSER_ENGINE='firefox'
python -m pytest tests/e2e -q --basetemp=runtime/pytest-browser-firefox
Remove-Item Env:\RUN_BROWSER_TESTS
Remove-Item Env:\BROWSER_ENGINE
```

일반 API 회귀와 브라우저 회귀를 분리한다. 기본 전체 Pytest에서는 선택적6개 브라우저 시험을 skip하며, 이는 승인 대기나 실패라는 뜻이 아니다. 실제 회의실·후열 가독성·보조기술 사용자·공식 Kakao 실키/도메인·실자료 검수는 별도다.

## 기관 시범훈련

기관 담당자·소방 실무 검수자·보안 책임자·기준 PC·약 10명 참가자가 필요하다. 계획 §17.2에 따라 역할숙지→공동 상황판→보고/토론→통제단 전환/인계→AAR/재훈련을 수행하고 실패도 관찰 증거로 남긴다. 기관 승인 체크리스트를 채우기 전 정규 출시하지 않는다.


## 2026-11-17 M4 공공자료 회귀

공식 명세를 기준으로 구현했으며 시험 응답은 모두 합성이다. 실제 건축물/기상/용수 키·기관 데이터셋 응답 시험과 구분한다. `scripts/run_external_fixture.py`의 127.0.0.1:8011에서 HTTP 어댑터는 MockTransport로만 동작한다. 실제 외부 공급자에 전송하지 않는다.

- 단위: 고정 호스트/파라미터, 크기/타임아웃/네트워크/리다이렉트/압축/XML 오류, 키 마스킹, 싱글턴/빈 목록/중복/손상, 단위/시각/격자/결측/좌표, 개인정보 필드 제거, 관리자가 확인한 카탈로그 검증.
- 통합: 수집 불변성, 명시 검토/CAS/멱등성, 내부 자료 외부전송 차단, 발행본 변경 차단, 원자적 실패, 역할·기관·훈련 격리, 위조 차단, 교체/복제, 분당 제한, 수집 중 경합, 공용/참관 REST·WS 유출, AAR 동결 자료, 구버전 JSON 읽기/저장.
- 브라우저: 건물/날씨/용수 조회·검토·저장·새로고침, 반영 전 무변경, 실제/가상 선택 게이트, 단위/미확인 상태, 비공개 메모 제외, 390px 넘침, 동일 실행본 재선택, 새 기준자료 AAR. 기본6개 흐름도 같은 새 백엔드에서 재실행한다. `STUDIO_BROWSER_BASE=http://127.0.0.1:8011`, `RUN_BROWSER_TESTS=1`, `RUN_EXTERNAL_BROWSER_TESTS=1`. 기본 시험은 선택적7개 브라우저 시험을 실행하지 않는다.

첫 전체141건은29.34초에 통과했다. 그 뒤 구버전 JSON 호환성1건/WS 단언을 추가했고 통합15건은5.75초에 통과했다. 최종 결과를 아래에 추가한다. 과거 60분 소스 해시는 변경된 현재 API와 다르므로 현 버전의 장시간 통과로 기록하지 않는다.


### M4 공공자료 최종 검증 증거

- 전체 API·단위·통합·보안 **142 통과 / 29.958초**. 새 공공자료 관련 시험은34단위+15통합=49건이며 전체142건에 포함된다.
- Chromium7건/108.144초, Firefox7건/158.858초 통과. 초기 로드 대기 보완 후 Chromium 공공자료1건을 별도로 재검증해 9.947초에 통과했다. 중복 실행을 별개의 기능 수로 합산하지 않는다. JavaScript 미처리 예외 기록은 비어 있다.
- Firefox 첫 실행6통과/1실패는 별도 JUnit으로 보존한다. 초기 목록/실행본/대화상자 완료를 명시한 시험으로 전체7건을 다시 통과했다. 제품 권한/발행 게이트를 완화하지 않았다.
- 웹12건·TypeScript/Vite 빌드 통과. 지연3D 청크500kB 초과 경고를 유지한다. 최신 기준자료 AAR PDF3쪽을 모두 렌더링해 직접 확인했다. 한글·출처/기준일/관측단위·워터마크/쪽번호가 보이고 비공개 메모가 없으며 페이지 경계 밖 텍스트/잘림/겹침이 관찰되지 않았다.
- 합성 예시4개와 매니페스트7개 해시 검증 통과. plan.md와 사본 바이트 일치. `docs/evidence/public-data-20261117.json`에 실제 JUnit 집계·환경·소스/PDF 해시·미실행 범위를 저장했다. 원본 DB/쿠키/캡처/PDF와 실패 로그는 Git에서 제외한다.
- 이전60분 결과는 현 API 소스(715de660777846f42f235f39c8dabc859d03e56b9cfed7c00a6fc9437305fec9)의 통과 증거가 아니다. 공공 실키/기관 권리·현장 자료·기준 PC/실제 약10명 시범훈련은 미검증이다. 전체 목표와 기관 정규 출시는 완료 처리하지 않는다.

## 2026-11-17 모델·사진·IFC 최종 회귀

모든 입력은 합성이다. 자산/공공자료 브라우저는127.0.0.1:8011의 MockTransport/FixtureScanner만 사용하며 실제 공공 API/AV와 구분한다. 현재 API SHA256은 `49dcd590af46c71990dee0a71ec0e19e880b762aa997d8a8d18e9c7efc3a289f`다.

| 실행 | 실제 결과 | 범위/근거 |
|---|---|---|
| API·단위·통합·보안 | **192 통과 / JUnit36.464초** | pytest-assets-current.xml, 실제 고정 IFC 도구 시험 포함. 콘솔36.50초 |
| 재현 bundle.json IFC 집중 | **10 통과 / 1.04초** | 합성 IFC 실제 변환3층/3노드/36tri·경계·Windows 시간/출력 제한 |
| Chromium 최종 첫 시도 | **6 통과 / 2 실패 / 117.345초** | browser-assets-chromium-initial-failed.xml 보존. 초기 데이터/패널 open 상태 가정 수정 |
| Chromium 전체 재실행 | **8 통과 / 121.395초** | browser-assets-final-chromium.xml |
| Firefox 전체 | **8 통과 / 157.796초** | browser-assets-final-firefox.xml |
| Vitest | **4파일·15 통과 / 393ms** | 공유 좌표/스케일/회전3개 추가. API192와 별도 |
| 타입검사/Vite | **통과** | 기본375.17KB/gzip115.58KB, 지연 asset-runtime650.88KB/gzip169.58KB. 큰 청크 경고 유지 |
| 패키지/정적 확인 | **pip check·컴파일·npm audit 통과** | npm 발견0, Python37개 공식 PyPI 권고 조회 실패0/권고0. 해당 시점 알려진 정보에 한함 |
| 계약·합성 예시 | **8개 해시·예시4개·원본/사본 일치** | 자산 provenance JSON Schema/OpenAPI 포함. 원본 plan 미수정 |
| 자산 AAR PDF | **3쪽 전부 렌더링/직접 시각 확인** | PyMuPDF1.27.2.3. 한글·표·권리/제작자·층 매핑·해시·워터마크·쪽번호, 경계 밖 텍스트0/비공개 메모 없음 |
| 현 버전12접속60분 | **진행 중, 통과 미기록** | 2026-11-17T01:55:50Z 시작, artifacts/perf/soak-assets-final-stable.json. 이전 소스 결과 재사용 금지 |

두 엔진 각8개는 기존6개 전과정·공공자료1개·자산1개다. 자산 사례는 업로드/미리보기·단위1.25/회전25도/위치8m·층/객체 매핑·3객체→2객체·뷰 변경 시 모델 재요청 없음·비공개 참고사진/공용404·공개 외벽사진200·390px·AAR 출처/메모 제외를 확인한다. 양쪽 실제 렌더링 캡처에서 위쪽 빨강/아래 파랑/좌상단 노랑 색상표 방향을 확인했다. 비공개 검토 메모를 숨기기 위해 권한을 완화하지 않았다.

선택적 IFC 시험은 `RUN_IFC_TOOL_TESTS=1`이며 실제 고정 도구를 별도 준비해야 한다. 기본 Pytest는 선택적 브라우저8개와 실제 IFC1개를 건너뛴다. Windows Job 제한 시험은 Windows에서만 실행한다. 현재 경고1개는 Starlette의 httpx TestClient 사용 중단 예정 안내이며 실패/보안 인증으로 재해석하지 않는다.

```powershell
python -m scripts.run_external_fixture
# 별도 셸
$env:STUDIO_BROWSER_BASE='http://127.0.0.1:8011'
$env:RUN_BROWSER_TESTS='1'
$env:RUN_EXTERNAL_BROWSER_TESTS='1'
$env:RUN_ASSET_BROWSER_TESTS='1'
$env:BROWSER_ENGINE='chromium'
python -m pytest tests/e2e -q
$env:BROWSER_ENGINE='firefox'
python -m pytest tests/e2e -q
```

`docs/evidence/assets-20261117.json`은 현 소스/JUnit/PDF/환경 해시와 실패 이력을 기록한다. 60분 시험은 완료 뒤 별도로 검증/발행한다. 실제 AV·실기관 자료/권리·오프라인 네트워크·실키·전문가/기준 PC·약10명 시범훈련은 미실행이다.

## 전체 감사 후 진행자/화면·영상 진행

- 영상 이전 전체194/JUnit39.599초. 사건 연기/건너뛰기의 원자성/멱등·사유/유출, 증거 발행 실패 시 기존 결과 보존을 추가했다.
- 최종 일반 흐름 각9건: Chromium141.098초·Firefox184.72초 통과.3D 너비/높이·고정/원위치·공개 전 미리보기·연기/건너뛰기·390px 포함. Firefox 최초8통과/1실패는 큰 뷰포트에서 End 키 노출 문제였고 Home/End 수정 후 집중1건9.39초·전체9건을 재실행했다. 파일 browser-review-firefox-initial-failed.xml을 보존한다.
- 별도 SDK 오류 각3건: Chromium17.012초·Firefox28.147초.8012의 가상키 전용 빌드에서 SDK 네트워크 실패/7초 시간초과/로드뷰 없음 응답을 로컬 주입한다. 실제 공급자에 전송하지 않았고 실제 SDK/키 수용시험을 대신하지 않는다. 최초3실패(잘못된 state_version envelope)는 별도 JUnit 보존 후 수정했다.
- 증거 docs/evidence/console-review-20261117.json은 영상 이전 API SHA49dcd590…와 당시 소스/실패/해시/환경을 기록한다. 현재 영상 API에 재사용하지 않는다.
- 1887.81초/12접속/135명령/오류0 부하는 영상 서버 변경 전 중단했다. artifacts/perf/soak-assets-before-media-incomplete.json이며 complete/passed=false다.60분 통과로 집계하지 않는다.
- 영상 native/계약9건은 실제 고정 FFmpeg9.0.2·합성 MP4로 정상 변환·메타데이터 제거/크기 유지·기본 차단·해시/범위/권한 게이트를 검증했다. 초기에 검토자 누락 fixture로1건 실패한 기록을 보존했다. 실제 AV 아님.
- 영상 통합3건: 합성 처리/AV 프로토콜, 도구 미설정 격리, 공개 전 DTO/바이트/WS 차단→공개 원자 cue→정지/되돌림 차단, PRIVATE 수신자 허용/다른 역할404, 복제 cue/승인 초기화. 실제 재생/디코딩을 이3건으로 주장하지 않는다.
- 영상 추가 후 전체206건은42.10초 통과(artifacts/tests/pytest-media-current.xml). 이후 도구 설정 예외 보완의 집중12건은3.46초 통과(artifacts/tests/media-contract-and-workflow.xml). 웹15건/타입·빌드는 통과했으나 새 영상 UI/동기 재생의 실제 브라우저와 최종60분은 미실행이다.

고정 영상 도구를 준비한 경우 RUN_MEDIA_TOOL_TESTS=1로 합성 네이티브 시험을 명시 실행한다. 기본 테스트는 실제 도구 시험을 건너뛴다. 영상 매니페스트/동기/권리·콘텐츠 계약은 MEDIA_TIMELINE을 따른다.

추가로 업로드/재검사 대기4개·검사2개를 제한했다. 차단된 합성 검사기에서5개 동시 요청 중1개가 즉시429/Retry-After2, 나머지4개만 검사/저장된 것을 확인했다. 관련 자산/영상19건은7.45초 통과했다(artifacts/tests/media-asset-queue-regression.xml). 전체206건 실행 뒤 추가한 안전 보완으로, 최종 전체 결과와 합산/혼동하지 않는다.

### 영상 실제 재생과 시계 보정 단계

- 시계 보정 전 전체207건41.10초(artifacts/tests/pytest-media-final-candidate.xml). 실제 브라우저의 디코딩/재생/출처/공개 전 차단은 진행됐으나 두 화면의 목표 훈련시계가 약0.8초 달라 전체 영상 흐름이 실패했다. media-browser-chromium-initial/second/third/clockfix/diagnostic/clock-diagnostic2.xml과 실제 JSON 표본을 보존한다. CSP eval 실패를 시험 폴링으로 보완했으며 보안 정책/허용 오차를 완화하지 않았다.
- 시계 보정 후 집중7건2.47초(clock-media-focused.xml), 전체209건41.74초(pytest-clock-final-candidate.xml) 통과. RUN_IFC_TOOL_TESTS=1/RUN_MEDIA_TOOL_TESTS=1로 실제 합성 네이티브 시험을 포함했다. 웹22·타입/빌드 통과. deprecation 경고1·650.88kB 지연 번들 크기 경고는 남아 있다.
- 인증된 시각 API는 비로그인401, 최소 DTO/no-store와 가명 각 역할 허용, 투영의 elapsed/clock_sampled_at 동일 시점, 서로 다른 브라우저 원점/전달 지연, 일시정지/과거 재생 정지, 보정 전 대안을 시험했다.
- 현재 실제 Chromium 수정본 재생 회귀는 실행 중이다. Firefox/영상 PDF/최종60분 결과는 아직 없다. 시계 수정 전526.29초·12접속·47명령·오류0 중단본은 미완료이며60분 통과로 발행하지 않는다.

수정 후 Chromium 실제 합성 영상 흐름1건38.710초 통과(media-browser-chromium-serverclock.xml). 수집/원본 디코드/영상 편집과 저장·공개 전 메타데이터/바이트 차단·공용 화면 실제 재생·정지/재개·재접속·되돌림live404·과거seq 승인영상·AAR 출처/클립·비공개 검토 메모 누출 없음까지 검증했다. 페이지 오류 배열은 빈 배열이다. 재접속 두 화면 표본은 순차 측정 지연을 보정한 차이0.006946초(artifacts/browser/chromium-media-clock-sample.json)로 기존0.6초 기준을 통과했다. 허용 오차를 늘리지 않았다. 이는 합성 AV·로컬 브라우저 검증이며 실제 AV/실제 영상·기관 LAN 보증이 아니다. 최종 소스60분(soak-media-clock-final.json)과 Firefox 전체10건을 시작했으며 아직 미완료다.

후속 결과: 영상 시계 버전 일반 Chromium10건194.49초·Firefox10건225.81초 통과. 영상 PDF3쪽의 필수 텍스트/비공개 메모 부재/페이지 밖 텍스트 부재 및 모든 페이지 직접 시각 검토 완료다. docs/evidence/video-timeline-20261117.json은 당시 API324dbee0… 한정이다. 그60분 시도는 상세 생성기 보완 전402.63초·39명령·오류0에서 중단했다. passed/complete=false이며 최종 시험이 아니다.

## 상세 가상 대상물 생성기 검증

GENERATOR_CONTRACT에 추가 범위를 먼저 명시했다.7개 계약 단위·1개 발행/원자 상태/되돌림/재생/백업복구 통합을 더한 전체217개42.49초 통과(artifacts/tests/pytest-generator-current.xml). 웹29개·타입/빌드도 통과했다. GPU 없는 순수 기하 시험에서 음수층 윤곽/높이·상위층 숨김·절개·계단/구역 ID와 상태 연출을 검증했다. ZIP은 표준 CRC32 벡터/중앙 디렉터리 위치·경로/중복/예산을 검사한다.

실제 생성기 흐름은 Chromium1개13.30초(generator-browser-chromium-second.xml)·Firefox1개17.39초(generator-browser-firefox.xml) 통과했다.10개 프리셋→지붕/지하/층 윤곽→방화구획·계단→건물/구역 복제→저장→ZIP 실제 다운로드→Python ZIP/해시/기존 GLB 검사→리허설/발행→지하 절개를 확인했다. 한 Chromium GLB는3704삼각형·306객체·최저Y=-4.50000004m다. 실제 AV 검증은 포함하지 않는다. 최초 선택자 오류와 통합 시험 Idempotency-Key 누락428을 보존했다.

이후 주변 자원 GUI/공유 생성 기하와 초기 상태 안전 제한을 더했다. 상태 제한 후 첫 전체는225통과/1실패이며 실패는 추가 시험의 code/gate 키 오류다. 수정 뒤 초기/패치 악성 범위·변조 게이트/생성기 집중16개0.06초 통과(generator-state-limit-focused-fixed.xml). **현재 전체/두 엔진/최종60분 재검증 전이며 통과로 기록하지 않는다.** 스키마2의 JSON 계약 기본값을 확장했고 새 DB 테이블/마이그레이션은 필요하지 않다. 구코드로 내려갈 때는 새 필드/종류가 없는 변경 전 백업을 함께 복원한다.

후속 최종 후보: 전체226개43.69초(pytest-generator-final-candidate.xml), 공유 기하/지도 범위와 스냅샷 순서까지 웹34개·타입/빌드 통과. 주변 자원/안전 제한 포함 Chromium11개209.21초(browser-generator-final-chromium.xml)는 수신 순서 보완 전의 결과다. 이후 보완은 웹에만 적용했고, REST 지연/최신 WS 이후 응답·DOM 버전 감시를 넣은 집중 Chromium1개14.79초(generator-browser-snapshot-order-chromium.xml)가 통과했다. 지연 주입의 보완 전 표본도 통과했으므로 실제 역행 오류 재현 증거로 주장하지 않는다.

현재 API498c8674… 소스의60분 시험(artifacts/perf/soak-generator-final.json)은 실행 중이고 미완료다. 최신 웹 전체 두 엔진11개와 SDK 오류 각3개·현 장면 표본을 이어서 검증한다. 이전 단계의 통과를 새 웹 전체 결과로 합산/대체하지 않는다.

### 화면·인쇄 감사 후 추가 보완

수신 순서 포함 전체11개는 Chromium201.22초·Firefox226.49초 통과했다. 별도 합성 지도 오류 각3개는16.41/28.29초 통과다. 실제 SDK/실키를 시험한 것이 아니며8012는 시험 후 종료했다. 원본/사본·8개 계약/예시 해시와4예제 모델도 확인했다.

PDF 직접 검사에서 내부 사건명이 남은 것을 발견해4종 명칭을 보완했다. 첫 추가 Chromium은1통과/1실패(잘못된 fixture envelope422), 두 번째는1통과/1실패(실제 재생 제목의 raw kind 대안)를 보존했다. 후자는 App의 제목 대안을 바로잡았고 최종 회귀로 재검사한다. 현재 출력 PDF는 마지막 검수 전까지 전달 완료로 표시하지 않는다.

신규 환경 요약 시험은 수정 전1실패/1통과였다(state-summary-before-environment-fix.json). 수정 후 웹36·타입/빌드 통과. Chromium 환경 집중1건13.63초는 실제3D와 강제2D에서 비공개 강우/바람/정전 주석이 직원에게 보이고 공동 경로에서는 숨겨지는 것을 확인했다. 실행본 없는 미리보기의 캔버스 동일성과 환경 사례를 포함해 전체 브라우저 대상은 이제12개다. **이12개 최종 전체와60분은 아직 완료 전이다.**

후속 결과: Chromium12개217.60초 통과. 출입구/자유 윤곽 둘레·층수/현재 연기 효과의 장면 예산 보완 규칙3개를 더해 웹39개·타입/빌드 통과다. 실제16000출입구→WebGL 생성 전2D를 더한 전체13개는 Chromium219.80초 통과했다. AAR PDF3쪽 전부 직접 확인했고 내부 코드명이 한글로 바뀐 것을 확인했다.

Firefox 최초13개는11통과/2실패248.31초다. 실패는 실제사진 준비 전 naturalWidth=0과2D End 직후 항목 노출이었다. 사진은 같은64px 조건을 재시도하며 End는 instant와 화면 교차비율1로 검증한다. 이전 결과는 browser-firefox-photo-and-end-initial-failed.xml에 보존했다. 현재 보완 후 Firefox13개 재검증과 소스498c8674…의60분을 계속한다. 아직 최종 통과로 발행하지 않는다.

후속 Firefox는12통과/1실패262.78초였다(browser-firefox-end-fractional-failed.xml).사진 디코딩 조건은 통과했다. End 키의 마지막 항목 하단1050.14998px이1050px 화면에서 약0.15px 잘려 교차비율0.9972527이었던 것을 진단했다.4px scroll-margin을 적용한 집중 Firefox1개15.73초(environment-end-margin-firefox.xml)·웹39개/타입/빌드는 통과했다. 전체13개는 다시 실행 중이며 비율1 기준은 유지한다.

고정 API498c8674…의 장시간 시험은3600.60초/12가상 접속/246명령/오류0으로 실제 완료했다(artifacts/perf/soak-generator-final.json).최종 버전은12접속 모두247, p95동기0.378초/최대0.503초다. 스크립트의 연속 시퀀스/중복·누락/최종 장면·권한 유출·소스 동일 검사를 통과해 complete/passed=true다. 로컬 HTTP/WS 합성 시험이며 기관 기준 PC·GPU·실제 회의실 시범훈련은 미실행이다.

## 2026-11-17 14:10 KST 최종 로컬 고정본 검증

버전 증거: [최종 상세 생성기·영상/환경 검증](evidence/generator-final-20261117.json). 원본 plan/사본 SHAcae4e3a6…와 API SHA498c8674…를 확인했다. 원본 계획/법령 역할을 변경하지 않았다.

| 시험 | 최종 실제 결과 | 원시 근거 |
|---|---|---|
| API·단위·통합·보안·복구 |226통과/JUnit43.655초, skip0 |pytest-generator-final-candidate.xml |
| 웹 규칙·타입·빌드 |39통과/실패0·TypeScript/Vite 통과 |web-final-current.json·빌드 출력 |
| Chromium 전체 |13통과/227.314초·skip0 |browser-final-current-chromium.xml |
| Firefox 전체 |13통과/261.09초·skip0 |browser-final-current-firefox.xml |
| 모의 지도 SDK 장애 |각3통과/15.714·26.782초 |map-final-current-chromium/firefox.xml |
| 장시간12접속 |3600.60초/246명령/오류0·최종247전원 일치 |soak-generator-final.json |
| 영상 출처 AAR PDF |3쪽 전부 렌더링/직접 시각 확인 |pdf-visual-review.json·PDF SHA1cc21e63… |
| 기본 로컬8010 |UI로그인·장면·종료된247실행본·스키마2/페이지 오류0 |main-handoff-smoke.json |
| 로컬 장면 표본 |UI자동로그인 포함4.151초·표시FPS중앙38/10표본·2D 전환 없음 |scene-probe.json |
| 계약/예시/원본 |8파일 해시·4예제 모델·역할 원본·AC38행·plan사본 일치 |release-contract-check.json |
| 백업→새 파일 복원 |스키마[1,2]·무결성·SHA cf577a64… 일치 |runtime의manifest만, DB바이트 증거 제외 |

브라우저13개 실제 이름을6개 시험 모듈의 AST와 정확히 대조했고 누락/중복/skip이 없다. 원시 XML/JSON/캡처는 artifacts에, 검토용 집계/소스 지문은 docs/evidence에 보존했다. 전체13개와 추가 지도3개를 서로 다른 검증 범위로 기록하며 과거 재시도를 기능 개수로 합산하지 않는다.

Firefox 최종 수정은4px scroll-margin이며 화면 교차비율1을 유지했다. 최종 마지막 항목 bottom1046.15px/화면1050px이다. 수정 전11/2·12/1 실패 JUnit과 관찰된 실패 경계 추출 요약은 보존했다. 사진은 동일64px 조건의 디코딩 완료 대기이며 검증 기준을 낮추지 않았다.

합성 AV응답/공공자료·모의SDK와 실제 고정 IFC/FFmpeg 도구 처리를 구분한다. 실AV/실키/실시설·기관 권리/보안/정밀도/전문가 승인·기준 PC/프로젝터·약10명 실제 회의실 시범훈련은 미실행이다. SwiftShader 표본/loopback12접속을 기관 수용 성능으로 주장하지 않는다. Three585.56kB 경고와 Starlette/httpx 사용 중단 예정 경고는 추적한다.211개 비무시 소스의 제한된 키패턴/런타임파일 검사 발견0은 완전한 보안 인증이 아니다.

### 현 전체 브라우저 재현

먼저 별도 터미널에서 합성전용 `python -m scripts.run_external_fixture`를 실행한다. 실제 AV/기관 자료를 검증하는 서버가 아니며 시험 후 종료한다. 고정 도구 준비는 ASSET_PIPELINE/MEDIA_TIMELINE을 따른다.

```powershell
$env:STUDIO_BROWSER_BASE='http://127.0.0.1:8011'
$env:RUN_BROWSER_TESTS='1'
$env:RUN_EXTERNAL_BROWSER_TESTS='1'
$env:RUN_ASSET_BROWSER_TESTS='1'
$env:RUN_MEDIA_BROWSER_TESTS='1'
$env:RUN_GENERATOR_BROWSER_TESTS='1'
$env:RUN_ENVIRONMENT_BROWSER_TESTS='1'
$env:BROWSER_ENGINE='chromium'
python -m pytest tests/e2e/test_browser.py tests/e2e/test_external_browser.py tests/e2e/test_asset_browser.py tests/e2e/test_media_browser.py tests/e2e/test_generator_browser.py tests/e2e/test_environment_browser.py -q
$env:BROWSER_ENGINE='firefox'
python -m pytest tests/e2e/test_browser.py tests/e2e/test_external_browser.py tests/e2e/test_asset_browser.py tests/e2e/test_media_browser.py tests/e2e/test_generator_browser.py tests/e2e/test_environment_browser.py -q
```

지도 장애3개는 별도8012/가상 공개키 빌드와 RUN_MAP_BROWSER_TESTS=1에서 실행한다. 모든 외부 요청은 로컬 차단/대체한다. 운영 빌드에 QA 키/승인 플래그를 섞지 않는다. 현재8011/8012는 종료하고 기본8010만 유지했다.

### 2026-11-17 14:12 KST CI Python 권고 조회 연결

기존 Python 의존성 조회를 .github/workflows/verify.yml에 추가했다. PyYAML BaseLoader로 구문을 파싱하고 contents:read·의존성 설치 이후 정확히1회 실행을 확인했다. 실제 로컬 명령 `python scripts/audit_python_dependencies.py --output artifacts/python-advisories-final-ci-20261117.json`은37개 조회/실패0/알려진 권고0/종료0이다. [CI 보완 증거](evidence/ci-audit-20261117.json)를 기록했다. 원격 CI는 미실행이며 완전한 취약점 부재/기관 보안 인증을 뜻하지 않는다. 제품 API/웹/시험/스크립트의 기존 지문을 모두 대조해 동일함을 확인했고 기능 시험은 반복하지 않았다.

### 2026-11-17 16:56 KST 최초 Git 게시 전 검증

.gitattributes의 원바이트 보존 아래215개 인덱스 파일/작업 파일 Git blob을 전부 대조해 일치했다. 금지 경로·제한된 키패턴0, plan사본/기존 소스 SHA 동일이다. CRLF를 인식한 diff --check의 유일한 기존 문제는 application.py839의 빈 EOF로 기록하며 코드 바이트는 바꾸지 않았다. 공식 actions3종v7 태그를 원격에서 확인했다. 제품 변경 없이 Git/배포 문서만 추가했으므로 이미 통과한 기능 시험을 반복하지 않는다. 호스팅 실행 환경의 새 기능/권한 시험은 별도 필요하다.

원격 CI 최초 실제 실행44042619512: 설치/타입/빌드 성공, Pytest137통과/19skip/86오류(부모 runtime 폴더 부재), 이후4개 단계 skip. 첫 실패를 보존하고 CI 부모 폴더 생성 뒤 동일 전체 재시험한다. 원격 기준이므로 로컬226개와 합산하지 않는다.

수정 후 원격 CI44042858035/0437ecf855abaf5f2f160a70db0c26eed0092415는 전체 success다. Pytest223통과/19skip/24.78초·웹39·타입/빌드·인벤토리·Python37조회 실패0/알려진 권고0·npm audit0을 실제 로그에서 확인했다. 최초 실패와 수정 후 성공을 모두 보존한다. 이 CI는 현재 Python 구성의 검증이며 정적 전체 기능 전환판의 통과는 아니다.

설치형 실행기 최초 시험2통과/2실패→SPA 상태 경로 수정/201 기대값 교정 후4통과3.83초. Python 경로 없는 실제 독립.exe에서 schema2/홈200/로그인/합성 훈련201을 확인했다. 이는 Python3.14.3의 최초 QA 후보이며 최종 설치/업데이트/백업/GUI/배포·Python3.14.10 빌더 검증은 아직 남았다.7개 실제 후보 브라우저 흐름 실행 중이다.

설치형 후속: 신선한 DB의 과거 실행본 fixture를 강화한 실제 후보 Chromium7개115.35초 통과. SQLite 연결 닫기 수정/손상 백업/자동 이전 기록/복원 실패 주입 롤백7개11.28초 통과. 전체 서버232개117.56초·웹39·타입/빌드 통과. 설치형 공개 지도 설정 추가8개13.91초 통과이며 새 Windows 빌더/최종 설치물 검증은 별도로 이어간다.


### Windows 설치형 실제 수용 시험 (2026-11-17 18:18 KST)

최종 빌드bd78c0e/Windows 실행44050912074 success. 249수집/231통과/18skip/실패0이며 독립 frozen 실행기 자체 검사도 성공했다. 배포된 정확한 파일을 Windows11 Pro26300에 설치해 동일784개 payload 해시·한글 제어 창·Python 없는 PATH·schema2/로그인/훈련 생성·재시작/백업/복원·종료 권한 거절을 확인했다. 설치본 Chromium7개107.54초/Firefox7개130.66초, 지도 합성 장애 각3개15.04/26.72초 통과. 동일 버전 재설치·제거·제거 후 재설치에서 훈련13개와 설정/백업을 보존했다. 다른 버전 업그레이드, Windows10, 실제 AV·기관 승인·약10명 실제 회의실 실증은 미실행이다. Authenticode는NotSigned이며 다운로드와 SHA256을 안내한다.

최종 공개 URL의31,535,358바이트를 다시 받아 SHA256393d7c9e21fd454af9940652b57bdc219773d75541b92714c0fa76df6ced993d 일치를 확인했다. 정적 사이트1440/390px×두 엔진의 링크·체크섬·키보드·가로 넘침·6개 잘못된 배포 메타데이터 거절을 확인했고 페이지 오류/외부 런타임 요청0이다. 첫 부정 fixture의 callback이 Playwright Request를 JSON 값으로 받은 TypeError는 시험 코드 문제로 기록하고 시그니처를 고친 후 전체 재실행했다. 원시 artifacts/download-site, 요약 docs/evidence/windows-release-20261117.json. 이후 Site source235586e9/버전1/배포appgdep_6afc1c1b2c908191bb94f5185d7079ee가18:19:36 KST에 succeeded로 종료됐다. 소유자 전용 접근을 유지하며 공개 설치파일은 GitHub에서 제공한다.

실제 호스팅 후에는 비인증401/소유자 읽기 접근200과 공개 웹자원5개 SHA256 일치를 확인했다. HTML은 서비스가 추가한 관찰된 Cloudflare challenge1개를 제외한 원본 바이트가 일치했다. 사이트의 보안 스크립트/인증은 수정하지 않았다. 자격증명은 증거/소스/파일에 포함하지 않는다.


### U27 GitHub Pages 수용 계약

Pages workflow/main 전용·최소 권한·site/dist만 게시, 공개 HTTPS/로그인 불필요, 프로젝트 하위 경로의 상대 CSS/JS/이미지/배포 JSON·정확한 설치파일 링크/SHA256, 두 엔진1440/390px·키보드·오류/가로 넘침·잘못된 배포 메타데이터 거절을 확인한다. 빌드7개 파일과 원본 자원 바이트·YAML/권한/컴파일은 확인했다. 이후2902bb8/Pages 실행44074688598과 소스 전체CI44074688551이 success로 종료됐다. 실제 공개 HTTPS 사이트에서 Chromium/Firefox×1440/390px의 링크·SHA·키보드/복사·넘침 검증4개와 잘못된 메타데이터 거절6개, JS오류0/외부 런타임 요청0을 확인했다. 두 실제 화면을 직접 시각 확인했고 자원7개 모두 빌드 SHA와 일치했다. 설치파일 HEAD200/31,535,358바이트이며 원본 plan/사본 SHA는 같다. [GitHub Pages 증거](evidence/github-pages-20261117.json).


### 웹 전용판 기반 및 Git 보안 업데이트

web 타입검사/프로덕션 빌드와 기존 웹39개/타입·빌드를 통과했다. 기존 의존성 버전·integrity는 바뀌지 않았고 workspace 링크/선언26줄만 lock에 추가했다. 최초 bootstrap은 존재하지 않는 선택적 @types/node를 가정한 KeyError였으며 Node 전역을 쓰지 않는 설정으로 수정했다. 첫 두 브라우저 부팅은 새8015 Origin이 합성 서버 허용 목록에 없어403으로 실패했다. 해당 QA 서버에 정확한8015 Origin만 설정하고 다른 Origin403 검증을 더해 Chromium/Firefox 기본2개를 재검증했다. 최초 실패 JUnit을 별도 보존했다. 이는 공통 UI 개발 기반 시험이며 저장 어댑터·기관 계정·전체 웹 운영/공개 배포 시험은 아직 아니다.

Git2.56.1의 공식 GitHub 자산 SHA256/유효 Authenticode를 확인 후 실제 업데이트·버전/저장소HEAD·인증 도우미 설정 보존과 원격 main 조회를 확인했다. npm audit취약점0, Python37조회 실패0/알려진 권고0. 전체 기관 보안 인증을 뜻하지 않는다. 실제 결과는 evidence/git-security-update-20261117.json 및 web-workspace-baseline-20261117.json을 따른다.

워크스페이스 CI44077535545: 빌드/서버/웹시험은 통과, 목록 생성 KeyError로 전체 실패. 이후 보안 단계는skip이다. 링크/미정 버전/범위 밖/순환 메타데이터5개0.07초 통과 후 목록157JS/19Python·고지144개 생성 성공. 실패와 후속 원격 결과는 구분한다.


### 2026-11-18 U30 투트랙 수용 시험 결과

- 웹서버 web/server.py가 별도 web/dist와 API/WS를 같은 출처에서 제공한다. 운영 HTTPS/기관 계정·허용 Host/Origin·보안 쿠키를 적용하고 기본 데모는 loopback만 허용한다. 서버 설정 server.json과 공통 실행 설정 settings.json은 버전1·엄격 검증·원자 교체·이전 유효본 보존이다. Windows0.1 settings.env는 허용 항목만 최초 이관하고 원본을 보존한다. 데이터 폴더의 공용 정적 자원 배치는 거절한다.
- 훈련 제작 화면에 설정 JSON 저장/미리보기/새 편집본 불러오기를 연결했다. 체크섬·2MB·중복 키·유한값·스키마·기관/역할을 검증한다. 같은 멱등키 동시8회는 훈련1개/감사1개만 기록한다. 가져오기에서 숙지·검수·발행·기관 승인·자산/영상 연결을 초기화한다. 기존 기록을 덮어쓰지 않는다.
- 최초 웹 생성 시험에서 운영 COOKIE_SECURE가 다른 로컬 인스턴스 환경에 남아 HTTP 로그인401이 발생했다(11통과/12실패). 공유 RLock과 환경 스냅샷/복원으로 고치고 JSON·웹·설치형41개를 통과했다. 병행 인스턴스가 임시 DATABASE_URL을 잘못 읽지 않는 회귀도 추가했다. 중복 계정 CLI의 SQL 예외에 암호 해시가 포함될 가능성을 확인해 일반 오류로 바꾸고 비노출 시험을 통과했다.
- 전체 Pytest295수집/276통과/19선택 시험skip/실패0,58.953초(dual-track-full-api-first.xml). 웹39개·타입/루트 빌드/별도 web 빌드 모두 통과했다. Three585.56kB 지연 청크 경고는 유지하며 실제 기준 PC 성능 승인으로 확대하지 않는다.
- 실제 웹서버8016·격리 합성 DB에서 Chromium8개122.37초/Firefox8개163.42초를 통과했다. JSON 편집 저장·파일 다운로드·미리보기·새 편집본·손상 거절과 기존10사건/보고/인계/AAR/공용 격리/모바일 흐름을 포함한다. 웹/로컬 표시 보완 뒤 마지막 JSON 집중시험은 Chromium1개4.00초·Firefox1개8.14초 통과했다. 첫 표시 시험은 존재하지 않는 .app-header 선택자를 쓴1실패였고 실제 로그인 화면의 웹서버판 표시로 바로잡았다. 실패 파일은 보존했다.
- 서버 ZIP을 새 디렉터리에 풀어 Node/PYTHONPATH 없이 실행·JSON 지속·백업·서버 실행 중 복원 거절·중지 후 복원/재시작을 실제 검증했다(artifacts/web-server-extracted-qa.json). 이 후보는 source_dirty=true로 발행하지 않는다. 깨끗한 커밋의 서버 ZIP/Windows0.2와 실제0.1→0.2 업그레이드·컨테이너 CI는 후속 검증이다. 로컬 Docker는 없어 실행했다고 기록하지 않는다.
- 원본 plan/사본 바이트 동일. 별도 웹서버 패키지·Docker/HTTPS Compose·계정/백업/업데이트 문서를 준비했다. 실제 공개 서버/도메인 미제공이므로 Pages를 실행 웹앱으로 표시하지 않는다. 이전 workspace 수정 커밋c62b388/원격 CI44078012351은 success다.


### 2026-11-18 0.2 최종 산출물 수용·공개

- Windows 빌더44212338188/source18a7d3a는276통과/19skip·Python3.14.10·frozen PNG/XLSX/재시작/백업복원 성공이다. 실제 Windows11에서 설치된784파일/67,135,337바이트를 매니페스트와 전부 대조했다. 실제0.1→0.2 업그레이드에서 훈련/기존 settings.env 바이트/JSON 이관/백업을 보존했고, 웹→로컬·로컬→웹 JSON 새 편집본 가져오기를 확인했다. PATH에 Python/Node가 없었다.
- 실제 최종 설치판 Chromium8개120.15초/Firefox8개155.96초 통과. JSON 실행 설정으로 가상 공개키를 주입한 별도 지도 QA에서 네트워크/시간초과/로드뷰 없음 각3개17.19/29.91초 통과했다. 외부 제공자 통신은 차단/합성했으며 실제 승인·실키를 주장하지 않는다. 같은 버전 재설치/제거/제거 후 재설치에서19개 합성 훈련과 settings.json/기존 env/백업을 보존했고 최종 QA 앱 파일은 제거했다. 다른 실제 사용자 설치/기본 데이터는 건드리지 않았다.
- 수정 후 Linux CI44212776714/source3aefa7d는281통과/20skip·웹39·두 웹 빌드·Python37조회 실패0/알려진 권고0·기한 제한 JS 개발 권고 평가·서버 ZIP 생성/실제 추출 검증 전체 success다. 컨테이너44212776675는 비루트/읽기전용·Host/계정 격리·JSON 재시작과 Trivy0.76.2 수정 가능한High/Critical0을 통과했다. 최초 실패를 숨기거나 ignore로 없애지 않았다.
- 정확한 CI 서버 ZIP을 Windows에서도133자원 해시 검증 후 Python만으로 실행·재시작·백업/중지 후 복원·실행 중 복원 거절을 확인했다. 이 최종 패키지의 Chromium8개118.44초/Firefox8개152.07초 통과. JSON 미리보기390px도 두 엔진 가로 넘침/JS오류0이다.
- GitHub 아티팩트의 Windows ZIP 수신이 지연돼 GitHub 커넥터의 같은 artifact14386657440을 받았다. Node fetch는 실패로 기록하고 Windows 신뢰 저장소의 숨김 stdin URL 수신을 사용했다. 서명 URL/키는 Git/증거/파일에 저장하지 않았다. 완료 후 지연된 자기 GH 다운로드 프로세스만 중지했다.
- v0.2.0을 초안으로 올려 수용 후10:13:40 KST 공개 prerelease로 발행했다. Windows31,547,397바이트/SHA2565a6415205fccbf3c203e8340744e1d81c49cc99d0f1c9f151a472ab93de6a1cd, 서버724,857바이트/SHA25626ea88b5aa8e5c03327f1a24c551acfe916a97a5e7e8a0f950d6c9fe92f27f05가 GitHub 자산 digest 및 인증 없는 재다운로드와 모두 같다. 전자서명NotSigned·실제AV/기관검수/실제시범 미실행은 유지한다.
- 안내 사이트를 두 방식의 다운로드·JSON·서버 설치/실제 주소 구분으로 갱신했다. 로컬 두 엔진1440/390px4회·잘못된 메타데이터6종×두 엔진12회 거절·JS/외부런타임요청0이며 모바일 화면을 직접 확인했다. Windows에 Node가 포함된다는 잘못된 초안 문구를 Python 런타임/웹 화면 포함으로 고쳤다. 실제 Pages 반영/해시는 후속 확인한다.


### 2026-11-18 공개 Pages 최종 확인

- Pages44214302290/source0dfd03c success. 공개 HTTPS 실제 주소에서 Chromium/Firefox×1440/390px4회·메타데이터6종×두 엔진12회 거절·페이지 오류0/외부 런타임요청0을 확인했다. HTML/JS/CSS/releaseJSON/PNG/SVG/robots7개 모두 로컬 빌드 바이트 SHA와 일치한다. 서버/설치 파일 공개 재다운로드 SHA도 일치한다. 첫 검사 명령은 허용 목록과 다른 말미 '/'로 CLI가 실행 전 거절했으며 허용된 정확한 주소로 실행했다. 검사 범위를 넓히지 않았다.
- JSON 미리보기 모바일 화면과 실제 안내 모바일 화면을 직접 시각 확인했다. 안내 페이지에는 두 설치 방식·별도 공개 서버 필요·JSON과 전체 백업 차이를 표시했다. QA 웹8016/8017·지도8019·설치8018·정적8020은 종료했고 해당 프로세스 부재를 확인했다. 기존 개발8010은 변경하지 않았다.
- 현재 사용자 요청의 웹서버/로컬 구현·JSON·배포 패키지·공개 다운로드 작업은 완료다. 실제 공개 훈련 서버/도메인 정보는 미제공이므로 임의 유료 서버나 허위 운영 주소를 만들지 않는다. 기관 전문가 검수·실제AV·약10명 실제 회의실 시범훈련은 미실행이며 전체 기관 정규 출시 목표를 완료로 바꾸지 않는다.


SCREEN 수용 계약: schema/참조/60초·상태/멱등/CAS/권한·WS·미래/메모 유출·재시작/백업복원, 실제 Chromium/Firefox 60초 자동 변화·정지/4방면/공용·JSON/모바일·WebGL 실패 대안/자원 해제·추출 배포를 실행 후 기록한다. 전국 실사 데이터 미제공을 통과로 표시하지 않는다.


### 2026-11-18 SCREEN 구현·로컬 수용 중간 기록

- 밝은 대형3D/얇은 우측 메시지·A/B/C/D/지휘관·실시간 연기/불꽃/방수/차량/요구조자/지휘대/소화전·배치 편집·12사건/64카탈로그·JSON/회의 기록·공용 전용 투영을 구현했다. 최초 API11통과/1실패는 TestClient WS의 기본testserver Host 거절이었다. 실제 loopback WS URL로 fixture를 고친 뒤 기존 웹/설치형 관련 포함31개 통과했다.
- 첫 브라우저는 실행본 선택 UI가 실제로 추가되지 않아2실패/1통과였다. PowerShell 한글 here-string의 변환 때문에 치환이 적용되지 않은 점을 확인하고 UTF-8/일치 단언으로 바로잡았다. 실행본 생성 시각 정렬/명시 선택을 제공했다. 후속 실시간60초·장면/메시지·정지·4방면은 통과했으나 메모 저장 후 비활성 버튼에서 초점이 빠져 ESC가 전달되지 않는1실패/2통과가 남았다. 문서 캡처 ESC/대화상자 초점 복원으로 수정한 뒤 Chromium3개78.56초·Firefox3개85.53초를 통과했다. 실패 JUnit은 보존했다.
- WebGL 장면을 일관되게 유지하고 정적 도형 배칭·움직이는 부품/검수 모델 제외·정확한 정점 좌표 회귀·반복 그림자 계산 제한·동작 줄임·2D 대안·부하 기반 품질 조정을 구현했다. 배칭 시험 최초1실패/45통과는 보수적 AABB의 회전 오차를 정점 이동으로 오인한 시험이었다. 정확한 정점 경계로 고친 뒤46개 전체 통과했다. 이 PC의 headless표본13FPS→초기 자동 경량19FPS는 기관24fps 승인으로 기록하지 않는다. 최종 동적 해상도 결과는 별도 확인한다.
- 자료는 기본 격리·서버 기관/역할·검사기/구조·정규화본 재검사·이용권/모델·좌표 사람 검수 후 사용한다. 합성 CLEAN fixture의 실제 정규화/검수/공용 바인딩 정상과 미검사 자료 거절을 포함해6개 통과했다. 합성 검사기는 실제 AV/기관 승인으로 표시하지 않는다. 실제 전국 건물/실사 공급자 질문은 답변 대기다. 주소만으로 실제 실내·형상을 만들거나 외부 URL/로드뷰를 추출하지 않는다.
- 별도 프론트엔드 경로를 검사하기 전에 CLI가 공유 웹 경로 기준으로 JSON을 쓸 수 있던 위험을 사전 검토에서 발견했다. 실제 app frontend로 먼저 데이터 경로를 검증하고 --check도 해당 빌드를 확인하게 수정했다. 파일 생성이0건인 거절 회귀를 포함해32개 관련 시험 통과했다. 수동 공개/메모 직후의 복구 시계가 마지막 사건보다 뒤로 갈 수 있는 경우도 커밋 시계로 보완했다.
- 최초 통합 수집은 원래test_browser.py와 이름 충돌로 실행 전 실패했다. screen/tests를 패키지로 구분한 뒤 전체318수집/296통과/22선택skip56.14초, 웹46개·기존/새 웹3빌드가 통과했다. npm version/integrity는 기존과 모두 같고 own workspace만 추가했다. Python37권고조회 실패0/알려진 권고0, JS는 기존 단일 개발 권고5경로의 기한 제한 평가·운영0을 유지한다. 알려진 권고0으로 숨기지 않는다.
- source_dirty=true QA ZIP122자원 추출 해시·Node 없는 실제 실행·설정지속·재시작·실행 중 복원 거절/중지 후 복원은 통과했다. 깨끗한 커밋의 최종ZIP/컨테이너/실제 브라우저CI·국내실사 공급자 연계는 완료로 표시하지 않는다. 원본plan/사본은 동일하다.
