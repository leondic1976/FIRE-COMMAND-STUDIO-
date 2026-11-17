"""Bounded public-data adapters. Approval and credentials are server-side only."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from datetime import datetime
from typing import Literal
from urllib.parse import quote, unquote

import httpx
from pydantic import Field, SecretStr, model_validator
from defusedxml import ElementTree

from .domain import Contract, Source, ExternalFact, utcnow

MAX_RESPONSE = 2 * 1024 * 1024
ProviderId = Literal['building_registry', 'weather', 'hydrant']


class ProviderFailure(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


class ParcelQuery(Contract):
    sigunguCd: str = Field(pattern=r'^\d{5}$')
    bjdongCd: str = Field(pattern=r'^\d{5}$')
    platGbCd: Literal['0', '1', '2'] = '0'
    bun: str = Field(pattern=r'^\d{4}$')
    ji: str = Field(default='0000', pattern=r'^\d{4}$')
    page: int = Field(default=1, ge=1, le=100)
    per_page: int = Field(default=100, ge=1, le=100)


class WeatherQuery(Contract):
    base_date: str = Field(pattern=r'^\d{8}$')
    base_time: str = Field(pattern=r'^\d{2}00$')
    nx: int = Field(ge=1, le=149)
    ny: int = Field(ge=1, le=253)

    @model_validator(mode='after')
    def valid_time(self):
        datetime.strptime(self.base_date + self.base_time, '%Y%m%d%H%M')
        return self


class HydrantQuery(Contract):
    page: int = Field(default=1, ge=1, le=1000)
    per_page: int = Field(default=100, ge=1, le=100)


class ExternalQuery(Contract):
    provider: ProviderId
    query: ParcelQuery | WeatherQuery | HydrantQuery

    @model_validator(mode='after')
    def matching_query(self):
        expected = {'building_registry': ParcelQuery, 'weather': WeatherQuery, 'hydrant': HydrantQuery}
        if not isinstance(self.query, expected[self.provider]):
            raise ValueError('공급자와 조회 조건이 맞지 않습니다.')
        return self


class ExternalSettings(Contract):
    approved: bool = False
    approval_reference: str = Field(default='', max_length=200)
    building_key: SecretStr = Field(default_factory=lambda: SecretStr(''))
    weather_key: SecretStr = Field(default_factory=lambda: SecretStr(''))
    hydrant_key: SecretStr = Field(default_factory=lambda: SecretStr(''))
    hydrant_path: str = ''
    hydrant_catalog_url: str = ''

    @classmethod
    def from_env(cls):
        return cls(approved=os.getenv('EXTERNAL_DATA_APPROVED') == 'true',
                   approval_reference=os.getenv('EXTERNAL_DATA_APPROVAL_REF', ''),
                   building_key=os.getenv('DATA_GOV_BUILDING_KEY', ''), weather_key=os.getenv('KMA_SERVICE_KEY', ''),
                   hydrant_key=os.getenv('DATA_GOV_HYDRANT_KEY', ''), hydrant_path=os.getenv('HYDRANT_DATASET_PATH', ''),
                   hydrant_catalog_url=os.getenv('HYDRANT_CATALOG_URL',''))


ExternalRecord = ExternalFact


class ExternalBatch(Contract):
    provider: ProviderId
    source: Source
    retrieved_at: str
    raw_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    records: list[ExternalRecord] = Field(max_length=100)
    total_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list, max_length=30)


class _SecretFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.values = set()

    def add(self, value):
        if value:
            self.values.update({value, unquote(value), quote(unquote(value), safe='')})

    def clean(self, value: str):
        value = re.sub(r'(?i)(servicekey|authkey|apikey)=([^&\s\"<>]+)', r'\1=[REDACTED]', value)
        for secret in sorted(self.values, key=len, reverse=True):
            value = value.replace(secret, '[REDACTED]')
        return value

    def filter(self, record):
        record.msg = self.clean(record.getMessage())
        record.args = ()
        return True


_redactor = _SecretFilter()
for _logger in ('httpx', 'httpcore', 'httpcore.connection', 'httpcore.http11', 'httpcore.http2', 'httpcore.proxy', 'httpcore.socks_proxy'):
    logging.getLogger(_logger).addFilter(_redactor)


def _text(value, limit=200):
    if value is None:
        return ''
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ProviderFailure('SCHEMA', '공급자 응답의 문자열 필드가 올바르지 않습니다.')
    value = str(value).strip()
    if len(value) > limit or any(ord(c) < 32 and c not in '\t\r\n' for c in value):
        raise ProviderFailure('SCHEMA', '공급자 응답의 문자열 길이·문자 제한을 초과했습니다.')
    return value


def _number(value, low, high, integer=False):
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        raise ProviderFailure('SCHEMA', '공급자 응답의 숫자 필드가 올바르지 않습니다.')
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ProviderFailure('SCHEMA', '공급자 응답의 숫자 필드가 올바르지 않습니다.') from None
    if not math.isfinite(number) or not low <= number <= high or integer and not number.is_integer():
        raise ProviderFailure('SCHEMA', '공급자 응답의 숫자 범위가 올바르지 않습니다.')
    return int(number) if integer else number


def _items(data):
    try:
        response = data['response']
        code = str(response['header']['resultCode']).strip()
        if code == '03':
            return [], 0
        if code not in {'00', '0'}:
            raise ProviderFailure('UPSTREAM_AUTH' if code in {'20', '22', '30', '31', '32'} else 'UPSTREAM', '제공처가 요청을 승인하지 않았습니다. 키·할당량·제공 상태를 확인하세요.')
        body = response['body']
        items = body.get('items') or {}
        items = items.get('item', []) if isinstance(items, dict) else items
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError()
        total = _number(body.get('totalCount', len(items)), 0, 100_000_000, True)
        if total is None:
            raise ValueError()
        return items, total
    except ProviderFailure:
        raise
    except (KeyError, TypeError, ValueError):
        raise ProviderFailure('SCHEMA', '공급자 응답 구조가 계약과 다릅니다.') from None


class PublicDataRegistry:
    def __init__(self, settings: ExternalSettings | None = None, transport=None):
        self.settings = settings or ExternalSettings.from_env()
        self.transport = transport
        for key in (self.settings.building_key, self.settings.weather_key, self.settings.hydrant_key):
            _redactor.add(key.get_secret_value())

    def status(self, provider: ProviderId):
        key = getattr(self.settings, {'building_registry': 'building_key', 'weather': 'weather_key', 'hydrant': 'hydrant_key'}[provider]).get_secret_value()
        approved = self.settings.approved and bool(self.settings.approval_reference.strip())
        valid_key = bool(re.fullmatch(r'[A-Za-z0-9+/=._-]{8,1024}', unquote(key)))
        path_match = re.fullmatch(r'/api/([0-9]{8})/v1/(?:uddi:)?[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}', self.settings.hydrant_path)
        catalog_match = re.fullmatch(r'https://www\.data\.go\.kr/data/([0-9]{8})/(?:fileData|openapi|standard)\.do',self.settings.hydrant_catalog_url)
        valid_dataset = bool(path_match and catalog_match and path_match[1]==catalog_match[1])
        configured = valid_key and (provider != 'hydrant' or valid_dataset)
        return {'id': provider, 'implemented': True, 'available': approved and configured,
                'live_verified': False, 'reason': '수집 후 출처·항목 검토 필요' if approved and configured else '서버 승인 참조·인증키·제공 경로 설정 필요'}

    async def capabilities(self):
        return ['building_title', 'weather_observation', 'hydrant_candidates', 'review_before_apply', 'offline_fallback']

    async def validate_access(self):
        return [self.status(provider) for provider in ('building_registry', 'weather', 'hydrant')]

    async def _request(self, url, params):
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(8, connect=3),
                                         follow_redirects=False, trust_env=False,
                                         headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'}) as client:
                async with client.stream('GET', url, params=params) as response:
                    if response.status_code != 200:
                        raise ProviderFailure('UPSTREAM', '제공처 응답 오류입니다. 로컬 자료로 계속할 수 있습니다.')
                    if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                        raise ProviderFailure('FORMAT', '제공처의 예상하지 않은 압축 응답을 차단했습니다.')
                    content = bytearray()
                    if response.is_stream_consumed:
                        content.extend(response.content)
                    else:
                        async for chunk in response.aiter_raw():
                            content.extend(chunk)
                            if len(content) > MAX_RESPONSE:
                                raise ProviderFailure('TOO_LARGE', '공급자 응답 크기 제한을 초과했습니다.')
                    if len(content) > MAX_RESPONSE:
                        raise ProviderFailure('TOO_LARGE', '공급자 응답 크기 제한을 초과했습니다.')
            raw = bytes(content)
            try:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                # Government gateways can return XML errors despite JSON requests.
                try:
                    ElementTree.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                except Exception:
                    raise ProviderFailure('FORMAT', '제공처 응답 형식을 해석할 수 없습니다.') from None
                raise ProviderFailure('UPSTREAM_AUTH', '제공처가 JSON 자료 대신 오류 응답을 반환했습니다. 인증 설정을 확인하세요.') from None
            return value, hashlib.sha256(raw).hexdigest()
        except httpx.TimeoutException:
            raise ProviderFailure('TIMEOUT', '제공처 응답 시간이 초과됐습니다. 로컬 자료로 계속할 수 있습니다.') from None
        except httpx.HTTPError:
            raise ProviderFailure('NETWORK', '제공처에 연결할 수 없습니다. 로컬 자료로 계속할 수 있습니다.') from None

    async def fetch(self, request: ExternalQuery) -> ExternalBatch:
        provider, query = request.provider, request.query
        if not self.status(provider)['available']:
            raise ProviderFailure('DISABLED', '기관 승인·인증·제공 경로 설정 전 외부 수집은 비활성입니다.')
        key_name = {'building_registry': 'building_key', 'weather': 'weather_key', 'hydrant': 'hydrant_key'}[provider]
        key = unquote(getattr(self.settings, key_name).get_secret_value())
        if provider == 'building_registry':
            params = query.model_dump(exclude={'page', 'per_page'}) | {'pageNo': query.page, 'numOfRows': query.per_page, '_type': 'json', 'serviceKey': key}
            data, digest = await self._request('https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo', params)
            rows, total = _items(data)
            records = self._buildings(rows)
            source_url, label = 'https://www.data.go.kr/data/15134735/openapi.do', '국토교통부 건축HUB 건축물대장 표제부'
            warnings = ['대장 속성은 실내 구조·도면·실측 외관을 제공하지 않습니다. 좌표·치수·현황을 별도 확인하세요.']
        elif provider == 'weather':
            params = query.model_dump() | {'pageNo': 1, 'numOfRows': 100, 'dataType': 'JSON', 'serviceKey': key}
            data, digest = await self._request('https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst', params)
            rows, total = _items(data)
            records = self._weather(rows, query)
            source_url, label = 'https://www.data.go.kr/data/15084084/openapi.do', '기상청 초단기실황 · 출처표시'
            warnings = ['대표 관측 격자의 과거 실황 참조이며 개별 건물의 현재 현장 기상·화재 확산 예측이 아닙니다.']
        else:
            params = {'page': query.page, 'perPage': query.per_page, 'returnType': 'JSON', 'serviceKey': key}
            data, digest = await self._request('https://api.odcloud.kr' + self.settings.hydrant_path, params)
            rows = data.get('data')
            if not isinstance(rows, list) or len(rows) > 100:
                raise ProviderFailure('SCHEMA', '소방용수 제공처 응답 구조가 계약과 다릅니다.')
            total = _number(data.get('totalCount', len(rows)), 0, 100_000_000, True)
            if total is None:
                raise ProviderFailure('SCHEMA', '소방용수 전체 건수가 올바르지 않습니다.')
            records = self._hydrants(rows)
            dataset = self.settings.hydrant_path.split('/')[2]
            source_url, label = self.settings.hydrant_catalog_url, '공공데이터포털 소방용수시설 후보 · 자료 '+dataset
            warnings = ['옥외 시설 위치·속성 후보입니다. 현재 사용 가능 여부·수압·옥내 소화전을 보증하지 않습니다.']
        if len({record.external_id for record in records}) != len(records):
            raise ProviderFailure('SCHEMA', '공급자 응답의 식별자가 중복됩니다.')
        if not records:
            warnings.append('조회된 자료가 없습니다. 조건·기준일을 확인하거나 수동 입력하세요.')
        # Only normalized, allowlisted fields leave this module; no raw body or keys.
        records = [record.model_copy(update={'external_id': _redactor.clean(record.external_id), 'name': _redactor.clean(record.name),
                   'fields': {k: _redactor.clean(v) if isinstance(v, str) else v for k, v in record.fields.items()}}) for record in records]
        as_of = records[0].fields['observed_at'] if provider == 'weather' and records else '기준일은 항목별 확인 · 수집시각과 구분'
        return ExternalBatch(provider=provider, source=Source(provider=label, as_of=as_of,
                              rights='unknown', confidence='unverified', classification='PUBLIC', url=source_url),
                             retrieved_at=utcnow(), raw_sha256=digest, records=records, total_count=total, warnings=warnings)

    @staticmethod
    def _buildings(rows):
        records = []
        for row in rows:
            if not isinstance(row, dict) or not row.get('mgmBldrgstPk'):
                raise ProviderFailure('SCHEMA', '건축물대장 식별자 필드가 없습니다.')
            id = _text(row['mgmBldrgstPk'], 120)
            fields = {target: _text(row.get(key)) for target, key in {
                'address': 'platPlc', 'road_address': 'newPlatPlc', 'use': 'mainPurpsCdNm',
                'structure': 'strctCdNm', 'approval_date': 'useAprDay', 'source_date': 'crtnDay'}.items()}
            fields.update(floors_above=_number(row.get('grndFlrCnt'), 0, 1000, True), floors_below=_number(row.get('ugrndFlrCnt'), 0, 100, True),
                          height_m=_number(row.get('heit'), 0, 2000), footprint_area_m2=_number(row.get('archArea'), 0, 1e8), total_area_m2=_number(row.get('totArea'), 0, 1e10))
            records.append(ExternalRecord(external_id=id, name=_text(row.get('bldNm') or row.get('dongNm') or id), fields=fields))
        return records

    @staticmethod
    def _weather(rows, query):
        descriptions = {'T1H': ('기온', '℃', -100, 70), 'RN1': ('1시간 강수량', 'mm', 0, 1000), 'REH': ('습도', '%', 0, 100),
                        'WSD': ('풍속', 'm/s', 0, 200), 'VEC': ('풍향', '°', 0, 360), 'UUU': ('동서 바람성분', 'm/s', -200, 200),
                        'VVV': ('남북 바람성분', 'm/s', -200, 200), 'PTY': ('강수형태 코드', '코드', 0, 9)}
        records = []
        for row in rows:
            if not isinstance(row, dict) or row.get('category') not in descriptions:
                raise ProviderFailure('SCHEMA', '기상 실황의 자료구분 코드가 계약과 다릅니다.')
            if str(row.get('baseDate')) != query.base_date or str(row.get('baseTime')).zfill(4) != query.base_time or _number(row.get('nx'),1,149,True) != query.nx or _number(row.get('ny'),1,253,True) != query.ny:
                raise ProviderFailure('SCHEMA', '기상 실황의 기준시각·격자가 요청과 다릅니다.')
            category = row['category']
            label, unit, low, high = descriptions[category]
            raw = _number(row.get('obsrValue'), -1000, max(1000, high))
            missing = raw is None or raw <= -900
            value = None if missing else _number(raw, low, high)
            records.append(ExternalRecord(external_id=category, name=label, fields={'category': category, 'value': value, 'unit': unit,
                'observed_at': datetime.strptime(query.base_date + query.base_time, '%Y%m%d%H%M').isoformat() + '+09:00',
                'nx': query.nx, 'ny': query.ny, 'missing': missing}))
        return records

    @staticmethod
    def _hydrants(rows):
        records = []
        for row in rows:
            if not isinstance(row, dict):
                raise ProviderFailure('SCHEMA', '소방용수 표준 컬럼이 없습니다.')
            id = _text(row.get('시설번호'), 120)
            latitude, longitude = _number(row.get('위도'), -90, 90), _number(row.get('경도'), -180, 180)
            if not id or latitude is None or longitude is None or latitude == longitude == 0:
                raise ProviderFailure('SCHEMA', '소방용수 시설번호·좌표가 없습니다.')
            records.append(ExternalRecord(external_id=id, name='용수시설 ' + id, fields={'latitude': latitude, 'longitude': longitude,
                'facility_type_code': _text(row.get('시설유형코드')), 'address': _text(row.get('소재지도로명주소') or row.get('소재지지번주소')),
                'source_date': _text(row.get('데이터기준일자')), 'reported_pressure': _text(row.get('출수압력')), 'availability': 'UNCONFIRMED'}))
        return records
