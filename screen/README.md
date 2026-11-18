# SCREEN · 현장 영상 훈련

큰 3D 현장과 작은 우측 상황 메시지를 보며 진행하는 별도 웹 프로그램이다. 밝은 화면, A/B/C/D 방면, 화재/요구조자/소방차/고가차/구급차/지휘대/대원/소화전/통제선 배치, 시나리오 JSON·회의 기록을 제공한다. 기존 스튜디오의 임무 숙지·평가 프로그램과 구분되는 현장 연출 모듈이다.

## 설치·실행

서버 ZIP은 Python3.14가 필요하며 빌드된 화면을 포함한다. 압축을 푼 루트에서 실행한다.

```powershell
python -m pip install -r requirements.txt
python -m screen.server --data-dir runtime/screen
```

서버 PC의 **http://127.0.0.1:8090/** 를 연다. 기본은 합성 데모이며 AI/실제 출동망·미승인 외부 연계는 비활성이다. `가상 진행자로 시작` → `현장 설정` → `새 훈련` → `훈련 시작` 순서로 사용한다. 공용화면은 같은 브라우저의 별도 창에서 열어 프로젝터로 옮긴다.

소스에서는 Node24로 `npm ci` 후 `npm run build --workspace screen`을 먼저 실행한다. 개발 서버5190을 쓸 때 API를 `--allow-development-origin http://127.0.0.1:5190`으로 실행하고 `npm run dev --workspace screen`을 사용한다. 운영 모드에는 개발 Origin을 허용하지 않는다.

## 시간과 토론

- 첫 사건≥60초, 연속 사건 간격≥60초, 마지막 사건 뒤≥60초 토론 시간. 기본12사건/14분 예시는 `data/warehouse.json`이다.
- 자동 진행 또는 진행자 확인 방식을 선택한다. 확인 방식도 시간이 되기 전에 공개할 수 없다. 일시정지/재개·종료와 회의 기록을 제공한다.
- 시나리오 장면 미리보기는 진행자 전용 검토다. 실행 훈련/공용화면을 빠르게 진행하는 기능이 아니다.
- 지연·재접속 뒤 여러 사건을 한꺼번에 공개하지 않는다. 서버 재시작은 마지막 커밋 시계로 일시정지 복구하며 최대5초의 미기록 시계 진행은 제외한다. 메시지·상태·시퀀스·이력은 한 트랜잭션에서 기록한다.
- 회의 기록은 공용화면으로 보내지 않는다. 실행본 선택으로 과거 기록을 열고 JSON으로 내보낼 수 있다.

## 현장과 방면

A는 건물 전면이다. **위에서 본 시계방향 A→B→C→D**이며 로컬 좌표 A=+Z, B=-X, C=-Z, D=+X다. A에서 건물을 바라보면 B는 왼쪽, C는 후면, D는 오른쪽이다. `A 전면 방위각`으로 지도상 방향을 정한다. 전체·지휘관 낮은 시점·각 방면, 마우스 회전/확대를 제공한다.

배치 지도 클릭은 선택한 자원을 지상으로 옮긴다. 화점·요구조자를 건물에 연결하면 방면/층/벽면 오프셋으로 위치를 정한다. 실내/출입구의 실제 위치를 자동으로 확인한 결과가 아니다. 구조 후 이동은 시나리오의 위치 변경으로 정한다.

JSON을 저장/가져오면 새 설정을 이동할 수 있다. 실제 자료 연결과 승인 상태는 가져오기로 승계하지 않는다. 실행 중 설정은 고정되며 편집한 설정은 새 실행본부터 적용된다. 전체 DB/사진/모델/회의 기록 백업은 설정 JSON과 다르다.

## 브이월드3D 연결 (SCREEN0.2)

공급자는 사용자 지시로 **브이월드**로 확정했다. 공식3.0 SDK의 지형/건물 지도에 자체 훈련 효과를 연결한다. 인증키가 없거나 서비스가 실패하면 현재2D·상황 메시지를 유지하며 실제 지도 성공으로 표시하지 않는다.

