"""Synthetic model/photo intake and real renderer checks; no real AV claim."""
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
from tests.asset_fixtures import building_glb,photo,facade_photo

pytestmark=pytest.mark.skipif(os.getenv('RUN_ASSET_BROWSER_TESTS')!='1',reason='Synthetic asset/scanner fixture required')
BASE='http://127.0.0.1:8011'


@pytest.fixture
def asset_browser(request):
    from playwright.sync_api import sync_playwright
    engine=os.getenv('BROWSER_ENGINE','chromium');assert engine in {'chromium','firefox'}
    Path('artifacts/browser').mkdir(parents=True,exist_ok=True)
    with sync_playwright() as pw:
        browser=getattr(pw,engine).launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1050});errors=[]
        context.on('page',lambda page:page.on('pageerror',lambda error:errors.append(str(error))))
        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(BASE+'/') or route.request.url.startswith('blob:') else route.abort())
        try:yield context
        finally:
            for i,page in enumerate(context.pages):
                if not page.is_closed():page.screenshot(path=f'artifacts/browser/{engine}-{request.node.name}-{i}.png',full_page=True)
            Path(f'artifacts/browser/{engine}-{request.node.name}-errors.json').write_text(json.dumps(errors,ensure_ascii=False),encoding='utf-8')
            context.close();browser.close()
        assert not errors,errors


