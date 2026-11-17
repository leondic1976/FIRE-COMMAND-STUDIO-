# 공통 도메인 계약

서버의 실행 검증 기준은 `apps/api/domain.py` Pydantic 모델이다. TypeScript `index.ts`는 UI에서 같은 계약을 사용하며 `python scripts/export_schemas.py`로 JSON Schema와 OpenAPI 스냅샷을 생성한다.

핵심 불변식: 기관별 격리, immutable 발행본·초기 편성, 별도 실행 편성, 서버 event_seq/state_version, audience별 정보 투영, 제한된 조건 DSL, 사건과 상태 패치 원자 적용. 단위·통합·보안 시험으로 계약 회귀를 검증한다.
