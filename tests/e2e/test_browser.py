"""Opt-in, isolated background browser checks authorized by the user.

This module does not import or launch Playwright during ordinary Pytest runs.
It uses only synthetic demo data at the fixed loopback address below.
"""
import os
import json
import re
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from tests.conftest import control, prepare, release_n

BASE = os.getenv('STUDIO_BROWSER_BASE','http://127.0.0.1:8010')
DESKTOP = os.getenv('RUN_DESKTOP_BROWSER_TESTS') == '1'
ARTIFACTS = Path('artifacts/desktop/browser') if DESKTOP else Path('artifacts/browser')
if BASE not in {'http://127.0.0.1:8010','http://127.0.0.1:8011'} and not (DESKTOP and re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}', BASE)):
    raise ValueError('Browser checks are limited to the two local synthetic servers')
pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_BROWSER_TESTS') != '1',
    reason='Opt-in background browser checks; set RUN_BROWSER_TESTS=1.',
)


@pytest.fixture
def browser_context(request):
    # Keep browser launch out of test collection and all default test runs.
    from playwright.sync_api import sync_playwright

    with httpx.Client(base_url=BASE) as client:
        health = client.get('/api/v1/health')
        health.raise_for_status()
        assert client.get('/api/v1/auth/profiles').json()['demo'] is True
        if DESKTOP:
            status = client.get('/_desktop/status').json()
            assert status['application'] == 'fire-command-studio' and status['loopback_only']
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        engine = os.environ.get('BROWSER_ENGINE', 'chromium')
        if engine not in {'chromium', 'firefox'}:
            pytest.fail('BROWSER_ENGINE must be chromium or firefox')
        browser = getattr(playwright, engine).launch(headless=True)
        (ARTIFACTS / f'{engine}-environment.json').write_text(json.dumps({
            'engine':engine,'browser_version':browser.version,'playwright':version('playwright'),
            'headless':True,'base_url':BASE,'existing_browser_profile_used':False,
            'real_user_pilot':False,'target_pc_fps_verified':False,
        },ensure_ascii=False,indent=2),encoding='utf-8')
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        errors = []
        context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
        try:
            yield context
        finally:
            for index, page in enumerate(context.pages):
                if not page.is_closed():
                    page.evaluate('window.scrollTo(0,0)')
                    page.screenshot(path=str(ARTIFACTS / f'{engine}-{request.node.name}-{index}.png'), full_page=True)
            (ARTIFACTS / f'{engine}-{request.node.name}-errors.json').write_text(
                json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8'
            )
            context.close()
            browser.close()
        assert not errors, errors


def login(page, profile='facilitator'):
    from playwright.sync_api import expect

    page.goto(BASE)
    page.get_by_label('가상 사용자').select_option(profile)
    with page.expect_response(lambda response:response.url==BASE+'/api/v1/sessions') as initial_sessions:
        page.get_by_role('button', name='스튜디오 입장').click()
    expect(page.get_by_role('heading', name='공동 상황판단 훈련')).to_be_visible()
    if initial_sessions.value.json():
        expect(page.locator('[data-session-id]')).not_to_have_attribute('data-session-id','')


