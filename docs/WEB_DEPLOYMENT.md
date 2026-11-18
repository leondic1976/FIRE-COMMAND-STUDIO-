# 웹서버판 설치·운영

웹서버판과 Windows 로컬판은 같은 훈련 기능과 JSON 설정 형식을 사용한다. 웹서버는 관리자가 한 번 설치하고, 사용자는 브라우저에서 서버 주소를 연다. Windows 로컬판은 해당 PC에서 실행한다. 참가자는 대형 공용화면을 보며 구두 토론하며 진행자가 대리 입력한다.

## Python 서버 패키지

서버 패키지를 별도 폴더에 압축 해제한다. Python3.14 환경에서 실행하며 프론트엔드는 이미 빌드돼 있어 서버에 Node를 설치할 필요가 없다.

```powershell
python -m pip install -r requirements.txt
python -m web.server --data-dir runtime/web-server --init
python -m web.server --data-dir runtime/web-server
```

위 기본값은 해당 서버 PC에서만 여는 합성 데모이며 `http://127.0.0.1:8080/`에서 동작한다. 다른 컴퓨터에 공개하는 서버는 아래 운영 설정과 계정·HTTPS를 사용한다. 같은 데이터를 사용하는 프로세스는 하나만 실행한다. 기존 Windows 사용자 데이터나 개발8010 DB를 기본값으로 재사용하지 않는다.

## 공개 HTTPS 운영

기관이 승인한 서버·도메인을 준비한다. 다음 `training.example.com`은 예시이며 실제 주소로 바꾼다.

```powershell
python -m web.server --data-dir runtime/web-server --production --host 0.0.0.0 --public-url https://training.example.com --init
python -m web.server --data-dir runtime/web-server --create-account --organization my-training-org --username operator --role admin
python -m web.server --data-dir runtime/web-server
```

비밀번호는 숨김 입력으로 받는다. 기본 운영 계정/비밀번호는 배포하지 않는다. production에서는 데모 계정 선택이 차단되고 Secure/HttpOnly/SameSite 쿠키와 서버 기관·역할 권한을 사용한다. 승인된 HTTPS 역방향 프록시에서 같은 출처로 HTML/API/WebSocket을 제공한다. 서비스는 단일 프로세스이며 임의 전달 헤더를 신뢰하지 않는다. 실제 서버 주소·TLS·기관 계정·접근 정책의 최종 검증은 해당 환경에서 수행한다.

## Docker + HTTPS 프록시

저장소 또는 서버 패키지 루트에서 실행한다. Docker/Compose는 서버 운영자가 준비한다.

```sh
export STUDIO_DOMAIN=training.example.com
docker compose -f web/compose.yaml up -d --build
docker compose -f web/compose.yaml exec app python -m web.server --create-account --organization my-training-org --username operator --role admin
```

