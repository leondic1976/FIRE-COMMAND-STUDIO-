# FIRE-COMMAND STUDIO

임무 숙지 → 공동 상황판단 → 보고·조치 → 지휘결론 → 상황 변화 → 강평·재훈련을 연결하는 웹서버·PC 로컬 가상 재난지휘 훈련 스튜디오.

현재 제공물은 `plan.md`에 따른 로컬 합성 훈련 구현이다. 역할/공동훈련·상세 대상물 제작·공공자료/자산/영상·AAR를 구현하고 자동 검증했다. 기관 정규 훈련용 출시 승인은 받지 않았다. 실제 기관 SOP·명부·건물자료·회의실 실증은 제공되지 않았으며, 미실행 시험은 통과로 표시하지 않는다.

## SCREEN · 밝은 3D 현장 화면

루트 [screen/](screen/README.md)에 별도 웹 현장 연출 모듈을 추가했다. 큰 주간3D·작은 우측 상황 메시지·A/B/C/D·최소1분 사건·화재/요구조자/차량/지휘대/소화전 사전 배치·시나리오 JSON·회의 기록을 제공한다. [SCREEN0.1.0 패키지](https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/tag/screen-v0.1.0)를 내려받아 Python3.14에서 `python -m screen.server --data-dir runtime/screen`으로 실행한다(최초 의존성 설치는 screen/README 참고). 기본 주소는 **http://127.0.0.1:8090/** 다.

기본 현장은 자체 제작 가상 자료다. **전국 실제3D/실사 데이터·자동 지도 연계는 포함되지 않았으며 공급자/이용권 답변 대기**다. 승인된 GLB/방면 사진 연결 경로와 가상/근사/실제 라벨을 제공한다. 원격/로컬 두 엔진·60초 실제 진행·컨테이너·ZIP 추출/복구와 밝은 화면을 검증했다. [검증 범위](docs/evidence/screen-20261118.json). 기관 정규 훈련 승인·기준 PC/GPU·실제 회의실 수용을 대신하지 않는다.

## Windows 설치판

