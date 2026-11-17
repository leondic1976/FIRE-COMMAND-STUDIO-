# ADR-001: 로컬 검증과 기관 운영의 실행 환경

상태: 로컬 개발에 채택. 기관 운영은 승인 전.

계획서 권장 React/TypeScript/Vite/Three.js, FastAPI/Pydantic을 사용한다. 저장소는 SQLAlchemy로 트랜잭션과 낙관적 버전을 구현한다. PostgreSQL 서버가 제공되지 않은 개발 환경에는 SQLite를 사용하고, DATABASE_URL로 PostgreSQL로 전환 가능하게 한다. PostgreSQL에서의 실제 부하·복구는 별도 실행 증거가 필요하다.

훈련 상태 변경은 원자적 compare-and-swap 갱신과 append-only 이벤트 저장으로 묶는다. WebSocket은 서버가 필터링한 스냅샷을 전송하며 재접속은 최신 상태로 회복한다. 단일 웹 프로세스를 기본으로 하고 다중 워커 운영은 공유 브로커 도입/검증 전 제한한다.

실제 자료·외부지도·AI 없이 가상 훈련 전 과정을 먼저 완성한다. 운영기관의 SSO·SOP·자료권리·LAN/프로젝터·참가자 시범훈련 승인은 소프트웨어 자동시험으로 대체하지 않는다.
