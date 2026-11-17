from datetime import datetime, timedelta, timezone
from .domain import Exercise, Role, Feature, Patch

ROLE_DATA = [
    ("incident_commander", "지휘대장", None, "기관 확인 필요", ["재난현장 지휘·조정·통제", "위험과 자원 제약에 따른 우선순위·지휘결론", "통제단 가동 전 지휘와 전환 판단"]),
    ("field_officer", "현장지휘요원", "incident_commander", "현장지휘부", ["지휘대장 지휘 보좌", "초기 대응활동 계획 수립 지원", "현장 대응방안과 소방력 배치 제안"]),
    ("resource_officer", "자원지원요원", "incident_commander", "자원지원부", ["자원집결지·대기소 선정 지원", "동원자원 현황 관리", "지원기관·대체자원 요청과 회신 확인"]),
    ("communications_officer", "통신지원요원", "incident_commander", "현장지휘부", ["통신체계 유지·관리", "무전지휘 지원과 전달 확인", "교신 장애 시 예비통신계획 보고"]),
    ("safety_officer", "안전관리요원", "incident_commander", "현장지휘부", ["현장 안전사고 예방계획 검토", "안전진단과 위험요인 보고", "대원 보호·안전조치 권고"]),
    ("situation_officer", "상황조사요원", "incident_commander", "대응계획부", ["현장·119상황실 정보 지원", "상황판단 정보 수집·제공", "확인 사실과 미확인 정보를 구분해 종합 보고"]),
    ("medical_officer", "구급지휘요원", "incident_commander", "현장지휘부", ["재난의료체계 가동 지원", "사상자 현황과 수용능력 확인", "이송·의료자원 조정안 보고"]),
]


def base_roles() -> list[Role]:
    return [Role(id=i, name=n, reports_to=p, department=d, tasks=t) for i, n, p, d, t in ROLE_DATA]


def quiz_for(role: Role) -> list[dict]:
    return [
        {"id": "report", "question": f"{role.name}의 정보가 미확인 상태입니다. 우선 어떻게 보고하나요?", "options": ["추정을 확정 사실로 보고", "출처·미확인 여부를 구분해 승인된 보고선으로 보고", "보고하지 않음"], "answer": 1, "reason": "사실과 추정을 구분하고 승인된 보고경로를 따릅니다."},
        {"id": "mission", "question": f"현재 역할의 핵심 임무에 해당하는 것은?", "options": [role.tasks[0], "확인 없이 다른 요원의 권한을 대신 확정", "참관객 요청을 인명·대원안전보다 우선 처리"], "answer": 0, "reason": role.tasks[0]},
        {"id": "handover", "question": "대체근무를 시작하기 위한 절차는?", "options": ["대체 지정 즉시 기존 담당자 평가를 승계", "구두 통보만으로 활성화", "수락·임무카드·이해도·구두확인·인계를 완료"], "answer": 2, "reason": "대체 지정은 숙련·인계를 뜻하지 않습니다. 새 담당자는 인계 이후부터 귀속됩니다."},
    ]


