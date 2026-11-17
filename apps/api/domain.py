"""Validated, provider-independent exercise contracts. All examples are simulated."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Any
import math
import json
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .geometry import validate_outline


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


PATCH_FIELDS = {"smoke", "fire", "closed", "warning", "status", "water", "casualties", "radius", "communication", "power", "rain", "wind"}


def valid_state_value(field, value):
    if field not in PATCH_FIELDS:
        return False
    if field in {'closed','warning','power'}:
        return type(value) is bool
    if field in {'status','communication'} or field == 'water' and isinstance(value,str):
        return isinstance(value,str) and 1 <= len(value) <= 100
    if type(value) not in (int,float) or not math.isfinite(value):
        return False
    limit={'smoke':4,'fire':4,'rain':4,'water':20,'wind':200,'radius':2000,'casualties':100000}.get(field)
    return limit is not None and 0 <= value <= limit and (field != 'casualties' or int(value) == value)


class Role(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    name: str = Field(min_length=1, max_length=100)
    tasks: list[str] = Field(min_length=1, max_length=20)
    reports_to: str | None = None
    department: str = "기관 확인 필요"
    authority_limits: str = "승인된 임무 범위에서 보고·제안. 기관 SOP 검수 전."
    first_minute: str = "현재 상황과 정보 출처, 담당자 및 보고경로를 확인한다."
    output: str = "확인된 정보 / 미확인 정보 / 조치 제안 / 재보고 시각"
    source: str = "긴급구조현장지휘규칙 별표 5 훈련용 요약 · 기관 SOP 검수 전"
    source_url: str = "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=287771"
    version: int = Field(default=1, ge=1)
    critical: bool = True


class Person(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    display_name: str = Field(min_length=1, max_length=80)
    available: bool = True


class Assignment(Contract):
    id: str
    role_id: str
    person_id: str
    effective_from: datetime
    effective_to: datetime
    shift_id: str = "A"
    status: Literal["ACTIVE", "PLANNED", "ENDED"] = "ACTIVE"
    backups: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def valid_period(self):
        if self.effective_from.tzinfo is None or self.effective_to.tzinfo is None:
            raise ValueError("근무 시각에는 시간대가 필요합니다.")
        if self.effective_to <= self.effective_from:
            raise ValueError("근무 종료는 시작 이후여야 합니다.")
        if self.person_id in self.backups or len(set(self.backups)) != len(self.backups):
            raise ValueError("대체자는 본인 및 중복 없이 지정합니다.")
        return self


class Source(Contract):
    provider: str = Field(min_length=1, max_length=200)
    as_of: str = Field(min_length=1, max_length=100)
    rights: Literal["approved", "restricted", "unknown"] = "approved"
    confidence: Literal["verified", "approximate", "unverified", "simulated"] = "simulated"
    classification: Literal["SYNTHETIC", "INTERNAL", "PUBLIC"] = "SYNTHETIC"
    url: str = Field(default="", max_length=500)
    reviewer: str = Field(default="", max_length=100)


class FloorOutline(Contract):
    floor: int = Field(ge=-20, le=80)
    footprint: list[list[float]] = Field(min_length=3, max_length=100)

    @field_validator('footprint')
    @classmethod
    def valid_outline(cls, points):
        return validate_outline(points)


class Building(Contract):
    id: str = Field(pattern=r"^B[0-9]{2,4}$")
    name: str = Field(min_length=1, max_length=100)
    use: str = "창고"
    floors: int = Field(default=3, ge=1, le=80)
    floor_height: float = Field(default=4, ge=2, le=10)
    width: float = Field(default=32, ge=3, le=300)
    depth: float = Field(default=22, ge=3, le=300)
    x: float = Field(default=0, ge=-2000, le=2000)
    z: float = Field(default=0, ge=-2000, le=2000)
    rotation: float = Field(default=0, ge=-360, le=360)
    color: str = Field(default="#b3bdc4", pattern=r"^#[0-9a-fA-F]{6}$")
    entrances: list[str] = Field(default_factory=lambda: ["NORTH", "SOUTH"], min_length=1)
    footprint: list[list[float]] = Field(default_factory=list, max_length=100)
    accuracy: Literal["SIMULATED", "APPROXIMATE", "VERIFIED"] = "SIMULATED"
    basement_floors: int = Field(default=0, ge=0, le=20)
    roof_style: Literal['FLAT','GABLE','SHED'] = 'FLAT'
    window_style: Literal['REGULAR','NONE'] = 'REGULAR'
    wall_finish: Literal['CONCRETE','BRICK','METAL','GLASS'] = 'CONCRETE'
    floor_outlines: list[FloorOutline] = Field(default_factory=list, max_length=100)

    @field_validator("footprint")
    @classmethod
    def footprint_valid(cls, points):
        return validate_outline(points)

    @model_validator(mode='after')
    def floor_references(self):
        floors = [item.floor for item in self.floor_outlines]
        if len(floors) != len(set(floors)) or any(f == 0 or f < -self.basement_floors or f > self.floors for f in floors):
            raise ValueError('층별 윤곽의 중복·0층·건물 층 범위를 확인하세요.')
        return self


INTERIOR_KINDS = {'ROOM','CORRIDOR','STAIR','ELEVATOR','COMPARTMENT','EVAC_ROUTE','FIRE_EQUIPMENT','HAZMAT','PASSAGE'}


class Feature(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["ZONE", "ENTRANCE", "HYDRANT", "VEHICLE", "ROAD", "PERIMETER", "ASSEMBLY", "HOSPITAL",'PARKING','ROOM','CORRIDOR','STAIR','ELEVATOR','COMPARTMENT','EVAC_ROUTE','FIRE_EQUIPMENT','HAZMAT','PASSAGE']
    building_id: str | None = None
    floor: int = Field(default=0, ge=-20, le=80)
    x: float = Field(default=0, ge=-2000, le=2000)
    z: float = Field(default=0, ge=-2000, le=2000)
    state: dict[str, int | float | bool | str] = Field(default_factory=dict)
    data_origin: Literal['SIMULATED','REFERENCE'] = 'SIMULATED'
    source_layer_id: str | None = None
    width: float = Field(default=4, ge=.3, le=300)
    depth: float = Field(default=4, ge=.3, le=300)
    height: float = Field(default=2.5, ge=.1, le=10)
    rotation: float = Field(default=0, ge=-360, le=360)
    linked_building_id: str | None = Field(default=None, pattern=r'^B[0-9]{2,4}$')

    @field_validator('state')
    @classmethod
    def state_valid(cls, values):
        if any(not valid_state_value(key,value) for key,value in values.items()):
            raise ValueError('초기 상태의 필드·자료형·유한값·훈련 연출 범위를 확인하세요.')
        return values


class ExternalFact(Contract):
    external_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    fields: dict[str, str | int | float | bool | None]

    @model_validator(mode='after')
    def bounded_fields(self):
        if len(self.fields)>25 or any(len(key)>64 or isinstance(value,str) and len(value)>500 for key,value in self.fields.items()):
            raise ValueError('외부 속성 필드 수·길이 제한을 초과했습니다.')
        return self


class ExternalLayer(Contract):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    import_id: str = Field(pattern=r'^external-[a-f0-9]{32}$')
    provider: Literal['building_registry','weather','hydrant']
    source: Source
    retrieved_at: str = Field(max_length=100)
    raw_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    records: list[ExternalFact] = Field(min_length=1,max_length=100)
    warnings: list[str] = Field(default_factory=list,max_length=30)

    @model_validator(mode='after')
    def bounded_layer(self):
        if len(json.dumps(self.model_dump(mode='json'),ensure_ascii=False).encode())>200_000:
            raise ValueError('외부 자료 계층 크기 제한을 초과했습니다.')
        return self


class ExternalReview(Contract):
    import_id: str
    layer_id: str
    actor_id: str
    at: str
    note: str = Field(min_length=3,max_length=1000)
    selected_ids: list[str] = Field(min_length=1,max_length=100)
    applied_fields: list[str] = Field(default_factory=list,max_length=10)
    supersedes_import_id: str | None = None


class AssetNode(Contract):
    index: int = Field(ge=0,le=1999)
    name: str = Field(max_length=200)
    bounds: list[list[float]] = Field(min_length=2,max_length=2)

    @field_validator('bounds')
    @classmethod
    def valid_bounds(cls,value):
        if any(len(point)!=3 or any(abs(v)>1e6 for v in point) for point in value) or any(value[0][i]>value[1][i] for i in range(3)):
            raise ValueError('객체 경계 범위 오류')
        return value


class AssetManifest(Contract):
    bounds: list[list[float]] = Field(default_factory=list,max_length=2)
    nodes: list[AssetNode] = Field(default_factory=list,max_length=2000)
    triangles: int = Field(default=0,ge=0,le=200000)
    texture_pixels: int = Field(default=0,ge=0,le=8388608)
    width: int = Field(default=0,ge=0,le=4096)
    height: int = Field(default=0,ge=0,le=4096)
    copyright_notice: str = Field(default='',max_length=500)
    duration_seconds: float = Field(default=0,ge=0,le=181)
    frame_rate: float = Field(default=0,ge=0,le=60)
    has_audio: bool = False
    video_codec: str = Field(default='',max_length=40)
    processing_tool: str = Field(default='',max_length=150)
    processing_manifest_sha256: str = Field(default='',pattern=r'^(?:[a-f0-9]{64})?$')

    @field_validator('bounds')
    @classmethod
    def bounds_valid(cls,value):
        if value and (len(value)!=2 or any(len(point)!=3 for point in value) or any(value[0][i]>=value[1][i] for i in range(3))):
            raise ValueError('모델 경계는 양의 크기를 가진3차원 범위여야 합니다.')
        return value


class AssetMapping(Contract):
    building_id: str = Field(pattern=r'^B[0-9]{2,4}$')
    purpose: Literal['MODEL','FACADE','REFERENCE','VIDEO']
    visibility: Literal['PUBLIC','STAFF'] = 'STAFF'
    photo_face: Literal['NORTH','SOUTH','EAST','WEST'] = 'NORTH'
    unit_scale: float = Field(default=1,ge=0.001,le=1000)
    rotation_y: float = Field(default=0,ge=-360,le=360)
    offset: list[float] = Field(default_factory=lambda:[0,0,0],min_length=3,max_length=3)
    floor_map: dict[str,int] = Field(default_factory=dict,max_length=2000)
    object_map: dict[str,str] = Field(default_factory=dict,max_length=2000)

    @model_validator(mode='after')
    def mapping_valid(self):
        if any(abs(value)>2000 for value in self.offset) or any(not key.isascii() or not key.isdigit() or len(key)>4 for key in self.floor_map|self.object_map):
            raise ValueError('모델 위치·객체 인덱스 제한을 초과했습니다.')
        if any(not -20<=floor<=80 for floor in self.floor_map.values()) or any(len(value)>80 for value in self.object_map.values()):
            raise ValueError('층·객체 매핑 범위 오류')
        return self


class AssetBinding(AssetMapping):
    id: str = Field(pattern=r'^binding-[a-f0-9]{32}$')
    asset_id: str = Field(pattern=r'^asset-[a-f0-9]{32}$')
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: Literal['GLB','PHOTO','VIDEO']
    mime: Literal['model/gltf-binary','image/png','video/webm']
    label: str = Field(min_length=1,max_length=160)
    source: Source
    manifest: AssetManifest
    reviewed_at: str


class AssetReview(Contract):
    asset_id: str
    binding_id: str
    actor_id: str
    at: str
    note: str = Field(min_length=3,max_length=1000)
    action: Literal['ATTACH','DETACH']
    mapping: AssetMapping | None = None
    prior_mapping: AssetMapping | None = None
    supersedes_asset_id: str | None = None


class Subject(Contract):
    id: str = "site-demo"
    name: str = Field(min_length=1, max_length=160)
    target_mode: Literal["REAL", "VIRTUAL", "VIRTUAL_ON_REAL_MAP"] = "VIRTUAL"
    scenario_factuality: Literal["SIMULATED", "HISTORICAL"] = "SIMULATED"
    map_context: Literal["SYNTHETIC", "REAL"] = "SYNTHETIC"
    latitude: float = Field(default=37.5, ge=-90, le=90)
    longitude: float = Field(default=127.0, ge=-180, le=180)
    north_rotation: float = Field(default=0, ge=-360, le=360)
    elevation: float = Field(default=0, ge=-500, le=9000)
    buildings: list[Building] = Field(min_length=1, max_length=100)
    features: list[Feature] = Field(default_factory=list, max_length=3000)
    source: Source
    model_accuracy: Literal["SIMULATED", "APPROXIMATE", "VERIFIED"] = "SIMULATED"
    interior_verified: bool = False
    external_layers: list[ExternalLayer] = Field(default_factory=list,max_length=100)
    asset_bindings: list[AssetBinding] = Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def bounded_external_data(self):
        if len(json.dumps([layer.model_dump(mode='json') for layer in self.external_layers],ensure_ascii=False).encode())>1_500_000:
            raise ValueError('대상물 외부 자료 총량 제한을 초과했습니다.')
        if len(json.dumps([binding.model_dump(mode='json') for binding in self.asset_bindings],ensure_ascii=False).encode())>1_500_000:
            raise ValueError('대상물 모델/사진 메타데이터 총량 제한을 초과했습니다.')
        return self




class Patch(Contract):
    feature_id: str
    field: str
    before: int | float | bool | str
    after: int | float | bool | str
    visual_kind: Literal["ILLUSTRATIVE", "ANNOTATION"] = "ILLUSTRATIVE"

    @model_validator(mode="after")
    def valid_patch(self):
        if any(not valid_state_value(self.field,value) for value in (self.before,self.after)):
            raise ValueError('상태 패치의 필드·자료형·유한값·훈련 연출 범위를 확인하세요.')
        return self


class Trigger(Contract):
    kind: Literal["MANUAL", "AT_TIME", "ON_ACTION", "ON_CONDITION", "ON_COMBINATION"] = "MANUAL"
    at_seconds: int = Field(default=0, ge=0, le=86400)
    action: str = Field(default="", max_length=80)
    condition: dict[str, Any] = Field(default_factory=dict)
    auto_release: bool = False


def check_condition(node: dict, depth: int = 0) -> bool:
    if depth > 6 or not isinstance(node, dict):
        return False
    if node.get("op") in ("AND", "OR"):
        return set(node) == {"op", "conditions"} and isinstance(node["conditions"], list) and 1 <= len(node["conditions"]) <= 12 and all(check_condition(n, depth + 1) for n in node["conditions"])
    if set(node) != {"feature_id", "field", "operator", "value"}:
        return False
    if not isinstance(node["feature_id"], str) or not 1 <= len(node["feature_id"]) <= 80 or not isinstance(node["field"], str) or node["field"] not in PATCH_FIELDS or node["operator"] not in ("eq", "ne", "gte", "lte"):
        return False
    value = node["value"]
    return type(value) in (str, bool, int, float) and (type(value) is not float or math.isfinite(value))


def condition_matches(node: dict, scene: dict) -> bool:
    if not check_condition(node):
        return False
    if node.get("op"):
        results = [condition_matches(n, scene) for n in node["conditions"]]
        return all(results) if node["op"] == "AND" else any(results)
    actual = scene.get(node["feature_id"], {}).get(node["field"])
    expected = node["value"]
    if actual is None:
        return False
    if node["operator"] == "eq":
        return type(actual) is type(expected) and actual == expected
    if node["operator"] == "ne":
        return type(actual) is not type(expected) or actual != expected
    if type(actual) not in (int, float) or type(expected) not in (int, float):
        return False
    return actual >= expected if node["operator"] == "gte" else actual <= expected


class MediaCue(Contract):
    binding_id: str = Field(pattern=r'^binding-[a-f0-9]{32}$')
    feature_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    clip_start_seconds: float = Field(default=0,ge=0,lt=181)
    clip_end_seconds: float = Field(gt=0,le=181)

    @model_validator(mode='after')
    def range_valid(self):
        if self.clip_end_seconds<=self.clip_start_seconds:raise ValueError('영상 종료시각은 시작시각보다 뒤여야 합니다.')
        return self


class EventDefinition(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    title: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="INJECT", max_length=80)
    category: str = Field(default="화재", max_length=80)
    objective: str = Field(min_length=1, max_length=300)
    sender: str = Field(default="모의 119상황실", max_length=120)
    recipient_role_ids: list[str] = Field(min_length=1, max_length=100)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"
    priority: Literal["NORMAL", "HIGH", "CRITICAL"] = "NORMAL"
    channel: Literal["RADIO_SIM", "PHONE_SIM", "MESSENGER_SIM", "OBSERVATION", "VIDEO"] = "RADIO_SIM"
    truth_status: Literal["CONFIRMED", "UNCONFIRMED", "FALSE_REPORT"] = "UNCONFIRMED"
    text: str = Field(min_length=1, max_length=5000)
    expected_actions: str = Field(default="담당 임무에 맞는 확인·보고·협조를 관찰한다.", max_length=3000)
    trigger: Trigger = Field(default_factory=Trigger)
    patches: list[Patch] = Field(default_factory=list, max_length=100)
    media_cues: list[MediaCue] = Field(default_factory=list,max_length=10)
    next_event_ids: list[str] = Field(default_factory=list, max_length=100)
    terminal: bool = False
    simulated_at: int = Field(default=0, ge=0, le=86400)
    evaluation_links: list[str] = Field(default_factory=lambda: ["mission", "collaboration"])


class Exercise(Contract):
    id: str
    name: str = Field(min_length=1, max_length=160)
    organization_name: str = "가상 훈련기관"
    objective: str = "임무 숙지·정보검증·협업·안전·지휘결정"
    mode: Literal["GROUP", "PARTIAL", "SOLO", "DIAGNOSTIC"] = "GROUP"
    organization_type: Literal["FIELD_COMMAND", "CONTROL_GROUP", "COMBINED", "CUSTOM"] = "FIELD_COMMAND"
    roles: list[Role] = Field(min_length=1, max_length=100)
    persons: list[Person] = Field(max_length=500)
    assignments: list[Assignment] = Field(max_length=1000)
    subject: Subject
    external_reviews: list[ExternalReview] = Field(default_factory=list,max_length=500)
    asset_reviews: list[AssetReview] = Field(default_factory=list,max_length=500)
    events: list[EventDefinition] = Field(min_length=1, max_length=1000)
    start_event_id: str
    pass_score: int = Field(default=80, ge=0, le=100)
    readiness: dict[str, dict] = Field(default_factory=dict)
    reviews: dict[str, dict] = Field(default_factory=dict)
    published: bool = False
    revision: int = Field(default=1, ge=1)
    rehearsal_passed: bool = False
    organization_approval: str = ""
    simulated_roles: list[str] = Field(default_factory=list)
    publication: dict | None = None
    rehearsal_report: dict | None = None
    practice_owner_person_id: str | None = None
    practice_difficulty: Literal["BEGINNER", "STANDARD", "ADVANCED"] = "BEGINNER"

    @model_validator(mode='after')
    def bounded_asset_history(self):
        if len(json.dumps([review.model_dump(mode='json') for review in self.asset_reviews],ensure_ascii=False).encode())>2_000_000:
            raise ValueError('자산 검토·변경 이력 총량 한도를 초과했습니다.')
        return self


def active_assignments(ex: Exercise, at: datetime | None = None) -> list[Assignment]:
    at = at or datetime.now(timezone.utc)
    return [a for a in ex.assignments if a.status == "ACTIVE" and a.effective_from <= at < a.effective_to]


def validate_exercise(ex: Exercise, readiness: bool = True) -> list[dict]:
    issues: list[dict] = []
    def issue(gate, text, severity="ERROR"):
        issues.append({"gate": gate, "severity": severity, "message": text})
    role_ids = {r.id for r in ex.roles}
    person_ids = {p.id for p in ex.persons}
    available = {p.id for p in ex.persons if p.available}
    roles = {r.id: r for r in ex.roles}
    statutory_departments = {"field_officer": "현장지휘부", "resource_officer": "자원지원부", "communications_officer": "현장지휘부", "safety_officer": "현장지휘부", "situation_officer": "대응계획부", "medical_officer": "현장지휘부"}
    if ex.organization_type != "CUSTOM" and not ({"incident_commander"} | set(statutory_departments)) <= role_ids:
        issue("G1", "법령 기본 조직의 지휘대장·6개 요원 정의가 누락되었습니다. 기관 커스텀은 별도 구분하세요.")
    if ex.organization_type == "CONTROL_GROUP" and not ex.organization_approval:
        issue("G1", "통제단 시작 편성은 기관 승인 편성·지휘관계 참조가 필요합니다.")
    if len(role_ids) != len(ex.roles):
        issue("G1", "중복 역할 ID")
    if len(person_ids) != len(ex.persons):
        issue("G2", "중복 참석자 ID")
    for role in ex.roles:
        if role.id in statutory_departments and not role.department.startswith(statutory_departments[role.id]):
            issue("G1", f"{role.name}: 제16조제3항 기본 배치 부서와 모순됩니다.")
        if any(not t.strip() for t in role.tasks):
            issue("G1", f"{role.name}: 빈 핵심 임무")
        if role.reports_to and role.reports_to not in role_ids:
            issue("G1", f"{role.name}: 존재하지 않는 보고 대상")
        seen = {role.id}
        parent = role.reports_to
        while parent in roles:
            if parent in seen:
                issue("G1", f"{role.name}: 보고체계 순환")
                break
            seen.add(parent)
            parent = roles[parent].reports_to
    active = active_assignments(ex)
    if ex.practice_owner_person_id and (ex.mode != "SOLO" or len(active) != 1 or active[0].person_id != ex.practice_owner_person_id):
        issue("G2", "개인 연습은 소유 참가자 한 명의 배치만 허용합니다.")
    if len({a.id for a in ex.assignments}) != len(ex.assignments):
        issue("G2", "중복 배치 ID")
    for a in ex.assignments:
        if a.role_id not in role_ids or a.person_id not in person_ids or any(p not in person_ids for p in a.backups):
            issue("G2", f"{a.id}: 역할/담당자/대체자 참조 누락")
    for i, a in enumerate(ex.assignments):
        for b in ex.assignments[i + 1:]:
            if a.status != "ENDED" and b.status != "ENDED" and max(a.effective_from, b.effective_from) < min(a.effective_to, b.effective_to):
                if a.person_id == b.person_id or a.role_id == b.role_id:
                    issue("G2", f"{a.id}/{b.id}: 근무기간 겹침·겸임 위험")
    for a in active:
        if a.person_id not in available:
            issue("G2", f"{a.role_id}: 담당자 부재, 대체 인계 필요")
        if not a.backups:
            issue("G2", f"{a.role_id}: 대체자 미지정", "WARNING")
    for r in ex.roles:
        assigned = [a for a in active if a.role_id == r.id]
        if r.critical and not assigned:
            if ex.mode in ("SOLO", "PARTIAL") and r.id in ex.simulated_roles:
                issue("G2", f"{r.name}: 명시적 모의요원", "WARNING")
            else:
                issue("G2", f"{r.name}: 핵심 역할 미배정")
    if ex.mode == "GROUP" and len({a.person_id for a in active}) < 4:
        issue("G2", "1~3명은 전체 조직훈련으로 실행할 수 없습니다. 부분/개인 모드를 선택하세요.")
    if readiness:
        for a in active:
            key = f"{a.person_id}:{a.role_id}"
            record = ex.readiness.get(key, {})
            role = roles.get(a.role_id)
            valid = role and record.get("acknowledged_version") == role.version and record.get("score", -1) >= ex.pass_score and ex.reviews.get(key, {}).get("approved")
            if not valid:
                issue("G3", f"{a.person_id}/{a.role_id}: 열람·상황형 문항·구두 확인 미완료", "WARNING" if ex.mode == "DIAGNOSTIC" or ex.practice_owner_person_id else "ERROR")
    subject = ex.subject
    buildings = {b.id: b for b in subject.buildings}
    features = {f.id: f for f in subject.features}
    if len(buildings) != len(subject.buildings) or len(features) != len(subject.features):
        issue("G5", "중복 건물/공간 ID")
    for f in subject.features:
        if f.building_id and (f.building_id not in buildings or f.floor > buildings[f.building_id].floors or f.floor < -buildings[f.building_id].basement_floors):
            issue("G5", f"{f.id}: 건물·층 참조 오류")
        if f.kind in INTERIOR_KINDS and (not f.building_id or f.floor == 0):
            issue('G5',f'{f.id}: 내부 요소에는 건물과 지상/지하 층 참조가 필요합니다.')
        if f.kind == 'PASSAGE' and (f.linked_building_id not in buildings or f.linked_building_id == f.building_id):
            issue('G5',f'{f.id}: 연결통로의 다른 대상 건물을 확인하세요.')
        if any(not valid_state_value(k,value) for k,value in f.state.items()):
            issue("G5", f"{f.id}: 허용되지 않은 초기 상태의 필드·형식·범위")
        if f.data_origin=='REFERENCE' and not any(layer.id==f.source_layer_id for layer in subject.external_layers):
            issue('G5',f'{f.id}: 외부 참조시설의 출처 계층이 없습니다.')
    if subject.source.rights != "approved":
        issue("G5", "자료 권리 미확인 또는 공개제한 — 발행 차단")
    if len({layer.id for layer in subject.external_layers})!=len(subject.external_layers):
        issue('G5','중복 외부 자료 계층 ID')
    for layer in subject.external_layers:
        if layer.source.rights!='approved' or not layer.source.reviewer:
            issue('G5',f'{layer.id}: 외부 자료의 권리·검토 기록이 필요합니다.')
        if layer.provider in {'building_registry','hydrant'} and layer.source.classification!='SYNTHETIC' and subject.target_mode=='VIRTUAL':
            issue('G5',f'{layer.id}: 실제 공간 속성을 가상 대상물로 표시할 수 없습니다.')
    if len({binding.id for binding in subject.asset_bindings})!=len(subject.asset_bindings):issue('G5','중복 자산 연결 ID')
    if sum(binding.manifest.triangles for binding in subject.asset_bindings)>500000:issue('G5','장면 모델 삼각형 총 예산50만 초과')
    if sum(binding.manifest.texture_pixels for binding in subject.asset_bindings if binding.purpose!='REFERENCE')>16777216:issue('G5','장면 모델/재질 텍스처 총 화소 예산 초과')
    for binding in subject.asset_bindings:
        building=buildings.get(binding.building_id)
        if not building or binding.source.rights!='approved' or not binding.source.reviewer:
            issue('G5',f'{binding.id}: 대상 건물·이용권·검토 기록이 필요합니다.')
            continue
        if binding.source.classification=='INTERNAL' and binding.visibility!='STAFF':issue('G5',f'{binding.id}: 내부 자산 공개 차단')
        if binding.purpose in ['MODEL','FACADE'] and binding.source.classification!='SYNTHETIC' and subject.target_mode=='VIRTUAL':issue('G5',f'{binding.id}: 실제 외관의 가상 표시 불일치')
        if binding.purpose=='MODEL':
            nodes={str(node.index) for node in binding.manifest.nodes}
            if set(binding.floor_map)!=nodes or not set(binding.object_map)<=nodes or any(floor>building.floors or floor < -building.basement_floors for floor in binding.floor_map.values()):issue('G5',f'{binding.id}: 모델의 층/객체 연결 오류')
            for node,feature_id in binding.object_map.items():
                feature=features.get(feature_id)
                if not feature or feature.building_id!=building.id or feature.floor!=binding.floor_map.get(node):issue('G5',f'{binding.id}: 객체·구역 연결 불일치')
    if subject.target_mode == "REAL" and (not subject.source.reviewer or subject.source.classification == "SYNTHETIC"):
        issue("G5", "실제 대상물은 자료 출처·검수자와 비합성 자료 구분이 필요합니다.")
    if subject.target_mode == "VIRTUAL" and (subject.map_context != "SYNTHETIC" or subject.model_accuracy != "SIMULATED"):
        issue("G5", "가상 대상물과 실제지도/실측 정확도 구분 불일치")
    if subject.target_mode == "VIRTUAL_ON_REAL_MAP" and subject.map_context != "REAL":
        issue("G5", "혼합 모드는 실지도 구분이 필요합니다.")
    if subject.scenario_factuality != "SIMULATED" and not subject.source.reviewer:
        issue("G5", "실제 사고 기록은 별도 승인·익명화 검수가 필요합니다.")
    if subject.model_accuracy == "VERIFIED" and subject.source.confidence != "verified":
        issue("G5", "검증 근거 없이 실측 모델로 표시할 수 없습니다.")
    if subject.interior_verified and (subject.source.confidence != "verified" or not subject.source.reviewer):
        issue("G5", "실내 검증 완료 표시는 근거·검수자가 필요합니다.")
    events = {e.id: e for e in ex.events}
    if len(events) != len(ex.events):
        issue("G4", "중복 사건 ID")
    if ex.start_event_id not in events:
        issue("G4", "시작 사건이 없습니다.")
    for e in ex.events:
        cue_bindings=set()
        for cue in e.media_cues:
            binding=next((item for item in subject.asset_bindings if item.id==cue.binding_id),None)
            if cue.binding_id in cue_bindings:issue('G5',f'{e.id}: 한 사건에서 같은 영상 연결을 중복 사용할 수 없습니다.')
            cue_bindings.add(cue.binding_id)
            if not binding or binding.kind!='VIDEO' or binding.purpose!='VIDEO':
                issue('G5',f'{e.id}: 검사/검토한 영상 연결이 없습니다.')
                continue
            if cue.feature_id not in features or features[cue.feature_id].building_id!=binding.building_id:issue('G5',f'{e.id}: 영상과 장면 객체의 건물이 다릅니다.')
            if cue.clip_end_seconds>binding.manifest.duration_seconds:issue('G5',f'{e.id}: 영상 클립 범위를 벗어납니다.')
            if binding.visibility!='PUBLIC' or binding.source.classification=='INTERNAL':issue('G5',f'{e.id}: 진행·평가 전용 영상은 참가자 사건에 연결할 수 없습니다.')
        if any(r not in role_ids for r in e.recipient_role_ids):
            issue("G4", f"{e.id}: 존재하지 않는 수신 역할")
        if any(n not in events for n in e.next_event_ids):
            issue("G4", f"{e.id}: 존재하지 않는 후속 사건")
        if not e.next_event_ids and not e.terminal:
            issue("G4", f"{e.id}: 종료 조건이 없습니다.")
        if e.terminal and e.next_event_ids:
            issue("G4", f"{e.id}: 종료 사건에 후속 분기가 있습니다.")
        if not e.evaluation_links:
            issue("G8", f"{e.id}: 평가기준 누락")
        for patch in e.patches:
            if patch.feature_id not in features:
                issue("G5", f"{e.id}: 없는 구역 {patch.feature_id}")
            elif patch.field not in features[patch.feature_id].state:
                issue("G5", f"{e.id}: 초기 상태 필드가 없습니다.")
        t = e.trigger
        if t.auto_release and t.kind != "AT_TIME":
            issue("G4", f"{e.id}: 자동 공개는 사전 승인된 시간 사건만 허용")
        if t.kind == "ON_ACTION" and not t.action:
            issue("G4", f"{e.id}: 조치 조건 누락")
        if t.kind in ("ON_CONDITION", "ON_COMBINATION"):
            if not check_condition(t.condition):
                issue("G4", f"{e.id}: 허용되지 않은 조건식")
            else:
                def condition_refs(n):
                    return [n["feature_id"]] if "feature_id" in n else sum((condition_refs(c) for c in n["conditions"]), [])
                if any(f not in features for f in condition_refs(t.condition)):
                    issue("G4", f"{e.id}: 조건식의 공간 참조 오류")
    visited, stack = set(), set()
    def walk(eid):
        if eid in stack:
            issue("G4", f"{eid}: 순환 분기")
            return
        if eid in visited or eid not in events:
            return
        stack.add(eid)
        for nxt in events[eid].next_event_ids:
            walk(nxt)
        stack.remove(eid)
        visited.add(eid)
    walk(ex.start_event_id)
    if set(events) - visited:
        issue("G4", "도달 불가능한 사건: " + ", ".join(sorted(set(events) - visited)))
    if not any(events[eid].terminal for eid in visited):
        issue("G4", "도달 가능한 종료 사건이 없습니다.")
    return issues
