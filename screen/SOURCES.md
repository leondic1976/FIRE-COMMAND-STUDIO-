# 자료·출처와 검증 경계

- `data/catalog.json`64개 멘트와 `warehouse.json`은 자체 작성 가상 예시다. 실제 기관 관측·승인·SOP가 아니며 완전한 화재 분류 목록이 아니다. 강도0~4는 시각 연출이다.
- 분류 참고: [NIST Fire Dynamics](https://www.nist.gov/el/fire-research-division-73300/firegov-fire-service/fire-dynamics), [NIST Wind Driven Fires](https://www.nist.gov/el/fire-research-division-73300/firegov-fire-service/wind-driven-fires), [NIST Structural Collapse](https://www.nist.gov/el/fire-research-division-73300/firegov-fire-service/structural-collapse), [NFA Command and Control of Incident Operations](https://apps.usfa.fema.gov/ax/sm/sm_0312.pdf). 바람/붕괴 페이지는 갱신 중단 표시가 있는 과거 연구다. 원본 시나리오·사진/도표를 복제하지 않았다. 특정 발생 시간·위험 예측·대응 정답을 추론하지 않는다.
- 3D 재질/지형/건물/차량/인물과 효과는 코드로 자체 생성한다. 외부 사진/로드뷰·타일·사유 모델을 기본 배포물에 넣지 않았다. 외부 실제 자료는 서버 검사·사람 검수 후 사용한다.
- 기술 참고: [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer), [Color Management](https://threejs.org/manual/pages/color-management.html). 실시간3D를 실사 촬영 영상이나 공학적 화재 해석으로 표시하지 않는다.
- 전국 실제 데이터 검토: [Google 공식 제공 범위](https://developers.google.com/maps/coverage), [Photorealistic 3D Tiles 제품](https://mapsplatform.google.com/maps-products/map-tiles/). 국가별/지역별 범위와 라이선스는 실제 공급 계약에서 확인한다. 브이월드 공식 개발 문서는 조회 실패였고 구현·실환경 제공 범위를 검증했다고 주장하지 않는다.
- Nominatim/OSM도 검토했으나 사용자가 공급자를 선택하지 않았고 [공공 Nominatim 정책](https://operations.osmfoundation.org/policies/nominatim/)의 명시적 사용 판단·호출 제한·캐시·비자동완성 조건이 있어 임의로 기본 검색 서비스로 넣지 않았다. [OSM 이용권](https://www.openstreetmap.org/copyright)의 표시/공유 조건을 생략하지 않는다. 모든 실제 건물/사진의 존재·정확도·이용권을 보장하는 근거로 사용하지 않는다.

확인 날짜2026-11-18. 실제 공급자/자료/키·적법한 공개 범위는 사용자 답변 대기다. 키·실명명부·도면·런타임DB·세션 쿠키는 Git/배포/공개 검증 증거에 포함하지 않는다.

2026-11-18 후속: 사용자가 브이월드를 선택했다. [공식 검색2.0](https://www.vworld.kr/dev/v4dv_search2_s001.do) 원문을 기본 인증서 검증 HTTP200으로 확인했다. key/service/search/request/version/format/size·장소/주소 구분·응답 point.x/y와 주소 결과의 title 부재·오류를 근거로 정규화한다. [검색API 등록](https://www.data.go.kr/data/15058799/openapi.do)의 비용/정책 범위를 따른다. 정확한 일일 호출 수를 추정하지 않는다. 공식3.0 샘플 저장소 HEADbb57af6e1a6e2e312634ac76dc7540e135ec10a0의 vw.Map/start/ws3d.viewer/콜백/facility_build를 확인했다. 과거 '공급자 미정/문서 조회 실패'는 당시 기록이며 공급자 선택과 검색 명세 확인으로 갱신한다. 인증키 포털의 서비스URL/IP/포트 허용·약관 세부/시설별 커버리지·실키 SDK 표시는 아직 확인하지 못했다.