def test_new_exercise_readiness_publish_and_ten_injects(browser_context):
    """Exercise creation must retain its selection despite old running sessions."""
    from playwright.sync_api import expect

    page = browser_context.new_page()
    login(page)
    page.get_by_role('button', name='새 훈련', exact=True).click()
    name = 'GUI 합성 검증 ' + uuid4().hex[:8]
    page.get_by_label('훈련명 (선택)').fill(name)
    with page.expect_response(
        lambda response: response.url == BASE + '/api/v1/exercises'
        and response.request.method == 'POST'
    ) as created:
        page.get_by_role('button', name='훈련 만들기', exact=True).click()
    exercise = created.value.json()
    expect(page.get_by_role('heading', name='훈련 제작 스튜디오')).to_be_visible()
    expect(page.get_by_label('훈련 선택')).to_have_value(exercise['id'])

    page.get_by_role('button',name='건물·지도·자원',exact=False).click()
    page.get_by_role('textbox',name='건물명',exact=True).fill('GUI 합성 검증 A동')
    page.get_by_role('spinbutton',name='층수',exact=True).fill('4')
    page.get_by_role('spinbutton',name='회전 (°)',exact=True).fill('25')
    with page.expect_response(lambda response: response.url==BASE+'/api/v1/exercises/'+exercise['id'] and response.request.method=='PUT') as updated:
        page.get_by_role('button',name='변경 저장',exact=True).click()
    assert updated.value.status==200
    page.reload()
    page.get_by_label('훈련 선택').select_option(exercise['id'])
    page.get_by_role('button',name='훈련 제작',exact=True).click()
    page.get_by_role('button',name='건물·지도·자원',exact=False).click()
    expect(page.get_by_role('textbox',name='건물명',exact=True)).to_have_value('GUI 합성 검증 A동')
    expect(page.get_by_role('spinbutton',name='층수',exact=True)).to_have_value('4')
    expect(page.get_by_role('spinbutton',name='회전 (°)',exact=True)).to_have_value('25')

    page.get_by_role('button', name='임무 숙지', exact=True).click()
    for assignment in exercise['assignments']:
        role = next(role for role in exercise['roles'] if role['id'] == assignment['role_id'])
        page.get_by_role('combobox', name='담당 역할 / 참석자').select_option(
            assignment['person_id'] + ':' + assignment['role_id']
        )
        expect(page.locator('.personal-card h2')).to_have_text(role['name'])
        page.locator('.check-label input').check()
        for question, answer in {'report': 1, 'mission': 0, 'handover': 2}.items():
            page.locator(f'input[name="{question}"][value="{answer}"]').check()
        page.get_by_role('textbox', name='내가 받을 정보·수행할 일·보고할 곳을 설명하세요').fill(
            '자동시험용 합성 답변: 확인 사실과 미확인 정보를 구분해 승인된 보고선으로 보고합니다.'
        )
        page.get_by_role('button', name='숙지 결과 제출').click()
        expect(page.get_by_text('최근 결과 100점', exact=False)).to_be_visible()
        page.get_by_role('textbox', name='진행자 구두확인·관찰 메모').fill(
            '자동 GUI 시험 합성 확인. 실제 사람의 이해도 검증이 아님.'
        )
        page.get_by_role('button', name='구두 확인 승인').click()
        expect(page.get_by_text('진행자 구두확인 완료', exact=False)).to_be_visible()

    page.get_by_role('button', name='훈련 제작', exact=True).click()
    page.get_by_role('button', name='검증·리허설·발행', exact=False).click()
    page.get_by_role('button', name='가상 리허설', exact=True).click()
    expect(page.get_by_text('리허설 검증 완료', exact=True)).to_be_visible()
    page.get_by_role('textbox', name='발행 승인 메모').fill('자동 GUI 검증용 가상 발행. 기관 정규 승인 아님.')
    page.get_by_role('button', name='검토 완료·불변 버전 발행').click()
    page.get_by_role('button', name='훈련 실행본 생성', exact=False).click()
    expect(page.get_by_role('heading', name='공동 상황판단 훈련')).to_be_visible()
    page.get_by_role('button', name='훈련 시작', exact=True).click()
    for index in range(1, 11):
        candidate = page.locator('.candidate-list > div').filter(has_text=f'EV-{index:02}')
        candidate.get_by_role('button', name='승인·공개', exact=True).click()
        expect(candidate).to_have_count(0)
    expect(page.locator('.message-card')).to_have_count(10)
    expect(page.locator('.building-strip')).to_contain_text('GUI 합성 검증 A동')
    page.get_by_role('combobox', name='3D 시점').select_option('top')
    page.get_by_label('건물 분리보기').click()
    page.get_by_label('카메라 원위치').click()
    canvas = page.locator('.three-host canvas')
    if canvas.count():
        before = canvas.screenshot()
        bounds = canvas.bounding_box()
        page.mouse.move(bounds['x']+bounds['width']*.5, bounds['y']+bounds['height']*.55)
        page.mouse.down()
        page.mouse.move(bounds['x']+bounds['width']*.7, bounds['y']+bounds['height']*.65, steps=8)
        page.mouse.up()
        page.evaluate('async()=>{for(let i=0;i<4;i++)await new Promise(requestAnimationFrame)}')
        if canvas.count():
            assert canvas.screenshot() != before, 'Orbit drag should change the actual canvas image'
        else:
            expect(page.locator('.scene-fallback')).to_be_visible()
        page.get_by_label('카메라 원위치').click()
    page.screenshot(path=str(ARTIFACTS / 'facilitator-board.png'), full_page=True)
    assert page.locator('canvas').count() or page.get_by_text('2D', exact=False).count()

    actions = page.locator('.action-panel')
    for stage in ['수신', '인지', '사실 확인', '보고·협조', '결정·조치', '회신', '종결']:
        actions.get_by_role('textbox', name=re.compile('내용·정보 출처·불확실 사항')).fill(
            f'GUI 합성 {stage}: 모의 출처를 확인하고 담당자와 미확인 사항을 기록합니다.'
        )
        with page.expect_response(lambda response: response.url.endswith('/actions') and response.request.method == 'POST') as saved:
            actions.get_by_role('button', name=stage + ' 기록', exact=True).click()
        assert saved.value.status == 200
    expect(actions.get_by_role('button', name='종결 완료', exact=True)).to_be_disabled()
    actions.locator('.decision-form > summary').click()
    decision = 'GUI 합성 지휘결론: 인접동 위험과 미확인 정보를 재확인 후 보고'
    actions.get_by_role('textbox', name='확정할 결론 요약').fill(decision)
    actions.get_by_role('button', name='지휘결론 기록').click()
    expect(page.locator('.command-strip')).to_contain_text(decision)

    handover = page.locator('.handover-panel')
    handover.get_by_role('textbox', name='대체 발동 사유').fill('GUI 합성 교대 절차 검증')
    handover.get_by_role('button', name='대체 발동 제안').click()
    expect(handover.locator('.handover-current')).to_contain_text('PROPOSED')
    handover.get_by_role('textbox', name='수락·설명·확인 메모').fill('GUI 합성 대체 수락 및 단계별 확인')
    handover.get_by_role('button', name='대체 수락', exact=True).click()
    handover.get_by_role('button', name='대체자 임무카드·문항 열기').click()
    for question, answer in {'report': 1, 'mission': 0, 'handover': 2}.items():
        handover.locator(f'input[name="h-{question}"]').nth(answer).check()
    handover.get_by_role('button', name='열람·이해도 제출').click()
    handover.get_by_role('button', name='구두 설명 확인', exact=True).click()
    handover.get_by_role('textbox', name='현재 상황', exact=True).fill('모의 상황과 공개된 메시지 확인')
    handover.get_by_role('textbox', name='미확인 정보 (없으면 없음)').fill('모의 병원 수용 가능 여부 미확인')
    handover.get_by_role('textbox', name='미완료 임무·진행 요청').fill('예비 통신계획 후속 확인 요청')
    handover.get_by_role('button', name='인계·인수 확인').click()
    handover.get_by_role('button', name='역할 활성화').click()
    expect(handover.locator('.handover-current')).to_have_count(0)

    page.get_by_role('button', name='종료', exact=True).click()
    page.get_by_role('textbox', name='실행 사유', exact=True).fill('GUI 합성 전 과정 검증 종료')
    page.get_by_role('button', name='기록 후 실행').click()
    expect(page.locator('.exercise-switch')).to_contain_text('종료')
    page.get_by_role('button', name='관찰·강평', exact=True).click()
    evidence_choice = page.get_by_role('combobox', name='연결할 행동 증거')
    evidence_choice.select_option(evidence_choice.locator('option').last.get_attribute('value'))
    page.get_by_role('combobox', name='관찰 점수').select_option('2')
    observation = 'GUI 합성 관찰: 출처와 불확실성을 구분한 보고 폐루프 완료'
    page.get_by_role('textbox', name='관찰 사실·판단근거').fill(observation)
    page.get_by_role('button', name='관찰 기록', exact=True).click()
    expect(page.locator('.observations article')).to_have_count(1)
    page.get_by_role('textbox', name='개선과제', exact=True).fill('GUI 합성 재보고 경로 재훈련')
    page.get_by_role('combobox', name='책임 역할').select_option('incident_commander')
    page.get_by_role('textbox', name='재훈련 계획').fill('GUI 합성 동일 조건에서 출처 확인 및 재보고 연습')
    page.get_by_role('button', name='개선과제 등록').click()
    improvement = page.locator('.improvement-card')
    improvement.get_by_text('완료 증거 기록', exact=True).click()
    improvement.get_by_role('textbox', name='재훈련·개선 완료 증거').fill('GUI 합성 재훈련 수행 기록. 실제 기관 훈련 아님.')
    improvement.get_by_role('textbox', name='평가관 검토 메모').fill('GUI 자동시험용 합성 검토')
    improvement.get_by_role('button', name='완료 근거 등록').click()
    expect(improvement).to_contain_text('완료 증거 등록')
    page.get_by_role('textbox', name='평가관 승인 메모').fill('GUI 합성 AAR 검토. 실제 기관 승인 아님.')
    page.get_by_role('button', name='최종 평가 승인').click()
    expect(page.locator('.aar-export .success-text')).to_be_visible()
    with page.expect_download() as exported:
        page.get_by_role('button', name='JSON', exact=True).click()
    report_path = ARTIFACTS / f'aar-{os.environ.get("BROWSER_ENGINE", "chromium")}.json'
    exported.value.save_as(report_path)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    assert len(report['observations']) == 1 and report['improvements'][0]['status'] == 'COMPLETED'
    assert report['approval'] and report['handovers'][0]['status'] == 'ACTIVE'
    page.get_by_role('button', name='인쇄·PDF', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    expect(page.get_by_role('dialog')).to_contain_text(observation)
    expect(page.locator('.report-paper section').nth(1)).to_contain_text('GUI 합성 교대 절차 검증')
    expect(page.locator('.report-paper section').nth(1)).to_contain_text('대체·인계 단계 변경')
    page.screenshot(path=str(ARTIFACTS / f'aar-{os.environ.get("BROWSER_ENGINE", "chromium")}.png'), full_page=True)
    page.keyboard.press('Escape')
    expect(page.get_by_role('dialog')).to_have_count(0)


def test_participant_solo_feedback_and_account_isolation(browser_context):
    from playwright.sync_api import expect

    page = browser_context.new_page()
    login(page, 'person-05')
    page.get_by_role('button', name='개인 임무연습', exact=True).click()
    page.get_by_role('combobox', name='연습할 역할').select_option('communications_officer')
    with page.expect_response(lambda response: response.url == BASE + '/api/v1/practice' and response.request.method == 'POST') as created:
        page.get_by_role('button', name='개인 연습 만들기').click()
    sid = created.value.json()['id']
    page.get_by_role('button', name='연습 시작', exact=True).click()
    page.get_by_role('button', name='다음 모의 상황', exact=True).click()
    expect(page.locator('.message-card').first).to_be_visible()
    actions = page.locator('.action-panel')
    for stage in ['수신', '인지', '사실 확인', '보고·협조']:
        actions.get_by_role('textbox', name=re.compile('내용·정보 출처·불확실 사항')).fill('GUI 개인 연습 합성 답변: 예비 통신경로를 확인해 보고합니다.')
        with page.expect_response(lambda response: response.url.endswith('/actions') and response.request.method == 'POST') as saved:
            actions.get_by_role('button', name=stage + ' 기록', exact=True).click()
        assert saved.value.status == 200
    expect(page.locator('.facilitator-controls')).to_contain_text('모의 동료 피드백')
    expect(page.get_by_text('진행자 제어', exact=False)).to_have_count(0)
    page.get_by_role('button', name='연습 종료', exact=True).click()
    page.get_by_role('button', name='로그아웃', exact=True).click()
    expect(page.get_by_label('가상 사용자')).to_be_visible()
    page.get_by_label('가상 사용자').select_option('person-06')
    page.get_by_role('button', name='스튜디오 입장').click()
    expect(page.get_by_role('heading', name='공동 상황판단 훈련')).to_be_visible()
    assert browser_context.request.get(BASE + '/api/v1/sessions/' + sid).status == 403
    expect(page.get_by_text('모의 동료 피드백', exact=False)).to_have_count(0)


def test_old_session_selection_reconnect_and_role_switch(browser_context):
    from playwright.sync_api import expect

    with httpx.Client(base_url=BASE) as client:
        assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code == 200
        exercise = client.post('/api/v1/exercises', json={'template': 'factory', 'name': 'GUI 재접속·권한 전환 합성 ' + uuid4().hex[:8]}).json()
        sid = prepare(client, exercise['id'])
        # A fresh installation has no historical runs. Create later runs rather
        # than depending on previous tests or a developer's long-lived database.
        for _ in range(4):
            later = client.post('/api/v1/exercises/' + exercise['id'] + '/sessions')
            assert later.status_code == 201
            assert later.json()['id'] != sid
        assert control(client, sid, 'start').status_code == 200
        release_n(client, sid, 3)
        page = browser_context.new_page()
        page.add_init_script('window.__testSockets=[];const NativeWebSocket=window.WebSocket;window.WebSocket=class extends NativeWebSocket{constructor(...args){super(...args);window.__testSockets.push(this)}};')
        login(page)
        selector = page.get_by_role('combobox', name='훈련 실행본 선택')
        selector.select_option(sid)
        expect(page.locator('.exercise-switch')).to_contain_text(exercise['name'])
        expect(page.locator('.topbar')).to_contain_text('실시간 연결')
        assert selector.locator('option').count() > 4
        oldest_id = selector.locator('option').last.get_attribute('value')
        selector.select_option(oldest_id)
        expect(selector).to_have_value(oldest_id)
        selector.select_option(sid)
        expect(page.locator('.exercise-switch')).to_contain_text(exercise['name'])
        page.wait_for_function('(sid)=>document.querySelector(".main-shell").dataset.sessionId===sid&&window.__testSockets.some(socket=>socket.url.endsWith("/"+sid)&&socket.readyState===WebSocket.OPEN)', arg=sid)
        page.evaluate('async()=>{await Promise.all(window.__testSockets.filter(socket=>socket.readyState===WebSocket.OPEN).map(socket=>new Promise(resolve=>{socket.addEventListener("close",resolve,{once:true});socket.close()})))}')
        browser_context.set_offline(True)
        expect(page.locator('.topbar')).to_contain_text('재연결 중')
        assert control(client, sid, 'pause').status_code == 200
        browser_context.set_offline(False)
        expect(page.locator('.topbar')).to_contain_text('실시간 연결', timeout=15000)
        expect(page.locator('.exercise-switch')).to_contain_text('일시정지')
        page.get_by_role('button', name='로그아웃', exact=True).click()
        expect(page.get_by_label('가상 사용자')).to_be_visible()
        page.get_by_label('가상 사용자').select_option('board')
        page.get_by_role('button', name='스튜디오 입장').click()
        expect(page.get_by_role('heading', name='공동 상황판단 훈련')).to_be_visible()
        expect(page.get_by_role('button', name='훈련 제작', exact=True)).to_have_count(0)
        expect(page.get_by_text('진행자 제어', exact=False)).to_have_count(0)
        assert browser_context.request.get(BASE + '/api/v1/sessions/' + sid).json().get('candidates') is None
        page.reload()
        expect(page.get_by_role('heading', name='공동 상황판단 훈련')).to_be_visible()
        expect(page.get_by_text('진행자 제어', exact=False)).to_have_count(0)


def test_phone_layout_and_modal_keyboard(browser_context):
    from playwright.sync_api import expect

    page = browser_context.new_page()
    page.set_viewport_size({'width': 390, 'height': 844})
    login(page)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.get_by_role('button', name='새 훈련', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    assert page.get_by_role('dialog').evaluate('(element)=>element.contains(document.activeElement)')
    page.keyboard.press('Shift+Tab')
    assert page.get_by_role('dialog').evaluate('(element)=>element.contains(document.activeElement)')
    page.keyboard.press('Escape')
    expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.locator('.toast')).to_have_count(0, timeout=6000)
    page.screenshot(path=str(ARTIFACTS / 'phone.png'), full_page=True)


def test_public_board_uses_public_network_projection(browser_context):
    from playwright.sync_api import expect

    with httpx.Client(base_url=BASE) as client:
        assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code == 200
        created = client.post('/api/v1/exercises', json={'template': 'factory', 'name': 'GUI 공용화면 합성 검증'})
        created.raise_for_status()
        sid = prepare(client, created.json()['id'])
        assert control(client, sid, 'start').status_code == 200
        release_n(client, sid, 3)
    assert browser_context.request.post(BASE + '/api/v1/auth/demo', data={'profile': 'board'}).ok
    page = browser_context.new_page()
    with page.expect_response(BASE + '/api/v1/board/sessions/' + sid) as public_response:
        page.goto(BASE + '/board/' + sid)
    assert public_response.value.ok
    snapshots = [public_response.value.json()]
    expect(page.locator('.message-card')).to_have_count(2)
    assert snapshots
    assert all('exercise' not in state and 'candidates' not in state and 'observations' not in state for state in snapshots)
    assert all(state['scene']['H01']['water'] != 'UNAVAILABLE' for state in snapshots)
    expect(page.get_by_text('소방용수 사용 여부 미확인', exact=True)).to_have_count(0)
    expect(page.get_by_text('진행자 제어', exact=False)).to_have_count(0)
    page.screenshot(path=str(ARTIFACTS / 'public-board.png'), full_page=True)


def test_webgl_unavailable_preserves_scene_state_in_2d(browser_context):
    from playwright.sync_api import expect

    with httpx.Client(base_url=BASE) as client:
        assert client.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
        exercise=client.post('/api/v1/exercises',json={'template':'factory','name':'GUI WebGL 미지원 대안 합성 '+uuid4().hex[:8]}).json()
        sid=prepare(client,exercise['id'])
        assert control(client,sid,'start').status_code==200
        release_n(client,sid,5)
    page=browser_context.new_page()
    page.add_init_script('const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return String(type).startsWith("webgl")?null:original.call(this,type,...args)};')
    login(page)
    page.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
    fallback=page.locator('.scene-fallback')
    expect(fallback).to_be_visible()
    expect(fallback).to_contain_text('B01-F03-Z01')
    expect(fallback).to_contain_text('B02')
    expect(fallback).to_contain_text('연기 3단계 · 화염 2단계')
    expect(fallback).to_contain_text('인접동 노출 주의')
    expect(fallback).to_contain_text('출입구 폐쇄')
    expect(page.locator('.scene-key')).not_to_be_visible()
    expect(page.locator('.performance')).not_to_be_visible()
    fallback.focus()
    page.keyboard.press('End')
    expect(fallback.locator('li').last).to_be_in_viewport()
    page.keyboard.press('Home')
    expect(fallback.locator('strong').first).to_be_in_viewport()
    page.locator('.building-strip button').filter(has_text='B02').click()
    expect(page.locator('.building-strip button.selected')).to_contain_text('B02')
    assert page.locator('.three-host canvas').count()==0


def test_candidate_preview_defer_skip_and_public_isolation(browser_context):
    from playwright.sync_api import expect

    with httpx.Client(base_url=BASE) as client:
        assert client.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
        exercise=client.post('/api/v1/exercises',json={'template':'factory','name':'GUI 사건 연기·건너뛰기 합성 '+uuid4().hex[:8]}).json()
        envelope=client.get('/api/v1/exercises/'+exercise['id']).json()
        exercise=envelope['exercise'];exercise['organization_approval']='합성 UI 전환 조건 주입 · 실제 기관 승인 아님'
        version=envelope['state_version']
        changed=client.put('/api/v1/exercises/'+exercise['id'],json={'expected_state_version':version,'exercise':exercise},headers={'Idempotency-Key':uuid4().hex})
        assert changed.status_code==200,changed.text
        sid=prepare(client,exercise['id'])
        assert control(client,sid,'start').status_code==200
    page=browser_context.new_page();login(page)
    page.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
    expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
    candidate=page.locator('[data-candidate-id="EV-01"]')
    width=page.get_by_role('slider',name='3D 영역 너비',exact=True)
    initial_width=page.locator('.scene-panel').bounding_box()['width']
    width.focus();page.keyboard.press('End');expect(width).to_have_value('78')
    expect(page.locator('.board-configurable')).to_have_css('grid-template-columns',re.compile(r'.*px .*px'))
    assert page.locator('.scene-panel').bounding_box()['width']>initial_width+40
    height=page.get_by_role('slider',name='3D 화면 높이',exact=True)
    height.focus();page.keyboard.press('Home');expect(page.locator('.scene-view')).to_have_css('height','320px')
    page.get_by_role('checkbox',name='상황판 안에서 메시지 위치 고정',exact=True).check()
    expect(page.locator('.messages-panel')).to_have_css('position','sticky')
    page.get_by_role('button',name='화면 배치 원위치',exact=True).click()
    expect(width).to_have_value('66');expect(page.locator('.scene-view')).to_have_css('height','550px')
    candidate.locator('summary').click()
    expect(candidate.locator('.candidate-preview')).to_contain_text('B01-F02-Z01 / smoke')
    expect(candidate.locator('table th')).to_have_text(['객체/필드','변경 전','변경 후'])
    before=browser_context.request.get(BASE+f'/api/v1/sessions/{sid}').json()
    candidate.get_by_role('button',name='연기',exact=True).click()
    submit=candidate.get_by_role('button',name='사유 기록 후 연기',exact=True)
    expect(submit).to_be_disabled()
    candidate.get_by_role('textbox',name='연기 사유',exact=True).fill('PRIVATE_GUI_DEFER 합성 토론시간 확보')
    candidate.get_by_role('spinbutton',name='훈련시계 기준 연기 시간 (초)',exact=True).fill('0')
    expect(submit).to_be_disabled()
    candidate.get_by_role('spinbutton',name='훈련시계 기준 연기 시간 (초)',exact=True).fill('60')
    candidate.screenshot(path=str(ARTIFACTS / f'{os.getenv("BROWSER_ENGINE","chromium")}-candidate-preview-and-defer.png'))
    submit.click()
    expect(candidate).to_contain_text('까지 연기')
    expect(candidate.get_by_role('button',name='승인·공개',exact=True)).to_be_disabled()
    after=browser_context.request.get(BASE+f'/api/v1/sessions/{sid}').json()
    assert before['scene']==after['scene'] and not after['messages']
    candidate.get_by_role('button',name='건너뛰기',exact=True).click()
    candidate.get_by_role('textbox',name='건너뛰기 사유',exact=True).fill('PRIVATE_GUI_SKIP 합성 관찰 대체')
    candidate.get_by_role('button',name='사유 기록 후 건너뛰기',exact=True).click()
    expect(candidate).to_have_count(0)
    next_candidate=page.locator('[data-candidate-id="EV-02"]');expect(next_candidate).to_be_visible()
    state=browser_context.request.get(BASE+f'/api/v1/sessions/{sid}').json()
    assert not state['messages'] and state['scene']==before['scene']
    assert any(entry['kind']=='EVENT_DEFER' for entry in state['log']) and any(entry['kind']=='EVENT_SKIP' for entry in state['log'])
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    next_candidate.get_by_role('button',name='승인·공개',exact=True).click()
    expect(page.locator('.message-card')).to_have_count(1)
    public=browser_context.new_page();public.goto(BASE+'/board/'+sid)
    expect(public.locator('.message-card')).to_have_count(1)
    expect(public.locator('.candidate-list')).to_have_count(0)
    assert 'PRIVATE_GUI_' not in public.locator('body').inner_text()
    response=browser_context.request.get(BASE+f'/api/v1/board/sessions/{sid}').json()
    assert 'candidates' not in response and 'PRIVATE_GUI_' not in str(response)
    page.set_viewport_size({'width':1440,'height':1000})
    page.get_by_role('button',name='통제단 전환',exact=True).click()
    page.get_by_role('textbox',name='기관 승인 편성 및 인계 확인',exact=True).fill('합성 전환 표시 시험 · 실제 기관 승인·실제 인계 아님')
    page.get_by_role('button',name='기록 후 실행',exact=True).click()
    expect(page.locator('.command-strip')).to_contain_text('통제단 단계')
    page.get_by_role('button',name='기록·재생',exact=True).click()
    timeline=page.locator('.timeline-table')
    expect(timeline).to_contain_text('사건 연기');expect(timeline).to_contain_text('사건 건너뛰기');expect(timeline).to_contain_text('통제단 전환')
    for internal in ['EVENT_DEFER','EVENT_SKIP','ORGANIZATION_TRANSITIONED']:expect(timeline).not_to_contain_text(internal)
