"""Opt-in sandbox integration against a synthetic local provider fixture only."""
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.getenv('RUN_VWORLD_BROWSER_TESTS') != '1', reason='Opt-in isolated synthetic VWorld QA')
BASE = 'http://127.0.0.1:8093'
OUT = Path('artifacts/screen/vworld-browser')


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        engine = os.getenv('BROWSER_ENGINE', 'chromium')
        assert engine in ['chromium', 'firefox']
        browser = getattr(p, engine).launch(headless=os.getenv('SCREEN_BROWSER_HEADED') != '1')
        yield browser
        browser.close()


def prepare(context):
    assert context.request.post(BASE + '/api/v1/auth/demo', data={'profile': 'facilitator'}).ok
    value = json.loads((Path(__file__).parents[1] / 'data/warehouse.json').read_text(encoding='utf-8'))
    value['site'].update(map_provider='vworld', target_mode='APPROXIMATE')
    value['title'] = '가상 브이월드 검증 ' + uuid4().hex[:6]
    value['events'][0]['private_prompt'] = 'PRIVATE_FUTURE_VWORLD_SENTINEL'
    imported = context.request.post(BASE + '/api/screen/scenarios/import', multipart={'file': {'name': 'synthetic.json', 'mimeType': 'application/json', 'buffer': json.dumps(value).encode()}}, headers={'Idempotency-Key': uuid4().hex})
    assert imported.status == 201
    scenario_id = imported.json()['id']
    created = context.request.post(BASE + '/api/screen/runs', data={'scenario_id': scenario_id}, headers={'Idempotency-Key': uuid4().hex})
    assert created.status == 201
    return scenario_id, created.json()['id']


def fixture_routes(context, fail=False):
    external = []
    def route(request):
        url = urlsplit(request.request.url)
        if request.request.url.startswith(BASE + '/'):
            request.continue_()
        elif url.scheme == 'https' and url.hostname == 'map.vworld.kr' and url.path == '/js/webglMapInit.js.do':
            if fail: request.abort()
            else: request.fulfill(content_type='application/javascript', body=Path(__file__).with_name('vworld_sdk_fixture.js').read_text(encoding='utf-8'))
        else:
            external.append(url.hostname)
            request.abort()
    context.route('**/*', route)
    return external


def test_real_minute_overlay_uses_isolated_camera_and_never_shares_training_arrays(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1600, 'height': 1000})
    external = fixture_routes(context)
    _, run_id = prepare(context)
    page = context.new_page(); errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE)
    page.get_by_role('combobox', name='훈련 실행본 선택', exact=True).select_option(run_id)
    expect(page.locator('.vworld-scene[data-renderer="vworld"]')).to_be_visible(timeout=25000)
    expect(page.locator('.vworld-overlay canvas')).to_be_visible()
    map_frame = page.frame_locator('iframe[title="브이월드3D 지도"]')
    expect(map_frame.get_by_text('합성 SDK FIXTURE · 실제 지도 아님', exact=True)).to_be_visible()
    assert page.locator('iframe').get_attribute('sandbox') == 'allow-scripts'
    caption = page.locator('.vworld-caption').bounding_box()
    watermark = page.locator('.training-watermark').bounding_box()
    logo = map_frame.get_by_text('합성 SDK FIXTURE · 실제 지도 아님', exact=True).bounding_box()
    assert caption['height'] < 80 and caption['y'] + caption['height'] <= watermark['y']
    assert watermark['y'] + watermark['height'] <= logo['y']

    started = time.monotonic()
    page.get_by_role('button', name='훈련 시작', exact=True).click()
    page.wait_for_timeout(52000)
    assert page.locator('.situation-message').count() == 0
    expect(page.locator('.situation-message')).to_have_count(1, timeout=25000)
    waited = time.monotonic() - started
    assert waited >= 59.5
    page.get_by_role('button', name='일시정지', exact=True).click()
    for side in ['B', 'C', 'D', 'A']:
        page.get_by_role('button', name=side + (' 전면' if side == 'A' else ' 후면' if side == 'C' else ' 측면'), exact=True).click()
        page.wait_for_timeout(150)
    target = page.frames[1]
    received = target.evaluate('window.__received')
    assert all(set(item['viewport']) == {'latitude', 'longitude', 'position', 'target'} for item in received if item.get('kind') == 'viewport')
    serialized = json.dumps(received)
    assert all(word not in serialized for word in ['PRIVATE_FUTURE', 'victim-a', 'entities', 'events', 'notes'])
    assert target.evaluate('(()=>{try{void parent.document.body;return false}catch{return true}})()')
    assert target.evaluate('(()=>{try{void document.cookie;return false}catch{return true}})()')
    assert target.evaluate('async()=>{try{await fetch("/api/screen/runs",{credentials:"include"});return false}catch{return true}}')
    assert len(target.evaluate('window.__cameraViews')) >= 4
    with context.expect_page() as opened:
        page.get_by_role('button', name='공용화면', exact=True).click()
    public = opened.value
    expect(public.locator('.vworld-scene[data-renderer="vworld"]')).to_be_visible(timeout=25000)
    expect(public.locator('.situation-message')).to_have_count(1)
    assert not public.locator('.control-bar').count()
    assert 'PRIVATE_FUTURE' not in public.locator('body').inner_text()
    page.screenshot(path=str(OUT / (os.getenv('BROWSER_ENGINE', 'chromium') + '-minute.png')), full_page=True)
    (OUT / (os.getenv('BROWSER_ENGINE', 'chromium') + '.json')).write_text(json.dumps({'engine': os.getenv('BROWSER_ENGINE', 'chromium'), 'version': browser.version, 'synthetic_sdk_only': True, 'live_provider_verified': False, 'wall_seconds_to_first_message': waited, 'private_parent_and_cookies_blocked': True, 'training_arrays_sent_to_sdk': False, 'page_errors': errors, 'unexpected_external_hosts': external}, indent=2), encoding='utf-8')
    assert not errors and not external
    context.close()


