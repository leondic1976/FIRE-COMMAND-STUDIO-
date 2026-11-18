"""Opt-in actual production build, with real sixty-second event timing."""
import json
import os
from pathlib import Path
import time
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.getenv('RUN_SCREEN_BROWSER_TESTS') != '1', reason='Opt-in loopback screen browser QA')
BASE = os.getenv('SCREEN_BROWSER_BASE', 'http://127.0.0.1:8090')
assert BASE in ('http://127.0.0.1:8090', 'http://127.0.0.1:8093')
OUT = Path('artifacts/screen/browser')


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    engine = os.getenv('BROWSER_ENGINE', 'chromium')
    assert engine in ('chromium', 'firefox')
    with sync_playwright() as p:
        headed = os.getenv('SCREEN_BROWSER_HEADED') == '1'
        browser = getattr(p, engine).launch(headless=not headed)
        (OUT / (engine + '-environment.json')).write_text(json.dumps({'engine': engine, 'version': browser.version,
            'headless': not headed, 'synthetic_only': True, 'real_user_profile_used': False}), encoding='utf-8')
        yield browser
        browser.close()


def prepare(context):
    assert context.request.post(BASE + '/api/v1/auth/demo', data={'profile': 'facilitator'}).ok
    scenario = json.loads((Path(__file__).parents[1] / 'data/warehouse.json').read_text(encoding='utf-8'))
    scenario['title'] = '합성 SCREEN 브라우저 ' + uuid4().hex[:6]
    imported = context.request.post(BASE + '/api/screen/scenarios/import', multipart={'file': {'name': 'synthetic.json', 'mimeType': 'application/json', 'buffer': json.dumps(scenario).encode()}}, headers={'Idempotency-Key': uuid4().hex})
    assert imported.status == 201, imported.text()
    scenario_id = imported.json()['id']
    created = context.request.post(BASE + '/api/screen/runs', data={'scenario_id': scenario_id}, headers={'Idempotency-Key': uuid4().hex})
    assert created.status == 201
    return scenario_id, created.json()['id']


def test_real_minute_scene_messages_pause_views_notes_and_public_isolation(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1600, 'height': 1000})
    scenario_id, id = prepare(context)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE)
    select = page.get_by_role('combobox', name='훈련 실행본 선택', exact=True)
    expect(select).to_be_visible()
    select.select_option(id)
    expect(page.locator('[data-renderer="3d"] canvas')).to_be_visible(timeout=20000)
    expect(page.get_by_role('button', name='훈련 시작', exact=True)).to_be_enabled()
    started = time.monotonic()
    page.get_by_role('button', name='훈련 시작', exact=True).click()
    expect(page.get_by_role('button', name='일시정지', exact=True)).to_be_visible()
    page.wait_for_timeout(52000)
    assert page.locator('.situation-message').count() == 0
    state = context.request.get(BASE + '/api/screen/board/' + id).json()
    assert 'victim-a' not in json.dumps(state) and not state['messages']
    expect(page.locator('.situation-message')).to_have_count(1, timeout=25000)
    waited = time.monotonic() - started
    assert waited >= 59.5
    state = context.request.get(BASE + '/api/screen/board/' + id).json()
    assert state['messages'][0]['elapsed'] >= 60
    assert next(e for e in state['scene']['entities'] if e['id'] == 'fire-a')['smoke'] == 3
    page.get_by_role('button', name='일시정지', exact=True).click()
    expect(page.get_by_role('button', name='재개', exact=True)).to_be_visible()
    first = context.request.get(BASE + '/api/screen/board/' + id).json()['elapsed']
    page.wait_for_timeout(1300)
    assert context.request.get(BASE + '/api/screen/board/' + id).json()['elapsed'] == first
    for side in ['B', 'C', 'D', 'A']:
        button = page.get_by_role('button', name=side + (' 전면' if side == 'A' else ' 후면' if side == 'C' else ' 측면'), exact=True)
        button.click()
        expect(button).to_have_attribute('aria-pressed', 'true')
    page.get_by_role('button', name='회의 기록', exact=True).click()
    page.get_by_role('textbox', name='회의 내용', exact=True).fill('PRIVATE_SCREEN_BROWSER_NOTE 합성 토론')
    page.get_by_role('button', name='기록 저장', exact=True).click()
    expect(page.locator('.notes-history')).to_contain_text('PRIVATE_SCREEN_BROWSER_NOTE')
    page.keyboard.press('Escape')
    with context.expect_page() as opened:
        page.get_by_role('button', name='공용화면', exact=True).click()
    public = opened.value
    expect(public.locator('.situation-message')).to_have_count(1)
    assert not public.locator('.control-bar').count()
    assert 'PRIVATE_SCREEN_BROWSER_NOTE' not in public.locator('body').inner_text()
    page.screenshot(path=str(OUT / (os.getenv('BROWSER_ENGINE', 'chromium') + '-minute.png')), full_page=True)
    (OUT / (os.getenv('BROWSER_ENGINE', 'chromium') + '-timing.json')).write_text(json.dumps({'wall_seconds_to_first_message': waited, 'server_elapsed': state['messages'][0]['elapsed'], 'minimum_interval': 60, 'page_errors': errors}), encoding='utf-8')
    assert not errors
    context.close()


def test_edit_placements_json_roundtrip_and_mobile_layout(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    scenario_id, id = prepare(context)
    page = context.new_page()
    page.goto(BASE)
    page.get_by_role('combobox', name='훈련 실행본 선택', exact=True).select_option('')
    page.get_by_role('combobox', name='시나리오 선택', exact=True).select_option(scenario_id)
    page.get_by_role('button', name='현장 설정', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.get_by_role('button', name='자원·화재 배치', exact=False).click()
    page.get_by_label('추가할 자원 종류').select_option('hydrant')
    page.get_by_role('button', name='자원 추가', exact=True).click()
    page.get_by_role('textbox', name='표시명', exact=True).fill('합성 소화전 추가')
    page.get_by_role('button', name='시나리오', exact=False).filter(has_text='시나리오').first
    with page.expect_download() as exported:
        page.get_by_role('button', name='JSON 저장', exact=True).click()
    destination = OUT / (os.getenv('BROWSER_ENGINE', 'chromium') + '-scenario.json')
    exported.value.save_as(destination)
    value = json.loads(destination.read_text(encoding='utf-8'))
    assert any(e['label'] == '합성 소화전 추가' for e in value['entities'])
    assert all(b['model_asset_id'] is None for b in value['buildings'])
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.get_by_role('button', name='저장 후 닫기', exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=str(OUT / (os.getenv('BROWSER_ENGINE', 'chromium') + '-mobile.png')), full_page=True)
    context.close()


def test_webgl_failure_has_current_map_and_keyboard_controls(browser):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    _, id = prepare(context)
    context.add_init_script('const old=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...a){return String(t).startsWith("webgl")?null:old.call(this,t,...a)}')
    page = context.new_page()
    page.goto(BASE + '/board/' + id)
    expect(page.locator('[data-renderer="2d"]')).to_be_visible(timeout=20000)
    expect(page.get_by_text('2D 현장 상태', exact=True)).to_be_visible()
    assert page.locator('.webgl-host canvas').count() == 0
    expect(page.get_by_text('소화전 H-01', exact=False)).to_be_visible()
    context.close()