def demo_exercise(exercise_id: str = "exercise-demo", template: str = "factory") -> Exercise:
    now = datetime.now(timezone.utc)
    role_ids = [r.id for r in base_roles()]
    labels = {"factory": ("물류창고 · 인접 공장", "화재"), "highrise": ("고층 공동주택", "고층건물"), "underground": ("지하상가 침수", "지하공간"), "compound": ("복합재난 훈련지구", "복합재난")}
    label, category = labels.get(template, labels["factory"])
    titles = ["초기 현장 정보", "인접동과 진입로 확인", "소방용수 사용 여부 미확인", "북측 상층 연기 증가", "인접동 노출·출입구 혼잡", "현장대 무전 불량", "요구조자·병원 수용 변동", "외부 참관객 브리핑 요청", "통제단 가동 검토", "최종 지휘결론·미완료 확인"]
    texts = ["모의 현장대: 주대상물 2층에서 연기 관찰. 정확한 화점·인원은 미확인입니다.", "모의 상황실: 인접 B·C동 용도와 진입로 현황을 확인해 주세요.", "모의 자원대: H01 수압은 아직 확인되지 않았습니다. 대체 급수 방안을 검토해 주세요.", "모의 드론 관찰: 북측 3층 연기량 증가 연출. 이전 신고와 층수가 다릅니다.", "모의 현장대: B동 노출 우려, 주출입구 혼잡. 위험 통제 범위를 검토해 주세요.", "모의 현장대: 교신 장애 발생. 예비 연락과 전달 확인이 필요합니다.", "모의 구급대: 요구조자 신고와 병원 수용 정보가 상충합니다. 출처를 확인해 주세요.", "모의 외부 관계자: 브리핑을 요청합니다. 현장 안전과 구조를 우선해 담당자를 정해 주세요.", "모의 상황실: 대응 확대에 따른 통제단 전환·부서 재배치·인계 검토를 요청합니다.", "각 담당자는 미완료 사항, 담당자와 재보고 시각을 정리해 최종 지휘결론을 확인해 주세요."]
    patches = {
        0: [("B01-F02-Z01", "smoke", 0, 1)],
        1: [("ROAD01", "closed", False, True)],
        2: [("H01", "water", "UNCONFIRMED", "UNAVAILABLE")],
        3: [("B01-F03-Z01", "smoke", 0, 3), ("B01-F03-Z01", "fire", 0, 2)],
        4: [("B02", "warning", False, True), ("PERIMETER01", "radius", 15, 30), ("ENT01", "closed", False, True)],
        5: [("V01", "communication", "NORMAL", "FAILED")],
        6: [("B01-F02-Z01", "casualties", 0, 3)],
    }
    recipients = [["situation_officer", "incident_commander"], ["field_officer", "safety_officer"], ["resource_officer"], ["situation_officer", "safety_officer"], ["safety_officer", "field_officer"], ["communications_officer"], ["medical_officer"], ["incident_commander", "safety_officer"], role_ids, role_ids]
    features = [
        {"id": f"B01-F0{floor}-Z01", "name": f"주대상물 {floor}층 북측", "kind": "ZONE", "building_id": "B01", "floor": floor, "state": {"smoke": 0, "fire": 0, "casualties": 0}} for floor in (1, 2, 3)
    ] + [
        {"id": "B02", "name": "인접 공장 B동", "kind": "ZONE", "building_id": "B02", "state": {"warning": False}},
        {"id": "B03", "name": "인접 창고 C동", "kind": "ZONE", "building_id": "B03", "state": {"warning": False}},
        {"id": "ROAD01", "name": "북측 진입로", "kind": "ROAD", "x": 0, "z": -35, "state": {"closed": False}},
        {"id": "ROAD02", "name": "동측 우회로", "kind": "ROAD", "x": 32, "z": 0, "state": {"closed": False}},
        {"id": "ENT01", "name": "북측 출입구", "kind": "ENTRANCE", "building_id": "B01", "x": 0, "z": -11, "state": {"closed": False}},
        {"id": "H01", "name": "가상 소화전 H01", "kind": "HYDRANT", "x": -28, "z": 26, "state": {"water": "UNCONFIRMED"}},
        {"id": "H02", "name": "가상 소화전 H02", "kind": "HYDRANT", "x": 55, "z": 27, "state": {"water": "AVAILABLE"}},
        {"id": "V01", "name": "모의 펌프차 01", "kind": "VEHICLE", "x": 6, "z": 25, "state": {"status": "WAITING", "communication": "NORMAL"}},
        {"id": "PERIMETER01", "name": "훈련 위험통제선", "kind": "PERIMETER", "state": {"radius": 15}},
        {"id": "ASSEMBLY01", "name": "가상 자원집결지", "kind": "ASSEMBLY", "x": -48, "z": 30, "state": {"status": "AVAILABLE"}},
        {"id": "HOSPITAL01", "name": "모의 협력병원", "kind": "HOSPITAL", "x": 65, "z": -35, "state": {"status": "UNCONFIRMED"}},
    ]
    events = []
    for i in range(10):
        events.append({"id": f"EV-{i+1:02}", "title": titles[i], "category": category, "objective": "정보검증·역할 협업·안전한 지휘결정", "text": texts[i], "recipient_role_ids": recipients[i], "visibility": "PRIVATE" if i in (2, 5, 6) else "PUBLIC", "priority": "HIGH" if i in (3, 4, 5) else "NORMAL", "next_event_ids": [f"EV-{i+2:02}"] if i < 9 else [], "terminal": i == 9, "simulated_at": i * 180, "patches": [{"feature_id": f, "field": k, "before": b, "after": a} for f, k, b, a in patches.get(i, [])]})
    exercise = Exercise.model_validate({
        "id": exercise_id, "name": f"{label} 공동 상황판단 훈련", "roles": [r.model_dump() for r in base_roles()],
        "persons": [{"id": f"person-{i:02}", "display_name": f"훈련요원 {i:02}"} for i in range(1, 11)],
        "assignments": [{"id": f"assignment-{i+1}", "role_id": r, "person_id": f"person-{i+1:02}", "effective_from": (now - timedelta(days=1)).isoformat(), "effective_to": (now + timedelta(days=30)).isoformat(), "backups": [f"person-{8+i%3:02}", f"person-{8+(i+1)%3:02}"]} for i, r in enumerate(role_ids)],
        "subject": {"name": f"가상 {label}", "buildings": [{"id": "B01", "name": "주대상물 A동", "use": "물류창고"}, {"id": "B02", "name": "인접 공장 B동", "use": "공장", "floors": 2, "width": 22, "depth": 18, "x": 48, "z": -12, "color": "#bda88f"}, {"id": "B03", "name": "인접 창고 C동", "use": "창고", "floors": 2, "width": 26, "depth": 16, "x": -45, "z": -18, "color": "#8fa7af"}], "features": features, "source": {"provider": "FIRE-COMMAND 절차 생성 합성자료", "as_of": now.date().isoformat()}},
        "events": events, "start_event_id": "EV-01"
    })
    if template == "highrise":
        building = exercise.subject.buildings[0]
        building.name, building.use, building.floors, building.width, building.depth = "고층 공동주택 A동", "고층아파트", 18, 24, 20
        exercise.subject.buildings[1].floors = 12
        exercise.subject.buildings[1].use = "공동주택"
        exercise.subject.buildings[1].name = "인접 공동주택 B동"
        exercise.subject.buildings[2].floors = 8
        exercise.subject.buildings[2].name = "인접 업무동 C동"
        exercise.subject.buildings[2].use = "업무시설"
        exercise.events[0].title = "공동주택 초기 연기 신고"
        exercise.events[1].text = "모의 현장대: 고층 공동주택의 소방차 진입·고가차 전개 공간과 인접동 피난 인원을 확인해 주세요."
        exercise.events[3].title = "상층 연기·피난계단 정보 상충"
        exercise.events[3].text = "모의 상황실: 상층 연기 신고와 피난계단 사용 가능 정보가 상충합니다. 정확한 층·출처·대원 접근로를 재확인해 주세요."
    elif template == "underground":
        exercise.subject.buildings[0].name = "지하상가 연결시설 A동"
        exercise.subject.buildings[0].use = "지하상가 연결시설 · 지하구역 위치는 주석"
        exercise.subject.features.extend([
            Feature(id="UG01", name="지하상가 북측 침수구역 (위치 주석)", kind="ZONE", building_id="B01", floor=0, x=0, z=-20, state={"water": 0, "casualties": 0}),
        ])
        exercise.events[0].title = "지하상가 초기 침수 신고"
        exercise.events[0].text = "모의 현장대: 지하상가 북측에서 침수 신고가 들어왔습니다. 수위·인원·전기설비 상태는 미확인입니다."
        exercise.events[0].patches = [Patch(feature_id="UG01", field="water", before=0, after=1)]
        exercise.events[2].title = "배수·급수 자원 사용 여부 미확인"
        exercise.events[2].text = "모의 자원대: 급수시설 사용 여부와 배수장비 도착 시각을 확인해야 합니다. 가용 장비·대체 자원을 요청해 주세요."
        exercise.events[3].title = "지하구역 침수 범위 증가"
        exercise.events[3].text = "모의 현장대: 북측 지하구역 침수 범위가 늘었다는 보고입니다. 실제 수위 계측값은 없으며 위치 주석은 훈련용 연출입니다."
        exercise.events[3].patches = [Patch(feature_id="UG01", field="water", before=1, after=3)]
        exercise.events[4].title = "피난 출입구 혼잡·안전구역 확대"
        exercise.events[6].title = "지하구역 요구조자 신고"
        exercise.events[6].patches = [Patch(feature_id="UG01", field="casualties", before=0, after=3)]
    elif template == "compound":
        exercise.subject.features.append(Feature(id="ENV01", name="강우·전력 가상 환경", kind="ZONE", state={"rain": 0, "power": True}))
        exercise.events[0].title = "강우 중 복합시설 연기 신고"
        exercise.events[0].text = "모의 상황실: 강우 중 복합시설에서 연기 신고와 도로 침수 정보가 함께 들어왔습니다. 출처별 확실성과 접근로를 확인하세요."
        exercise.events[0].patches.append(Patch(feature_id="ENV01", field="rain", before=0, after=3))
        exercise.events[5].title = "정전·무전 혼선 동시 발생"
        exercise.events[5].patches.append(Patch(feature_id="ENV01", field="power", before=True, after=False))
        exercise.events[7].title = "언론·관계기관 브리핑 동시 요청"
    return exercise