def test_provider_search_placement_and_mobile_json(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    fixture_routes(context)
    scenario_id, _ = prepare(context)
    page = context.new_page(); page.goto(BASE)
    page.get_by_role('combobox', name='훈련 실행본 선택', exact=True).select_option('')
    page.get_by_role('combobox', name='시나리오 선택', exact=True).select_option(scenario_id)
    page.get_by_role('button', name='현장 설정', exact=True).click()
    page.get_by_role('textbox', name='장소·주소 검색', exact=True).fill('가상 공공 건물')
    page.get_by_role('button', name='검색', exact=True).click()
    page.get_by_role('button', name='가상 브이월드 검색 건물', exact=False).click()
    expect(page.get_by_role('textbox', name='현장명', exact=True)).to_have_value('가상 브이월드 검색 건물')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.get_by_role('button', name='저장 후 닫기', exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    current = context.request.get(BASE + '/api/screen/scenarios/' + scenario_id).json()['scenario']['site']
    assert current['map_provider'] == 'vworld' and current['latitude'] == 37.5
    context.close()


def test_sdk_failure_keeps_current_map_without_fake_success(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    fixture_routes(context, fail=True)
    _, run_id = prepare(context)
    page = context.new_page(); page.goto(BASE + '/board/' + run_id)
    expect(page.locator('.vworld-fallback')).to_be_visible(timeout=15000)
    expect(page.locator('.vworld-fallback')).to_contain_text('2D 현장 상태')
    expect(page.locator('.vworld-scene[data-renderer="vworld"]')).to_have_count(0)
    assert page.locator('.mini-map svg').count() == 1
    context.close()


def test_training_webgl_failure_does_not_loop_or_claim_provider_success(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    fixture_routes(context)
    context.add_init_script('const old=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...a){return String(t).startsWith("webgl")?null:old.call(this,t,...a)}')
    _, run_id = prepare(context)
    initial = context.request.get(BASE + '/api/screen/board/' + run_id).json()['scene']
    fire = next(e for e in initial['entities'] if e['kind'] == 'fire' and e['visible'])
    page = context.new_page(); page.goto(BASE + '/board/' + run_id)
    expect(page.locator('.vworld-fallback')).to_contain_text('훈련3D를 표시할 수 없어', timeout=20000)
    page.wait_for_timeout(800)
    expect(page.locator('.vworld-scene[data-renderer="vworld"]')).to_have_count(0)
    expect(page.locator('.vworld-fallback')).to_contain_text(f"연기 {fire['smoke']}/화염 {fire['fire']}")
    assert page.locator('iframe').count() == 1
    context.close()
