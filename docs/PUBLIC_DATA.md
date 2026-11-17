# 공공 기준자료 연결·검토

2026-11-17 구현. 건축물대장·기상청 초단기실황·기관이 지정한 ODcloud 소방용수시설 자료를 **서버에서 조회하고, 불변 수집본을 저장한 뒤 제작자가 선택한 항목만 초안에 반영**한다. 실제 키·기관 데이터로 성공한 연결이라고 표시하지 않는다. 합성 HTTP 응답으로 검증한 소프트웨어 경로다.

## 공식 계약과 설정

| 공급자 | 고정 HTTPS 호스트·경로 | 조회/한계 |
|---|---|---|
| 건축물대장 | `apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo` | 시군구5자리·법정동5자리·대지구분·본번/부번4자리. 지상층수·용도·명칭을 선택 반영. 높이/면적/주소는 참고, 실내 구조나 건물 치수를 추정하지 않음 |
| 기상청 | `apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst` | KST 관측일/정시·격자 NX/NY. 단위·관측시각·결측을 보존. 관측값을 훈련 풍향이나 공학적 예측으로 자동 반영하지 않음 |
| 소방용수 | `api.odcloud.kr` + 관리자 승인 데이터셋 경로 | 전국 표준자료를 제공하는 기관별 데이터셋을 사전 확인해야 함. WGS84 좌표를 대상물 주변 약2km 로컬 좌표로 근사. 현재 사용 가능 여부는 항상 미확인 |

명세 근거: [건축물대장 공개 API](https://www.data.go.kr/data/15134735/openapi.do), [기상청 단기예보 조회서비스](https://www.data.go.kr/data/15084084/openapi.do), [전국소방용수시설 표준데이터](https://www.data.go.kr/data/15034538/standard.do). 카탈로그 확인과 실제 키의 허용 범위·실응답 검증은 구분한다. 소방용수 표준자료 자체를 단일 전국 HTTP API라고 가정하지 않는다.

서버 환경에만 다음을 설정한다. 키를 채팅·브라우저 입력·Git·검증 로그에 넣지 않는다. 실제 값을 문서에 적지 않는다.

```dotenv
EXTERNAL_DATA_APPROVED=false
EXTERNAL_DATA_APPROVAL_REF=
DATA_GOV_BUILDING_KEY=
KMA_SERVICE_KEY=
DATA_GOV_HYDRANT_KEY=
HYDRANT_DATASET_PATH=
HYDRANT_CATALOG_URL=
```

기관 승인 근거와 필요한 키가 설정되고 `EXTERNAL_DATA_APPROVED=true`일 때 해당 공급자만 활성화된다. 소방용수 경로는 `/api/8자리숫자/v1/UUID` 또는 `/api/8자리숫자/v1/uddi:UUID`만 허용한다. 요청 대상에 URL 전체나 임의 호스트를 받지 않는다. 별도의 `HYDRANT_CATALOG_URL`에는 관리자가 확인한 `https://www.data.go.kr/data/동일8자리자료ID/fileData.do` 또는 `openapi.do`/`standard.do`를 넣는다. 카탈로그 유형을 임의 추정하지 않으며 ID 불일치·쿼리/리다이렉트 URL은 비활성 처리한다. 연결 상태의 `live_verified`는 실기관 시험을 대신하지 않으며 현재 false다. Vite 환경변수에 서비스 키를 넣지 않는다.

## 제작 흐름과 불변식

1. 훈련 제작 → 건물·지도·자원 → 공공 기준자료에서 조회 조건을 입력한다. 내부 분류 대상물은 외부 조회를 차단한다.
2. 수집·미리보기는 훈련 상태를 변경하지 않는다. 정규화된 수집본·원응답 SHA256·조회조건·수집시각을 기관 범위에 저장한다. 원응답 본문·키·알 수 없는 개인정보 필드는 저장하지 않는다.
3. 이용권·좌표·기준시각·선택 속성·검토 메모를 확인한다. 건물/용수는 실제·혼합 모드를 명시해야 반영된다. 수집본 자체의 권리는 미확인 상태를 유지한다.
4. 반영은 서버 버전/CAS·멱등키와 단일 트랜잭션을 사용한다. 검토자·정정/교체 이력이 추가되며 이전 수집본은 남는다. 일반 편집으로 해당 이력과 출처 연결을 위조할 수 없다.
5. 건축물대장 반영은 근사 모델로 표시하고 실내 검증을 해제한다. 층을 줄여 기존 구역을 잃거나 지원 범위를 벗어나면 전체 반영을 거절한다. 소방용수 자료 교체 시 이전 자료 객체를 제거하고 새 항목만 반영한다.
6. 리허설·발행을 다시 확인한다. 실행본의 기준자료는 스냅샷으로 고정되고 AAR JSON/Markdown/인쇄 화면에 포함된다. 비공개 검토 메모는 공동화면 응답에 포함하지 않는다. 제한된 참관자는 실제 대상물 자료 목록도 받지 않는다.
7. 복제본은 공공자료 승인·자료 기반 용수 객체를 초기화한다. 최신 자료를 재수집·검토해야 한다. 일반 가상 객체는 유지한다.

8초 타임아웃·2MiB 응답 한도·리다이렉트/압축 응답 거절·XML DTD 차단·응답 스키마/좌표/숫자 검증·개인별 공급자 분당20회 제한을 적용한다. 실패 시 비밀 없는 오류와 로컬 제작 대안을 제공한다. HTTP 라이브러리 로그의 키도 마스킹한다.

## 검증 환경·저장 호환성

`tests/unit/test_external_data.py`와 `tests/integration/test_external_workflow.py`는 합성 응답으로 정상·장애·권한/기관 격리·동시 수정·멱등성·공용/참관 유출을 시험한다. `python -m scripts.run_external_fixture`는 127.0.0.1:8011 전용 합성 UI 시험 서버다. 모든 공급자 요청은 `httpx.MockTransport`로 처리하며 실제 외부 호출을 하지 않는다. 운영 진입점으로 사용하지 않는다.

```powershell
$env:RUN_EXTERNAL_BROWSER_TESTS='1'
$env:BROWSER_ENGINE='chromium' # 또는 firefox
python -m pytest tests/e2e/test_external_browser.py -q
```

공공자료 단계 자체에는 테이블 변경이 없으며 기존 JSON에 `external_layers=[]`, `external_reviews=[]`, 객체 `data_origin=SIMULATED`, `source_layer_id=null`을 추가했다. 이후 자산 단계에서 바이너리 테이블을 추가한 스키마2로 갱신했다(ASSET_PIPELINE 참조). 기존 백업은 새 계약에서 읽을 수 있다. 새 외부자료/자산을 반영한 DB를 구버전 코드로 되돌려 읽지 않는다. 업데이트 전 `scripts/backup_restore.py`로 백업하고 롤백 시 코드와 해당 시점 백업을 함께 복원한다.

실제 공공 API 실응답·기관 데이터셋의 컬럼·이용권·데이터 최신성·누락률 검수는 미실행이다. 가상 시험의 승인 체크는 실제 기관 승인/이용권을 만들어내지 않는다.