[Windows 설치 프로그램 다운로드](https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/tag/v0.2.0) · [GitHub Pages 다운로드·운영 안내](https://leondic1976.github.io/FIRE-COMMAND-STUDIO-/) · 로컬 훈련 시범판. Python·Node를 별도로 설치할 필요가 없습니다. 설치 후 바로가기를 실행하고 **훈련 스튜디오 열기**를 누르세요.

운영 PC 한 대에서 준비·대리 입력하고, **공용화면**을 프로젝터에 띄워 구두로 토론합니다. 데이터는 `%LOCALAPPDATA%\FIRECommandStudio`에 저장합니다. 전체 백업·복원과 제거 후 데이터 보존은 [설치·운영 안내](docs/WINDOWS_DISTRIBUTION.md)를 따릅니다. 전자서명은 적용하지 않았으며 릴리스의 SHA256으로 파일을 확인할 수 있습니다. 기관 정규 출시 승인과 실제 회의실 시범훈련은 별도입니다.

## 웹서버판과 JSON 설정

[웹서버 패키지 다운로드](https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/tag/v0.2.0). 관리자가 Python3.14 서버 또는 Docker/HTTPS로 설치하고 사용자는 브라우저로 접속합니다. 빌드된 화면이 포함돼 서버에 Node를 설치할 필요가 없습니다. 압축을 푼 폴더에서 다음을 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m web.server --data-dir runtime/web-server
```

기본 합성 데모는 서버 PC의 **http://127.0.0.1:8080/** 입니다. 공개 서버는 별도 도메인·HTTPS·기관 계정을 구성합니다. [웹서버 운영·백업·업데이트](docs/WEB_DEPLOYMENT.md)를 따르세요. GitHub Pages 주소는 다운로드 안내이며 공개 훈련 서버 주소가 아닙니다.

양쪽 방식은 같은 훈련 기능과 설정 JSON 형식을 사용합니다. 실행 설정은 비공개 settings.json, 웹서버 설정은 server.json에 저장합니다. 훈련 제작의 **설정 JSON 저장/불러오기**로 새 편집본을 이동하며 기존 기록·승인 상태를 덮어쓰지 않습니다. 전체 기록/첨부자료는 별도 DB 백업으로 보관합니다.

## 소스에서 실행

Node 24와 Python 3.14 환경에서 저장소 루트에서 실행한다.

```powershell
python -m pip install -r requirements.txt
npm.cmd ci
npm.cmd run build
npm.cmd run serve
```

접속: **http://127.0.0.1:8010**. 기본은 가상 데모 계정 선택 방식이다. 진행자·평가관·공동화면·참관자·가상 참가자 10명을 제공한다. 실제 성명·근무표·현장도면을 데모에 입력하지 않는다.

`.env.example`을 참고해 필요할 때 `.env`를 만든다. 실제 환경변수가 `.env`보다 우선한다. API는 `.env`를 읽으며, 공개 지도 런타임 설정은 서버 재시작 후 적용된다. `VITE_` 변수에는 공개용 지도 JavaScript 키만 허용하며, 공공 API·AI·DB 비밀값을 넣지 않는다.

웹 개발 서버는 별도 터미널에서 `npm.cmd run dev`로 실행할 수 있다. API 서버는 8010에 유지하며, Vite가 API와 WebSocket을 같은 출처로 프록시한다.

## 훈련 흐름

1. 진행자로 입장해 **훈련 제작** 12단계에서 조직·임무·가명 참석자·근무기간·대체자·대상물·사건을 정한다.
2. **임무 숙지**에서 역할별 카드 열람, 상황형 3문항, 업무 설명, 진행자 구두 확인을 기록한다. 읽음만으로 통과하지 않는다.
3. **검증·리허설·발행**에서 품질 검사와 모든 경로의 상태 패치 리허설을 실행한다. 승인 메모를 남겨 불변 버전을 발행하고 실행본을 만든다.
4. **훈련 상황판**에서 시작·사건 승인·보고·결정·일시정지·인계를 수행한다. 공용화면은 서버가 공개 정보만 반환하는 별도 경로를 사용한다.
5. **관찰·강평**에서 본인 행동 증거와 관찰을 연결하고 개선과제·책임 역할·목표일·재훈련·완료 증거를 기록한다. AAR는 JSON·Markdown·인쇄 미리보기로 제공한다.
6. 참가자는 **개인 임무연습**에서 AI·진행자 없이 모의 동료 보고와 사전 작성된 피드백으로 한 역할을 연습할 수 있다. 공동훈련 점수와 단순 비교하지 않는다.

## 제공 상태

| 영역 | 현재 상태 |
|---|---|
| 역할·편성·숙지·대체·인계 | 구현, 자동시험 있음. 기관 SOP·실사용 검수 대기 |
| 사건 편집·제한 DSL·공동 진행·재생 | 구현, 원자성·멱등성·권한·재접속 자동시험 있음 |
| 가상 주건물·인접동·로컬 지도 | 외형/윤곽 외 지하·층 윤곽·내부9종·10용도 제안·복제/거리/방위·주변 자원·가상 GLB/JSON 묶음 구현. 두 엔진 제작/절개/내보내기 검증, 기관 기준 PC·설계 정확도는 별도 |
| 평가·AAR·개선 완료 증거 | 보고/인계/관찰/과제 완료/AAR까지 브라우저 검증. AAR5쪽·임무카드1쪽 PDF 전체 시각 확인 |
| 카카오 지도·로드뷰 | 공식 SDK 표시 경로와 장애 대안 구현. 승인 플래그·공개 JS 키·도메인·실응답 검증 필요 |
| 건축물대장·기상·용수 API | HTTP·정규화·불변 수집/검토/반영과 합성 시험 구현. 실제 키/기관 데이터셋·이용권 검수 대기 |
| 사진·GLB/IFC | 비공개 저장·검사/권리·배치/층·객체 매핑·GLTFLoader·외벽/참고 사진·오프라인 IFC 변환 구현. 실제 AV/시설 자산/이용권·정확도·기관 오프라인 호스트 검수 대기 |
| 승인 녹화 영상 | MP4/WebM 격리·고정 도구 변환·사건 객체/클립 연결·훈련시계/재접속·AAR 구현. 두 엔진 합성 흐름 검증. [영상 계약](docs/MEDIA_TIMELINE.md), 실제 AV·권리/익명화·승인 호스트·실시간 중계는 별도 |
| AI | 비활성 어댑터. 외부 전송 없음. 승인된 공급자 구현은 후속 단계 |
| 운영 DB·계정 | SQLite 개발 경로 자동시험 있음. PostgreSQL 설정·기관 계정 CLI 준비, 기관 DB·SSO 실증 대기 |

지도 사용은 실제/혼합 대상물에서만 선택할 수 있다. `VITE_KAKAO_MAPS_APPROVED=true`와 도메인이 제한된 공개 JavaScript 키를 설정하고 서버를 재시작한다. 로드뷰는 공식 위젯 안에서만 참조하며 사진 추출·캐시·텍스처 재가공 기능은 제공하지 않는다.

## 검증

```powershell
python -m pytest tests -q --basetemp=runtime/pytest --junitxml=artifacts/tests/pytest.xml
npm.cmd test
npm.cmd run build
python scripts/export_schemas.py
```

12접속 장시간 시험은 서버 실행 후 아래 명령으로 별도 실행한다. 합성 답안·가상 승인만 사용하고, 실제 사용자 시범훈련을 대체하지 않는다.

```powershell
python scripts/perf_soak.py --duration 3600 --output artifacts/perf/soak-60min.json
```

독립 headless Chromium·Firefox에서 역할 숙지·인계·AAR·공공자료·모델/사진·영상·상세 생성기·비공개 환경 주석·과대 장면 대안의 전체13개 흐름이 각 엔진에서 통과했다. 기존 Chrome 연결·프로필을 사용하지 않는다. 기관 기준 PC·회의실 후열 실증과 구분하며 실제 결과는 [진행 현황](docs/PROGRESS.md), [시험 기록](docs/TEST_PLAN.md), [AC 추적표](docs/REQUIREMENTS.md)에 기록한다.

2026-11-17 최종 고정본의 API·단위·통합·보안 **226 통과**, 웹 규칙 **39 통과**, TypeScript·Vite 빌드 통과다. 같은 API 소스로 **3600.60초/12가상 접속/246명령/오류0** 장시간 시험을 완료했고 전 접속의 최종 버전247이 일치했다. npm 보안 조회0건·Python 의존성37개 공식 PyPI 권고 조회 실패0/발견0은 해당 패키지 버전의 기록이며 완전한 보안 인증은 아니다. 실제 AV/기관 자료·키·SOP/기준 장비·약10명 회의실 시범훈련은 별도다. [로컬 인계](docs/LOCAL_HANDOFF.md), [증거별 버전/범위](docs/evidence/README.md), [합성 예시](data/README.md)를 제공한다.

## 백업·기관 운영

```powershell
python scripts/backup_restore.py backup runtime/studio.db runtime/backups/studio-snapshot.db
python scripts/backup_restore.py restore runtime/backups/studio-snapshot.db runtime/restored/studio.db
```

백업은 커밋된 WAL 내용을 포함하며, 복구는 해시를 검증한 뒤 **존재하지 않는 새 파일**로만 수행한다. 운영 DB 전환 전 서버를 중지하고 복원본을 별도 확인한다. PostgreSQL은 기관 DBA의 별도 복구 리허설이 필요하다.

기관 운영은 `TRAINING_MODE=production`, `COOKIE_SECURE=true`, 승인된 HTTPS 출처와 전용 DB를 사용한다. 최초 계정은 숨김 비밀번호 프롬프트를 사용하는 `scripts/manage.py`로 생성한다. [기관 배포 문서](infra/README.md)를 따른다.

## 문서

- [원본 계획 사본](docs/DEVELOPMENT_PLAN.md), [사용자 지시](docs/INSTRUCTIONS.md), [작업 기록](docs/WORK_LOG.md), [개선 기록](docs/IMPROVEMENTS.md)
- [역할·인계 정책](docs/ROLE_POLICY.md), [사건·상태 계약](docs/SCENARIO_SCHEMA.md), [보안](docs/SECURITY.md), [출처·권리](docs/DATA_PROVENANCE.md)
- [진행자·평가관·참가자 매뉴얼](docs/USER_MANUAL.md), [승인·실증 대기사항](docs/OPEN_ITEMS.md)
- [공공 기준자료 설정·검토](docs/PUBLIC_DATA.md)
- [허가 모델·사진·오프라인 IFC](docs/ASSET_PIPELINE.md)
- [의존성·라이선스 선언 기록](docs/DEPENDENCIES.md), [합성 예시](data/README.md)
- [M0~M6 단계별 상태](docs/MILESTONES.md)

런타임 DB·토큰·백업·시험 임시파일·생성 캡처는 Git에서 제외한다. 2026-11-17 사용자 명시 승인으로 검증본을 [GitHub main](https://github.com/leondic1976/FIRE-COMMAND-STUDIO-)에 게시했고 [원격 CI](https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/actions/runs/44042858035)가 통과했다. 정적호스팅의 모든 기능 전환/배포는 [전환 조건](docs/STATIC_HOSTING.md)의 필수 구조 확인 후 진행한다. 기관 정규 출시 승인과는 별도다.
