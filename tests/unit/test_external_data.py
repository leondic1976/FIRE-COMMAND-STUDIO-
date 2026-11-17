import copy
import json
import logging

import httpx
import pytest
from pydantic import ValidationError

from apps.api.external_data import ExternalQuery, ExternalSettings, PublicDataRegistry, ProviderFailure

KEY='synthetic-service-key+only/fixture='
PATH='/api/15000000/v1/uddi:11111111-2222-3333-4444-555555555555'


def settings(**changes):
    return ExternalSettings(approved=changes.pop('approved',True),approval_reference='합성 시험용 승인 설정. 기관 승인 아님.',
        building_key=changes.pop('building_key',KEY),weather_key=KEY,hydrant_key=KEY,
        hydrant_path=changes.pop('hydrant_path',PATH),hydrant_catalog_url=changes.pop('hydrant_catalog_url','https://www.data.go.kr/data/15000000/openapi.do'),**changes)


def query(provider='building_registry',**changes):
    values={'building_registry':{'sigunguCd':'11680','bjdongCd':'10300','bun':'0012'},
            'weather':{'base_date':'20261117','base_time':'0600','nx':60,'ny':127},'hydrant':{}}
    return ExternalQuery(provider=provider,query=values[provider]|changes)


def envelope(items):
    return {'response':{'header':{'resultCode':'00','resultMsg':'NORMAL_SERVICE'},
            'body':{'items':{'item':items},'totalCount':len(items) if isinstance(items,list) else 1}}}


BUILDING={'mgmBldrgstPk':'synthetic-building-01','bldNm':'가상자료_실제건물아님','grndFlrCnt':'4','ugrndFlrCnt':1,
          'heit':'16.2','archArea':500,'totArea':2000,'mainPurpsCdNm':'공장','strctCdNm':'철근콘크리트구조',
          'platPlc':'합성 주소 · 실제 대상물 아님','crtnDay':'20261101'}


def registry(payload,**options):
    return PublicDataRegistry(settings(**options),transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload)))


async def test_disabled_and_invalid_configuration_never_contacts_network():
    calls=[]
    for config in [ExternalSettings(),settings(approved=False),settings(building_key=''),settings(building_key='bad\ncredential')]:
        instance=PublicDataRegistry(config,transport=httpx.MockTransport(lambda request:calls.append(request)))
        with pytest.raises(ProviderFailure,match='비활성'):await instance.fetch(query())
    for path in ['http://127.0.0.1/internal','/api/15000000/v1/../../secret','/api/15000000/v1/uddi:bad']:
        with pytest.raises(ProviderFailure):await PublicDataRegistry(settings(hydrant_path=path)).fetch(query('hydrant'))
    assert not calls


async def test_building_singleton_normalization_and_exact_outbound_fields(caplog):
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json=envelope(BUILDING))
    from urllib.parse import quote
    instance=PublicDataRegistry(settings(building_key=quote(KEY,safe='')),transport=httpx.MockTransport(respond))
    with caplog.at_level(logging.DEBUG):result=await instance.fetch(query())
    assert result.records[0].fields['floors_above']==4
    assert result.records[0].fields['height_m']==16.2
    assert result.source.rights=='unknown' and result.source.confidence=='unverified'
    assert result.source.url=='https://www.data.go.kr/data/15134735/openapi.do'
    request=calls[0]
    assert request.url.host=='apis.data.go.kr' and request.url.path.endswith('/getBrTitleInfo')
    assert set(request.url.params)=={'serviceKey','sigunguCd','bjdongCd','platGbCd','bun','ji','pageNo','numOfRows','_type'}
    assert request.url.params['serviceKey']==KEY
    assert KEY not in caplog.text and quote(KEY,safe='') not in caplog.text
    assert 'service-key' not in result.model_dump_json()


async def test_weather_unit_time_grid_and_missing_value_are_distinct():
    rows=[{'category':kind,'baseDate':'20261117','baseTime':'0600','nx':'60','ny':127,'obsrValue':value}
          for kind,value in [('T1H','9.2'),('WSD','2.4'),('REH','-998')]]
    result=await registry(envelope(rows)).fetch(query('weather'))
    assert result.records[0].fields['unit']=='℃'
    assert result.records[1].fields['value']==2.4
    assert result.records[2].fields['value'] is None and result.records[2].fields['missing']
    assert result.source.as_of=='2026-11-17T06:00:00+09:00'
    rows[0]['nx']=61
    with pytest.raises(ProviderFailure):await registry(envelope(rows)).fetch(query('weather'))


