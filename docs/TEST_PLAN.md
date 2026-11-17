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