도메인의 DNS를 서버로 연결하고 HTTPS 프록시에80/443 포트를 연결한다. 애플리케이션8080 포트와 데이터 볼륨은 외부에 직접 공개하지 않는다. 자동 인증서 발급에는 실제 도메인·네트워크·지속 저장이 필요하다. [Caddy 공식 HTTPS 요건](https://caddyserver.com/docs/automatic-https).

컨테이너는 비루트 UID10001, 읽기전용 앱 파일, 권한 축소, 별도 데이터 볼륨을 사용한다. Python/Node/프록시 베이스 이미지의 digest를 고정하고 빌드 때 OS 보안 업데이트를 적용한다. 빌더와 런타임을 분리해 Node 개발 의존성을 운영 이미지에 넣지 않는다. 기존 기관 Postgres를 사용할 경우 비밀번호가 포함된 DATABASE_URL은 서버의 비공개 환경변수로 설정한다. 예시 파일이나 정적 웹 번들에는 넣지 않는다.

## JSON 설정과 파일 보관

- `settings.json`: 승인된 연계·검사·공개 지도 키 등 비공개 실행 설정, schema_version1. 기존 로컬 `settings.env`는 처음 실행할 때 허용 항목만 옮기며 원본을 보존한다. 실행 설정 변경은 재시작 후 적용한다.
- `server.json`: 웹 운영 모드·바인딩·포트·공개 주소. CLI로 바꾼 값도 JSON으로 보존하고 이전 유효 파일은 `server.previous.json`으로 남긴다. 웹 정적 자원 폴더에 데이터 폴더를 만들지 않는다.
- 훈련 제작 화면의 **설정 JSON 저장/불러오기**: 역할·배치·장면·사건 설정을 이동한다. 미리보기 후 새 편집본으로 가져오며, 기존 훈련/실행본을 덮어쓰지 않는다. 숙지·구두 확인·리허설·발행·기관 승인·자산/영상 연결은 승계하지 않는다. 새 자료 검수와 발행 절차를 다시 수행한다.

설정 JSON은 전체 실행 이력/평가/첨부자료 백업을 대체하지 않는다. 실행 설정에는 비밀키가 포함될 수 있으므로 서버의 비공개 데이터 폴더에 보관하며 훈련 설정 다운로드·Git·정적호스팅에 포함하지 않는다.

## 백업·복원·업데이트

```powershell
python -m web.server --data-dir runtime/web-server --backup-to backups/training.db
```

DB와 함께 생성된 `training.db.manifest.json`을 함께 보관한다. SQLite의 커밋된 WAL을 포함한 일관 백업을 사용한다. 복원 전 서비스를 중지하고 다음을 실행한다.

```powershell
python -m web.server --data-dir runtime/web-server --restore-from backups/training.db
```

다른 실행기가 같은 데이터 폴더를 사용하면 복원을 거절한다. 검증된 백업을 별도 파일에 복원한 뒤 교체하며, 현재 DB는 `backups/before-restore-….db`로 보존한다. settings.json/server.json은 별도 비공개 백업으로 보관한다. Postgres는 이 SQLite 명령 대신 기관 DB 백업·복구 절차를 사용한다.

업데이트는 서버를 중지하고 기존 코드 폴더의 별도 백업을 남긴 뒤 새 패키지를 풀고 동일한 데이터 폴더로 실행한다. 데이터 폴더/볼륨은 제거하지 않는다. DB schema2와 JSON schema1은 별도로 관리하며 알 수 없는 버전은 실패로 중단한다. 기존 Windows0.1→0.2 설정 마이그레이션과 설치 제거 후 기록 보존은 별도 설치 시험으로 검증한다.

## 운영 경계

AI·실제 지휘망 발신은 기본 비활성이다. 외부 API·지도·AV·정밀 모델·IFC·영상 처리는 원래의 기관 승인·권리·고정 도구 조건을 유지한다. Linux 컨테이너에서 Windows Job/오프라인 호스트 승인을 자동으로 충족했다고 표현하지 않는다. 해당 네이티브 처리는 승인된 지원 호스트가 필요하며 준비 전에는 격리를 유지한다.

현재 제공물은 훈련용 로컬/웹 배포판이다. 실제 기관 SOP 검수·보안 승인·약10명 회의실 시범훈련과 실제 시설 정확도/장비 성능 검증은 별도다. GitHub Pages 안내 페이지와 실제 Python 운영 서버의 주소는 다르다.

보안 점검 참고(2026-11-18): npm 개발 도구 picomatch4.0.7에는 수정판 없는 [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)가 있다. 빌드에서 저장소 자체 glob만 사용하며 Node/개발 서버는 운영물에 포함하지 않는다. 전체 npm 보고를 보존하고 정확한 개발 경로/버전만2026-12-18까지 별도 평가한다. 새 권고·운영 경로·기한 경과는 CI를 중단한다. 컨테이너 런타임에서는 불필요한 pip를 제거하므로 추가 패키지는 이미지를 다시 빌드해 반영한다.