async def test_hydrant_candidates_never_claim_current_water_availability():
    row={'시설번호':'SYNTHETIC-01','위도':'37.5','경도':'127.0','시설유형코드':'1','출수압력':'0.3MPa',
         '데이터기준일자':'2025-01-01','관할기관전화번호':'DROP-ME','unexpected_private':'DROP-ME'}
    result=await registry({'data':[row],'totalCount':1}).fetch(query('hydrant'))
    assert result.records[0].fields['availability']=='UNCONFIRMED'
    assert result.records[0].fields['latitude']==37.5
    assert 'DROP-ME' not in result.model_dump_json()
    assert result.source.rights=='unknown'
    assert result.source.url=='https://www.data.go.kr/data/15000000/openapi.do'


@pytest.mark.parametrize('url',['https://evil.example/data/15000000/openapi.do','https://www.data.go.kr/data/15000001/openapi.do','https://www.data.go.kr/data/15000000/openapi.do?redirect=secret'])
async def test_hydrant_catalogue_must_be_explicit_and_match_dataset(url):
    calls=[]
    instance=PublicDataRegistry(settings(hydrant_catalog_url=url),transport=httpx.MockTransport(lambda request:calls.append(request)))
    with pytest.raises(ProviderFailure):await instance.fetch(query('hydrant'))
    assert not calls


@pytest.mark.parametrize('invalid',[
    {'url':'http://169.254.169.254'}, {'sigunguCd':'../x'}, {'bun':'12'}, {'serviceKey':'exfiltrate'},
    {'page':0}, {'per_page':10000},
])
def test_query_forbids_urls_credentials_and_unbounded_requests(invalid):
    with pytest.raises(ValidationError):query(**invalid)


@pytest.mark.parametrize('changes',[{'base_date':'20260230'},{'base_time':'2460'},{'base_time':'0630'},{'nx':0},{'ny':254}])
def test_weather_invalid_time_and_grid(changes):
    with pytest.raises(ValidationError):query('weather',**changes)


@pytest.mark.parametrize('payload',[
    [],{'response':{}},envelope([{}]),envelope([BUILDING,BUILDING]),
    envelope([{**BUILDING,'grndFlrCnt':'NaN'}]),envelope([{**BUILDING,'heit':-1}]),
    {'response':{'header':{'resultCode':'30','resultMsg':KEY}}},
])
async def test_malformed_or_rejected_payload_is_controlled_and_secret_free(payload):
    with pytest.raises(ProviderFailure) as rejected:await registry(payload).fetch(query())
    assert KEY not in str(rejected.value)


async def test_empty_result_is_not_a_fabricated_building():
    result=await registry(envelope([])).fetch(query())
    assert not result.records and result.total_count==0 and len(result.warnings)>1


@pytest.mark.parametrize('mode',['redirect','timeout','network','oversize','gzip','xml','xxe'])
async def test_transport_errors_redirect_and_unsafe_responses_fail_closed(mode):
    calls=[]
    def response(request):
        calls.append(request)
        if mode=='timeout':raise httpx.ReadTimeout('secret URL '+KEY)
        if mode=='network':raise httpx.ConnectError('secret URL '+KEY)
        if mode=='redirect':return httpx.Response(302,headers={'Location':'http://127.0.0.1/secret?serviceKey='+KEY})
        if mode=='oversize':return httpx.Response(200,content=b'x'*(2*1024*1024+1))
        if mode=='gzip':return httpx.Response(200,headers={'Content-Encoding':'gzip'},content=b'\x1f\x8b')
        if mode=='xml':return httpx.Response(200,content=('<error>'+KEY+'</error>').encode())
        return httpx.Response(200,content=b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///secret">]><x>&a;</x>')
    instance=PublicDataRegistry(settings(),transport=httpx.MockTransport(response))
    with pytest.raises(ProviderFailure) as rejected:await instance.fetch(query())
    assert KEY not in str(rejected.value) and len(calls)==1


async def test_secret_echo_is_scrubbed_from_normalized_values():
    result=await registry(envelope([{**BUILDING,'bldNm':KEY}])).fetch(query())
    assert KEY not in result.model_dump_json() and result.records[0].name=='[REDACTED]'
