# 개발용 기준 자료

`python scripts/export_schemas.py`로 계약과 합성 예시를 내보낸다. 역할 원본은 `apps/api/seeds.py`, 계약 원본은 `apps/api/domain.py`다. 이 폴더의 JSON을 편집해도 실행 중 데이터베이스는 바뀌지 않는다.

`packages/domain-schemas/asset-provenance.schema.json`은 업로드 multipart의 provenance JSON 계약이다. Exercise JSON Schema에는 연결/검토/매핑, OpenAPI에는 전용 자산/콘텐츠 경로가 포함된다. 생성 매니페스트는8개 계약/역할/예시 파일의 해시를 포함한다.

- `role-seeds/statutory-base.json`: 기본 7역할·보고선·임무. 법령 부서 매핑의 출처와 실무 검수 한계는 `docs/DATA_PROVENANCE.md` 참고.
- `synthetic/`: 물류창고·고층·지하 침수·복합재난의 미발행 예시. 사람·건물·사건 모두 합성자료다. 근무기간은 생성 시점 기준이다.
- `manifest.json`: 생성 시각·파일 해시·합성자료/기관 미승인 표시. 실제 명부·도면·세션 토큰·운영 DB를 포함하지 않는다.

실제 실행은 UI에서 새 템플릿을 생성하는 경로를 권장한다. 예시 JSON은 스키마 검토·오프라인 개발 자료이며, 미검수 예시를 기관 승인 훈련본으로 가져오는 기능은 제공하지 않는다.
