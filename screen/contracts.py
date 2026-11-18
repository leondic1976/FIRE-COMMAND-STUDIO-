"""Versioned screen scenarios. Values are visual cues, never hazard predictions."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Side = Literal['A', 'B', 'C', 'D']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)


class Source(Strict):
    name: str = Field(default='자체 제작 가상 현장', max_length=200)
    reference: str = Field(default='', max_length=500)
    accuracy: Literal['fictional', 'approximate', 'surveyed'] = 'fictional'
    rights: str = Field(default='자체 제작', max_length=200)


class Site(Strict):
    name: str = Field(default='가상 물류센터', min_length=1, max_length=120)
    address: str = Field(default='가상 훈련 부지 · 실제 주소 아님', max_length=240)
    latitude: float = Field(default=37.5, ge=-90, le=90)
    longitude: float = Field(default=127, ge=-180, le=180)
    front_bearing: float = Field(default=180, ge=0, lt=360)
    target_mode: Literal['VIRTUAL', 'APPROXIMATE', 'REAL'] = 'VIRTUAL'
    source: Source = Field(default_factory=Source)


class Building(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    name: str = Field(min_length=1, max_length=80)
    x: float = Field(ge=-200, le=200)
    z: float = Field(ge=-200, le=200)
    width: float = Field(default=40, ge=4, le=120)
    depth: float = Field(default=26, ge=4, le=120)
    floors: int = Field(default=3, ge=1, le=40, strict=True)
    floor_height: float = Field(default=4.4, ge=2.4, le=6)
    style: Literal['warehouse', 'office', 'apartment'] = 'warehouse'
    color: str = Field(default='#c5c9c5', pattern=r'^#[a-fA-F0-9]{6}$')
    model_asset_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    facade_assets: dict[Side, str] = Field(default_factory=dict)


class Entity(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    kind: Literal['fire', 'victim', 'engine', 'ladder', 'ambulance', 'command', 'hydrant', 'crew', 'cordon']
    label: str = Field(min_length=1, max_length=80)
    x: float = Field(default=0, ge=-250, le=250)
    z: float = Field(default=0, ge=-250, le=250)
    y: float = Field(default=0, ge=0, le=240)
    heading: float = Field(default=0, ge=0, lt=360)
    building_id: str | None = None
    floor: int = Field(default=1, ge=1, le=40, strict=True)
    side: Side = 'A'
    visible: bool = True
    smoke: int = Field(default=0, ge=0, le=4, strict=True)
    fire: int = Field(default=0, ge=0, le=4, strict=True)
    status: Literal['standby', 'active', 'waiting', 'rescued', 'unknown', 'unavailable'] = 'standby'
    spraying: bool = False
    target_id: str | None = None


class Weather(Strict):
    wind_degrees: float = Field(default=65, ge=0, lt=360)
    wind_speed: float = Field(default=2.5, ge=0, le=20)
    rain: float = Field(default=0, ge=0, le=1)
    daylight: float = Field(default=1, ge=.15, le=1)
    fog: float = Field(default=.12, ge=0, le=1)


class EntityPatch(Strict):
    visible: bool | None = None
    smoke: int | None = Field(default=None, ge=0, le=4, strict=True)
    fire: int | None = Field(default=None, ge=0, le=4, strict=True)
    spraying: bool | None = None
    status: Literal['standby', 'active', 'waiting', 'rescued', 'unknown', 'unavailable'] | None = None
    x: float | None = Field(default=None, ge=-250, le=250)
    z: float | None = Field(default=None, ge=-250, le=250)


class Patch(Strict):
    entities: dict[str, EntityPatch] = Field(default_factory=dict)
    weather: Weather | None = None
    damage: dict[str, int] = Field(default_factory=dict)
    water: bool | None = None
    power: bool | None = None

    @model_validator(mode='after')
    def bounds(self):
        if any(type(value) is not int or not 0 <= value <= 3 for value in self.damage.values()):
            raise ValueError('손상 연출은0~3 정수입니다.')
        return self


class ScenarioEvent(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    at_seconds: int = Field(ge=60, le=10800, strict=True)
    catalog_id: str = Field(max_length=40)
    title: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1200)
    source_label: str = Field(default='가상 현장 보고', min_length=1, max_length=100)
    certainty: Literal['fictional', 'unverified', 'confirmed'] = 'fictional'
    priority: Literal['info', 'attention', 'urgent'] = 'attention'
    side: Side = 'A'
    patch: Patch = Field(default_factory=Patch)
    private_prompt: str = Field(default='', max_length=2000)


class Scenario(Strict):
    schema_version: int = Field(default=1, ge=1, le=1, strict=True)
    id: str = Field(default='scenario-new', pattern=r'^[A-Za-z0-9_-]{1,60}$')
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default='', max_length=2000)
    mode: Literal['auto', 'confirm'] = 'auto'
    site: Site = Field(default_factory=Site)
    buildings: list[Building] = Field(min_length=1, max_length=24)
    entities: list[Entity] = Field(default_factory=list, max_length=96)
    weather: Weather = Field(default_factory=Weather)
    events: list[ScenarioEvent] = Field(min_length=1, max_length=120)
    duration_seconds: int = Field(default=900, ge=120, le=10860, strict=True)

    @model_validator(mode='after')
    def references_and_timing(self):
        buildings = {item.id: item for item in self.buildings}
        entities = {item.id: item for item in self.entities}
        if len(buildings) != len(self.buildings) or len(entities) != len(self.entities):
            raise ValueError('건물/배치 ID가 중복됐습니다.')
        if sum(b.floors * (b.width + b.depth) for b in self.buildings) > 18000:
            raise ValueError('건물 상세 예산을 초과합니다. 건물/층수를 줄이세요.')
        for item in self.entities:
            if item.building_id and (item.building_id not in buildings or item.floor > buildings[item.building_id].floors):
                raise ValueError('배치의 건물/층 참조를 확인하세요.')
            if item.target_id and item.target_id not in entities:
                raise ValueError('방수 대상 참조를 확인하세요.')
        previous = 0
        ids = set()
        for event in self.events:
            if event.id in ids or event.at_seconds - previous < 60:
                raise ValueError('사건 ID는 고유해야 하고 시간 간격은 최소60초입니다.')
            if set(event.patch.entities) - entities.keys() or set(event.patch.damage) - buildings.keys():
                raise ValueError('사건의 배치/건물 참조를 확인하세요.')
            ids.add(event.id)
            previous = event.at_seconds
        if self.duration_seconds < previous + 60:
            raise ValueError('마지막 사건 뒤 최소60초의 토론 시간을 두세요.')
        return self
