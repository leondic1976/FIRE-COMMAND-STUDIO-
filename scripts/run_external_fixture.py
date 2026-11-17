"""Loopback-only synthetic public-data UI fixture; no provider network requests.

Run: python -m scripts.run_external_fixture
Not a deployment entry point. All keys, observations and buildings are fictional.
"""
import os
import hashlib
from pathlib import Path

import httpx
import uvicorn

from apps.api.application import create_app
from apps.api.external_data import ExternalSettings
from tests.asset_fixtures import FixtureScanner
from apps.api.media_validation import MediaProcessor,MediaSettings


def envelope(items):
    return {'response': {'header': {'resultCode': '00'}, 'body': {'items': {'item': items}, 'totalCount': len(items)}}}


def reply(request):
    if request.url.host == 'api.odcloud.kr':
        return httpx.Response(200, json={'data': [
            {'시설번호': 'SYNTHETIC-H01', '시설유형코드': '1', '위도': 37.5001, '경도': 127.0002, '데이터기준일자': '2026-11-01'},
            {'시설번호': 'SYNTHETIC-H02', '시설유형코드': '1', '위도': 37.501, '경도': 127.002, '데이터기준일자': '2026-11-01'},
        ], 'totalCount': 2})
    if 'getUltraSrtNcst' in request.url.path:
        q=request.url.params
        return httpx.Response(200,json=envelope([{
            'baseDate': q['base_date'], 'baseTime': q['base_time'], 'nx': int(q['nx']), 'ny': int(q['ny']),
            'category': category, 'obsrValue': value,
        } for category,value in [('WSD','2.5'),('T1H','11.0')]]))
    return httpx.Response(200,json=envelope([{
        'mgmBldrgstPk': 'synthetic-building-01', 'bldNm': '합성 API 시험동 · 실제 건물 아님',
        'grndFlrCnt': 4, 'ugrndFlrCnt': 1, 'heit': 16.2, 'mainPurpsCdNm': '공장',
        'platPlc': '합성 주소 · 실제 위치 아님', 'crtnDay': '20261101',
    }]))


if __name__ == '__main__':
    os.environ['COOKIE_SECURE']='false'
    os.environ['ALLOWED_ORIGINS']='http://127.0.0.1:8011'
    Path('runtime').mkdir(exist_ok=True)
    key='synthetic-service-key+only/fixture='
    settings=ExternalSettings(approved=True,approval_reference='합성 UI 자동시험 설정. 기관 승인 아님.',
        building_key=key,weather_key=key,hydrant_key=key,
        hydrant_path='/api/15000000/v1/uddi:11111111-2222-3333-4444-555555555555',hydrant_catalog_url='https://www.data.go.kr/data/15000000/openapi.do')
    manifest=Path('runtime/tools/ffmpeg-9.0.2/bundle.json').resolve()
    media=MediaProcessor(MediaSettings(approved=True,approval_reference='SYNTHETIC LOCAL CODEC QA ONLY, NOT INSTITUTIONAL AV/HOST APPROVAL',host_isolation_confirmed=True,
        manifest_path=str(manifest),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())) if manifest.is_file() else MediaProcessor(MediaSettings())
    app=create_app('sqlite:///./runtime/external-fixture.db',True,external_settings=settings,external_transport=httpx.MockTransport(reply),asset_scanner=FixtureScanner(),media_processor=media)
    uvicorn.run(app,host='127.0.0.1',port=8011,access_log=False)