def test_glb_preview_floor_mapping_photo_and_public_content(asset_browser):
    from playwright.sync_api import expect
    context=asset_browser;page=context.new_page();page.goto(BASE)
    page.get_by_label('가상 사용자').select_option('facilitator')
    with page.expect_response(lambda r:r.url==BASE+'/api/v1/sessions') as sessions:
        page.get_by_role('button',name='스튜디오 입장').click()
    expect(page.get_by_role('heading',name='공동 상황판단 훈련',exact=True)).to_be_visible()
    if sessions.value.json():expect(page.locator('[data-session-id]')).not_to_have_attribute('data-session-id','')
    page.get_by_role('button',name='새 훈련',exact=True).click()
    page.get_by_label('훈련명 (선택)').fill('합성 자산 UI '+uuid4().hex[:8])
    with page.expect_response(lambda r:r.url==BASE+'/api/v1/exercises' and r.request.method=='POST') as created:
        page.get_by_role('button',name='훈련 만들기',exact=True).click()
    exercise=created.value.json();eid=exercise['id']
    page.get_by_role('button',name='건물·지도·자원',exact=False).click()
    panel=page.locator('.asset-panel')
    panel.get_by_role('textbox',name='자산 이름',exact=True).fill('GUI 합성3층 모델')
    panel.get_by_role('textbox',name='제작·촬영 주체',exact=True).fill('자동시험 코드 생성기')
    panel.get_by_role('textbox',name='자산 원천',exact=True).fill('프로젝트 합성 도형')
    panel.get_by_role('textbox',name='촬영·자료 기준일',exact=True).fill('2026-11-17')
    panel.get_by_role('textbox',name='이용허락·가공·내부 공개·재사용 범위',exact=True).fill('합성 UI 시험 자료. 실제 기관 이용권·검사기 승인 아님.')
    panel.get_by_role('group',name='모델·사진·영상 파일 (15MiB 이하)',exact=True).locator('input').set_input_files({'name':'synthetic.glb','mimeType':'model/gltf-binary','buffer':building_glb()})
    with page.expect_response(lambda r:r.url==BASE+f'/api/v1/exercises/{eid}/assets' and r.request.method=='POST') as uploaded:
        panel.get_by_role('button',name='격리 수집·검사',exact=True).click()
    model=uploaded.value.json();assert model['status']=='VALIDATED' and model['scan']['provider']=='synthetic-protocol-fixture'
    expect(panel.locator('[data-asset-ready]')).to_have_attribute('data-asset-ready','true',timeout=30000)
    for index in range(3):panel.get_by_role('combobox',name=f'객체 {index} 층 연결',exact=True).select_option(str(index+1))
    panel.get_by_role('combobox',name='객체 2 구역 연결',exact=True).select_option('B01-F03-Z01')
    panel.get_by_role('spinbutton',name='모델 단위 보정 (1=미터)',exact=True).fill('1.25')
    panel.get_by_role('spinbutton',name='모델 추가 회전 (°)',exact=True).fill('25')
    panel.get_by_role('spinbutton',name='모델 위치 보정 X (m)',exact=True).fill('8')
    panel.get_by_role('combobox',name='자산 공개 범위',exact=True).select_option('PUBLIC')
    panel.get_by_role('checkbox',name='이용권·공개범위·방향·단위·층/객체 연결을 검토했습니다.',exact=False).check()
    panel.get_by_role('textbox',name='자산 권리·좌표·대조 검토 메모',exact=True).fill('PRIVATE_ASSET_REVIEW_SENTINEL 합성 검토')
    panel.get_by_role('button',name='검토 후 초안에 연결',exact=True).click()
    expect(panel.locator('.asset-binding-row')).to_have_count(1)
    panel.screenshot(path=f'artifacts/browser/{os.getenv("BROWSER_ENGINE","chromium")}-asset-model-review.png')
    if panel.locator('.asset-upload').get_attribute('open') is None:panel.locator('.asset-upload summary').click()
    panel.get_by_role('textbox',name='자산 이름',exact=True).fill('GUI 합성 비공개 참고사진')
    panel.get_by_role('group',name='모델·사진·영상 파일 (15MiB 이하)',exact=True).locator('input').set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':photo()})
    with page.expect_response(lambda r:r.url==BASE+f'/api/v1/exercises/{eid}/assets' and r.request.method=='POST') as uploaded:
        panel.get_by_role('button',name='격리 수집·검사',exact=True).click()
    picture=uploaded.value.json();assert picture['kind']=='PHOTO'
    expect(panel.locator('.asset-photo-preview')).to_be_visible()
    expect(panel.locator('.asset-photo-preview')).to_have_js_property('naturalWidth',64)
    panel.get_by_role('checkbox',name='이용권·공개범위·방향·단위·층/객체 연결을 검토했습니다.',exact=False).check()
    panel.get_by_role('textbox',name='자산 권리·좌표·대조 검토 메모',exact=True).fill('PRIVATE_ASSET_REVIEW_SENTINEL 사진 합성 검토')
    panel.get_by_role('button',name='검토 후 초안에 연결',exact=True).click()
    expect(panel.locator('.asset-binding-row')).to_have_count(2)
    if panel.locator('.asset-upload').get_attribute('open') is None:panel.locator('.asset-upload summary').click()
    panel.get_by_role('textbox',name='자산 이름',exact=True).fill('GUI 합성 외벽 색상표')
    panel.get_by_role('group',name='모델·사진·영상 파일 (15MiB 이하)',exact=True).locator('input').set_input_files({'name':'facade.png','mimeType':'image/png','buffer':facade_photo()})
    with page.expect_response(lambda r:r.url==BASE+f'/api/v1/exercises/{eid}/assets' and r.request.method=='POST') as uploaded:
        panel.get_by_role('button',name='격리 수집·검사',exact=True).click()
    facade=uploaded.value.json();assert facade['kind']=='PHOTO'
    expect(panel.locator('.asset-photo-preview')).to_be_visible()
    panel.get_by_role('combobox',name='자산을 연결할 건물',exact=True).select_option('B02')
    panel.get_by_role('combobox',name='자산 사용 방식',exact=True).select_option('FACADE')
    panel.get_by_role('combobox',name='사진을 적용할 외벽 면',exact=True).select_option('SOUTH')
    panel.get_by_role('combobox',name='자산 공개 범위',exact=True).select_option('PUBLIC')
    panel.get_by_role('checkbox',name='이용권·공개범위·방향·단위·층/객체 연결을 검토했습니다.',exact=False).check()
    panel.get_by_role('textbox',name='자산 권리·좌표·대조 검토 메모',exact=True).fill('PRIVATE_ASSET_REVIEW_SENTINEL 합성 외벽 색상표')
    panel.get_by_role('button',name='검토 후 초안에 연결',exact=True).click()
    expect(panel.locator('.asset-binding-row')).to_have_count(3)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.set_viewport_size({'width':1440,'height':1050})
    # Exercise server gates through API; baseline browser tests cover readiness UI.
    def version():return context.request.get(BASE+'/api/v1/exercises/'+eid).json()['state_version']
    def change(path,body):
        response=context.request.post(BASE+'/api/v1'+path,data=body,headers={'Idempotency-Key':uuid4().hex})
        assert response.ok,response.text();return response.json()
    for assignment in exercise['assignments']:
        role=next(r for r in exercise['roles'] if r['id']==assignment['role_id'])
        change(f'/exercises/{eid}/readiness',{'expected_state_version':version(),'person_id':assignment['person_id'],'role_id':assignment['role_id'],
            'acknowledged_version':role['version'],'answers':{'report':1,'mission':0,'handover':2},'explanation':'합성 시험 준비. 실제 참가자 이해도 검증 아님.'})
        change(f'/exercises/{eid}/readiness/review',{'expected_state_version':version(),'person_id':assignment['person_id'],'role_id':assignment['role_id'],'approved':True,'note':'합성 자동시험 준비. 실제 기관 검수 아님.'})
    change(f'/exercises/{eid}/rehearse',{'expected_state_version':version()})
    change(f'/exercises/{eid}/publish',{'expected_state_version':version(),'note':'합성 자산 UI 검증. 기관 정규 승인 아님.'})
    session=change(f'/exercises/{eid}/sessions',{})
    page.reload();page.get_by_role('combobox',name='훈련 실행본 선택').select_option(session['id'])
    expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',session['id'])
    page.get_by_role('button',name='훈련 상황판',exact=True).click()
    expect(page.locator('.scene-asset-status')).to_contain_text('3객체 표시',timeout=30000)
    expect(page.locator('.scene-asset-status')).to_contain_text('GUI 합성 외벽 색상표 · 사진 색상맵',timeout=30000)
    expect(page.locator('.reference-media')).to_contain_text('GUI 합성 비공개 참고사진')
    expect(page.locator('.reference-media img')).to_have_js_property('naturalWidth',64)
    scene_requests=[];page.on('request',lambda request:scene_requests.append(request.url) if '/assets/' in request.url and request.url.endswith('/content') else None)
    page.get_by_role('combobox',name='표시할 층',exact=True).select_option('2')
    expect(page.locator('.scene-asset-status')).to_contain_text('2객체 표시',timeout=30000)
    assert not any(model['id'] in url for url in scene_requests),'A view-only change should reuse the verified bounded component cache'
    page.locator('.scene-panel').screenshot(path=f'artifacts/browser/{os.getenv("BROWSER_ENGINE","chromium")}-asset-model-in-scene.png')
    public=context.new_page();public.goto(BASE+'/board/'+session['id'])
    expect(public.locator('.scene-asset-status')).to_contain_text('3객체 표시',timeout=30000)
    expect(public.locator('.scene-asset-status')).to_contain_text('사진 색상맵',timeout=30000)
    expect(public.locator('.reference-media')).to_have_count(0)
    assert 'PRIVATE_ASSET_REVIEW_SENTINEL' not in public.locator('body').inner_text()
    denied=context.request.get(BASE+f"/api/v1/board/sessions/{session['id']}/assets/{picture['id']}/content")
    assert denied.status==404
    allowed=context.request.get(BASE+f"/api/v1/board/sessions/{session['id']}/assets/{facade['id']}/content")
    assert allowed.ok and allowed.headers['content-type'].startswith('image/png')
    public.locator('.scene-panel').screenshot(path=f'artifacts/browser/{os.getenv("BROWSER_ENGINE","chromium")}-asset-public-facade.png')
    page.get_by_role('button',name='관찰·강평',exact=True).click()
    page.get_by_role('button',name='인쇄·PDF',exact=True).click()
    report=page.get_by_role('dialog')
    expect(report.get_by_role('heading',name='8. 모델·사진·영상과 검토 범위',exact=True)).to_be_visible()
    expect(report).to_contain_text('자동시험 코드 생성기')
    expect(report).to_contain_text('합성 UI 시험 자료. 실제 기관 이용권·검사기 승인 아님.')
    expect(report).to_contain_text('1층 1객체 / 2층 1객체 / 3층 1객체')
    expect(report).not_to_contain_text('PRIVATE_ASSET_REVIEW_SENTINEL')
    if os.getenv('BROWSER_ENGINE','chromium')=='chromium' and os.getenv('GENERATE_ASSET_PDF')=='1':
        Path('output/pdf').mkdir(parents=True,exist_ok=True)
        page.pdf(path='output/pdf/asset-provenance-chromium.pdf',format='A4',print_background=True,
            display_header_footer=True,header_template='<span></span>',
            footer_template='<div style="width:100%;text-align:center;font-size:8px">TRAINING ONLY · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
            margin={'top':'14mm','bottom':'16mm','left':'12mm','right':'12mm'})
