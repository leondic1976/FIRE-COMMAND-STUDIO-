# 기관 내부 배포 준비

기본 검증은 단일 프로세스 FastAPI + SQLite + 빌드된 React/Three.js 앱이다. PostgreSQL/Docker는 현재 장비에 제공되지 않았으므로 실제 실행 검증을 완료했다고 표시하지 않는다.

1. 기관 승인 서버·TLS 역방향 프록시·접근 허용 도메인·자료 보존정책을 정한다.
2. `DATABASE_URL=postgresql+psycopg2://...`, `TRAINING_MODE=production`, `COOKIE_SECURE=true`, `ALLOWED_ORIGINS=https://승인도메인`을 환경으로 제공한다. 키/비밀번호는 Git에 넣지 않는다.
3. `python scripts/manage.py create-account --organization 기관ID --username 관리자ID --role admin`으로 최초 계정을 생성한다. 비밀번호는 숨김 프롬프트에 입력한다.
4. 앱은 `python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8010 --workers 1`로 실행한다. 외부 수신은 승인된 TLS 프록시에서 처리한다.
5. 실제 기관별 접근제어·전환 편성·역할 숙지·소방 실무검수·실제 대상물 권리·백업복구·LAN 12접속·회의실 후열 가독성을 다시 검증한다.

`compose.yaml`은 PostgreSQL 준비 예시이며 비밀번호 기본값이나 공개 DB 포트를 포함하지 않는다. 앱 계정은 DDL/운영자와 분리하고 필요한 테이블만 접근하도록 기관 DB 관리자가 설정한다. 다중 워커/여러 앱 인스턴스는 공유 작업 큐·브로커와 장애 시험을 갖추기 전 사용하지 않는다.

SQLite 개발 DB는 원본 작업 디렉터리의 `runtime/`에 생성된다. Google Drive 동기화 디렉터리는 기관 운영 DB 저장소로 사용하지 않는다. 실제 운영 데이터는 승인된 로컬/S3 호환 저장소와 기관 DB에 별도로 둔다.

PostgreSQL 백업/복구는 기관 DBA의 `pg_dump`/`pg_restore` 절차 및 권한으로 수행한다. 이 저장소의 `scripts/backup_restore.py`는 SQLite 전용이다. PostgreSQL 복구 리허설은 미실행 상태다.

현재 스키마2는 `asset_blobs`에 격리/정규화 콘텐츠를 보관한다. 메타데이터와 바이트는 원자적으로 기록하며 SQLite 백업에 함께 포함된다. 변경 전 WAL 일관 백업을 만들고 새 파일 복원본의 무결성/해시·자산 표시를 확인한다. 스키마1 복구본은 새 서버에서2로 마이그레이션한다. 다운그레이드는 서버를 중지하고 구코드와 변경 전 백업을 함께 복원한다. 바이너리 포함 DB/백업은 기관 승인 비공개 저장소·보유기간 정책을 적용한다.

실제 파일 입력에는 승인된 로컬 clamd와 갱신된 서명·오프라인 IFC 호스트를 먼저 검증한다. 기본은 격리/변환 비활성이다. ASSET_PIPELINE의 승인 플래그·해시 매니페스트·Job/DACL 제한과 네트워크 차단의 별도 운영 책임을 따른다. 합성 UI 시험용8011 서버는 배포하지 않는다.