1. [브이월드](https://www.vworld.kr/)에서 본인 계정으로 인증키를 신청한다. WebGL3D와 검색 API 사용을 선택하고 실제 서비스 URL을 등록한다. 현재 로컬 실행 주소는 **http://127.0.0.1:8090/** 이다. localhost/IP/포트 등록 허용 방식은 포털에서 확인하며 두 호스트를 같은 등록으로 가정하지 않는다.
2. 저장소/패키지 루트에서 다음을 실행한다. Windows에서는 `screen/configure-vworld.cmd`를 열어도 된다. 키는 숨김 입력하며 Git/로그/채팅으로 보내지 않는다. 검색 키가 따로 없으면 두 번째 입력은 Enter다.

```powershell
python -m screen.vworld configure --data-dir runtime/screen
python -m screen.vworld check --data-dir runtime/screen
```

3. 서버를 재시작한다. **현장 설정 → 대상 현장 → 지도 표시 방식 → 브이월드 실제3D 지도 + 훈련 연출**을 선택한다. 장소명/도로명/지번 검색 버튼으로 공개 대상물을 찾고 결과를 적용한다. A 전면 방위·건물 위치/폭/깊이/층고와 자원을 검토한 후 저장하고 새 훈련을 만든다. 실행 중인 이전 가상 실행본은 바뀌지 않는다.
4. 해당 건물의 실제 지도 제공 여부·외형/좌표/갱신 수준을 확인한다. 검색 좌표가 정확한 화점/실내/소화전 위치를 보장하지 않는다. 키/등록 주소 불일치·사용량 초과·SDK/네트워크/WebGL 실패는 명시2D 상태로 처리한다.

인증키·서비스 URL·이용조건 확인은 비공개 `vworld.json`에 보존하며 기본은 비활성이다. 프레임은 세션/부모DOM에 접근할 수 없고 지도 좌표/카메라 위치만 받는다. 회의 메모·미래 사건·요구조자/자원 배열은 SDK에 전달하지 않는다. SDK 로고/출처를 유지하고 지도/실사 타일을 추출·복제·오프라인 캐시하지 않는다. 브라우저용 지도 키는 SDK 요청에서 보이므로 발급한 서비스 주소로 제한한다. 별도 검색 전용 키는 서버 검색에만 사용한다.

공급 지도의 원본 건물을 붕괴·변형하지 않는다. 화재/방수/차량은 자체 훈련 오버레이며, 가림은 설정한 근사 건물 상자를 기준으로 한다. 제공자 지형/건물 전체의 정확한 가림·실내 물성·실제 화재 해석을 보장하지 않는다. 지도는 상류에서 갱신될 수 있으며 과거 실사 원본의 불변 백업을 제공하지 않는다. 자세한 계약/사용자 준비와 실제 검증 구분은 [브이월드 연계 기록](../docs/VWORLD_INTEGRATION.md)을 따른다.

## 전국 건물·실사 자료의 필수 조건

**전국 모든 건물의 실제 형상/실사 텍스처 데이터는 이 프로그램에 포함되지 않았다.** 주소·좌표만으로 모든 실제 건물이나 실내를 복원했다고 표시하지 않는다. 공급자는 브이월드로 확정했으며 공식 SDK 연계를 구현했다. 실제 인증키·등록 서비스 URL·대상 건물의 제공 범위/이용조건과 시설 모델/사진은 아직 미검증이다. 이 외부 조건을 가상 3D의 완성으로 대체하지 않는다.

현장별 주소/좌표·건물 규격을 설정하고, 승인된 GLB(미터 좌표·내장 텍스처)와 A/B/C/D 사진을 연결하는 경로를 구현했다. 가상/근사/실제 라벨을 구분한다. 실제 모드는 모든 건물의 검수된 실제 모델이 있어야 실행할 수 있다. 사진만 붙인 근사 상자를 실제 측량 모델로 표시하지 않는다.

자료 등록은 최대8MB, 서버 격리·승인 검사기·구조/외부 참조 검사·정규화본 재검사·출처/이용권/모델·좌표 사람 검수 후 적용한다. 기본 검사기 미설정 상태에서는 **격리**하며 승인하지 않는다. 사용자의 비공개 `settings.json`에서 기존 ASSET_SCAN_APPROVED/ASSET_SCAN_APPROVAL_REF 등 승인된 검사기 설정을 적용한다. 검증에서 주입한 합성 검사기는 실제 AV나 기관 승인이 아니다. 임의 URL·로드뷰 추출/텍스처 재사용은 제공하지 않는다.

## 실제 웹 운영·백업

```powershell
python -m screen.server --data-dir runtime/screen --production --host 0.0.0.0 --public-url https://screen.example.com --init
python -m screen.server --data-dir runtime/screen --create-account --organization my-training-org --username operator --role admin
python -m screen.server --data-dir runtime/screen
```

위 도메인은 예시다. 실제 공개 서버·DNS·HTTPS 프록시와 기관 계정을 준비한다. 비밀번호는 숨김 입력이며 기본 운영 계정은 없다. CLI 설정은 private `server.json`, 공통 연계 설정은 `settings.json`에 보존한다. 웹 정적 자원 폴더를 데이터 경로로 쓰면 설정을 쓰기 전에 거절한다. 기본 저장소는 SQLite schema2/단일 프로세스다.

Docker/HTTPS 구성은 서버 패키지 루트에서 다음을 실행한다.

```sh
export SCREEN_DOMAIN=screen.example.com
docker compose -f screen/compose.yaml up -d --build
docker compose -f screen/compose.yaml exec app python -m screen.server --create-account --organization my-training-org --username operator --role admin
```

DB 일관 백업은 `python -m screen.server --data-dir runtime/screen --backup-to backups/screen.db`를 사용한다. 함께 생성되는 manifest를 보존한다. 복원은 서버를 중지하고 `--restore-from backups/screen.db`로 실행한다. 현재 DB를 자동 백업하고 검증된 파일을 복원한다. JSON 실행 설정은 별도로 비공개 백업한다. 업데이트/제거 때 데이터 폴더/볼륨을 삭제하지 않는다.

## 검증·한계

`python -m pytest screen/tests tests -q`, `npm test`, `npm run build --workspace screen`. 실제 브라우저 시험은 별도 loopback8090 합성 서버에서 `RUN_SCREEN_BROWSER_TESTS=1`, `BROWSER_ENGINE=chromium|firefox`로 `python -m pytest screen/tests/test_browser.py -q`를 실행한다. 실제60초를 기다리며 사건/시계/공용 격리·JSON·모바일·WebGL 실패를 확인한다. 실행 결과와 실패/개선은 루트 docs/WORK_LOG·TEST_PLAN·IMPROVEMENTS 및 SCREEN 증거에서 기록한다.

정적인 장면 배칭·제한된 파티클·기기에 따른 가벼운 모드와2D 대안을 사용한다. 현재 FPS 표시는 해당 브라우저의 렌더링 표본이며 기관 기준 PC/프로젝터·전국 실사 성능 승인이 아니다. 실제 기관 SOP·자료 정확도/이용권·AV·약10명 실제 회의실 시범훈련은 별도다. GitHub Pages는 Python 서버를 실행하지 않는다.

한 현장의 예제/파일 모델 상한은24건물·40층·96배치·120사건이며, 연결 자료 총64MB/50만 삼각형/32M 텍스처 화소를 넘으면 실행과 미리보기를 차단한다. 브이월드 지도 스트리밍은 별도 SDK 프레임을 사용하며 파일 모델 상한을 전국 데이터 전체 상한으로 해석하지 않는다. 실제 인증키·등록 주소·지역별 제공 범위 검증 전에는 전국 실사 완성을 주장하지 않는다.
