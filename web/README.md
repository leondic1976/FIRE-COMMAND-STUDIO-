# FIRE-COMMAND STUDIO 웹서버판

Windows 로컬판과 같은 훈련 기능·설정 JSON을 사용하는 웹서버판이다. 웹서버는 관리자가 설치하고 사용자는 웹주소를 브라우저로 연다. 한 운영 PC와 대형 공용화면으로 구두 토론하고 진행자가 대리 입력한다.

## 실행

저장소에서는 루트에서 npm ci 및 npm run build --workspace web를 먼저 실행한다. 서버 배포 ZIP에는 빌드된 프론트엔드가 포함되므로 서버에 Node를 설치할 필요가 없다.

```powershell
python -m pip install -r requirements.txt
python -m web.server --data-dir runtime/web-server
```

기본 합성 데모 주소는 http://127.0.0.1:8080/ 이며 이 PC에서만 접속한다. 실제 공개 운영은 production/HTTPS/기관 계정을 사용한다. 구체적인 서버 설치·Docker/HTTPS·계정·백업/복원은 [운영 안내](../docs/WEB_DEPLOYMENT.md)를 따른다.

## JSON 설정

- 실행 연계 설정: 비공개 데이터 폴더의 settings.json, JSON schema1. 기존 settings.env는 최초1회 허용 항목만 옮기고 원본을 보존한다.
- 웹 서버 주소·운영 모드·포트: server.json, JSON schema1. 실행 중인 앱은 시작 시점의 설정을 보존하며 변경은 재시작 후 적용한다.
- 훈련 제작의 설정 JSON 저장/불러오기: 웹·로컬에서 같은 파일을 사용한다. 미리보기 후 새 편집본으로 가져오고 숙지/검수/발행 승인과 자산 연결은 다시 확인한다.
- 실행 기록/개인평가/첨부자료는 전체 DB 백업으로 보관한다. 설정 파일과 전체 DB 백업은 구분한다.

공통 데이터 계약/원자 명령/기관·역할 권한/공개 화면 투영/AI OFF/워터마크를 서버에서 유지한다. 직접 운영할 서버/호스팅·도메인은 실제 값이 확인돼야 공개 배포할 수 있다. GitHub Pages 안내 페이지가 Python 운영 서버를 대신하지 않는다.
