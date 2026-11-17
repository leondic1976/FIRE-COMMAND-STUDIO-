"""Actual browser error paths using an isolated synthetic-key build.

No provider traffic, real SDK or actual key/approval is used or claimed.
"""
import os
from pathlib import Path
from uuid import uuid4
import pytest

pytestmark=pytest.mark.skipif(os.getenv('RUN_MAP_BROWSER_TESTS')!='1',reason='Explicit isolated synthetic map QA fixture required')
BASE='http://127.0.0.1:8012'


@pytest.mark.parametrize('failure',['network','timeout','roadview_absent'])
def test_sdk_failure_preserves_local_scene_and_state(failure):
    from playwright.sync_api import sync_playwright,expect
    engine=os.getenv('BROWSER_ENGINE','chromium');assert engine in {'chromium','firefox'}
    Path('artifacts/browser').mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser=getattr(pw,engine).launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000})
        errors=[];sdk_requests=[];outside=[]
        def route_request(route):
            url=route.request.url
            if url.startswith(BASE+'/'):return route.continue_()
            if url.startswith('https://dapi.kakao.com/v2/maps/sdk.js?'):
                sdk_requests.append(True)
                if failure=='network':return route.abort()
                script='window.kakao={maps:{load:callback=>{}}};' if failure=='timeout' else 'window.kakao={maps:{load:callback=>callback(),LatLng:class{constructor(lat,lng){this.lat=lat;this.lng=lng;}},Roadview:class{},RoadviewClient:class{getNearestPanoId(center,radius,callback){callback(null);}}}};'
                return route.fulfill(status=200,content_type='application/javascript',body=script)
            outside.append(url.split('?')[0]);return route.abort()
        context.route('**/*',route_request)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            assert context.request.post(BASE+'/api/v1/auth/demo',data={'profile':'facilitator'}).ok
            created=context.request.post(BASE+'/api/v1/exercises',data={'template':'factory','name':'합성 지도 장애 QA '+uuid4().hex[:8]});assert created.ok
            ex=created.json();version=ex.pop('state_version');ex['subject'].update(target_mode='VIRTUAL_ON_REAL_MAP',map_context='REAL')
            saved=context.request.put(BASE+'/api/v1/exercises/'+ex['id'],data={'expected_state_version':version,'exercise':ex},headers={'Idempotency-Key':uuid4().hex});assert saved.ok,saved.text()
            page.goto(BASE);expect(page.get_by_role('heading',name='공동 상황판단 훈련',exact=True)).to_be_visible()
            page.get_by_label('훈련 선택',exact=True).select_option(ex['id'])
            expect(page.locator('.local-map')).to_be_visible()
            expect(page.get_by_role('button',name='카카오 지도',exact=True)).to_be_enabled()
            page.get_by_role('button',name='거리뷰' if failure=='roadview_absent' else '카카오 지도',exact=True).click()
            expected={'network':'인터넷·도메인·키 설정을 확인하세요.','timeout':'지도 SDK 연결이 지연되어','roadview_absent':'주변에 제공되는 로드뷰가 없습니다.'}[failure]
            expect(page.locator('.map-provider-error')).to_contain_text(expected,timeout=12000)
            expect(page.locator('.local-map')).to_be_visible()
            expect(page.locator('.scene-panel')).to_be_visible()
            assert page.locator('.building-strip button').count()==3
            page.locator('.building-strip button').filter(has_text='B02').click()
            expect(page.locator('.building-strip button.selected')).to_contain_text('B02')
            assert len(sdk_requests)==1 and not outside and not errors
            assert context.request.get(BASE+'/api/v1/exercises/'+ex['id']).json()['exercise']['subject']['target_mode']=='VIRTUAL_ON_REAL_MAP'
            page.screenshot(path=f'artifacts/browser/{engine}-map-{failure}.png',full_page=True)
        finally:context.close();browser.close()
