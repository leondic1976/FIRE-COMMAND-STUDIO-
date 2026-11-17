"""Actual synthetic authoring and GLB/JSON reuse; no institutional approval claim."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
import zipfile
import httpx
import pytest
from tests.e2e.test_asset_browser import asset_browser
from apps.api.asset_validation import validate_model
from tests.conftest import prepare

BASE='http://127.0.0.1:8011'
pytestmark=pytest.mark.skipif(os.getenv('RUN_GENERATOR_BROWSER_TESTS')!='1',reason='Explicit synthetic geometry/browser fixture required')


def test_oversized_procedural_entrances_use_2d_before_allocating_webgl(asset_browser):
    from playwright.sync_api import expect
    with httpx.Client(base_url=BASE) as client:
        assert client.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
        created=client.post('/api/v1/exercises',json={'template':'factory','name':'GUI 합성 장면 예산 '+uuid4().hex[:8]}).json()
        data=client.get('/api/v1/exercises/'+created['id']).json();exercise=data['exercise'];exercise['subject']['buildings'][0]['entrances']=['NORTH']*16000
        saved=client.put('/api/v1/exercises/'+created['id'],json={'expected_state_version':data['state_version'],'exercise':exercise},headers={'Idempotency-Key':uuid4().hex});assert saved.status_code==200,saved.text
        sid=prepare(client,exercise['id'])
    page=asset_browser.new_page();page.goto(BASE);page.get_by_label('가상 사용자').select_option('facilitator');page.get_by_role('button',name='스튜디오 입장',exact=True).click();page.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
    expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
    expect(page.get_by_role('region',name='2D 상황판 상태 목록',exact=True)).to_be_visible();expect(page.locator('.three-host canvas')).to_have_count(0)


def test_floor_interior_preset_copy_save_cutaway_and_scene_package(asset_browser):
    from playwright.sync_api import expect
    context=asset_browser;engine=os.getenv('BROWSER_ENGINE','chromium');page=context.new_page();page.goto(BASE)
    page.get_by_label('가상 사용자').select_option('facilitator')
    with page.expect_response(lambda r:r.url==BASE+'/api/v1/sessions'):
        page.get_by_role('button',name='스튜디오 입장',exact=True).click()
    page.get_by_role('button',name='새 훈련',exact=True).click();page.get_by_label('훈련명 (선택)').fill('GUI 합성 내부 생성기 '+uuid4().hex[:8])
    with page.expect_response(lambda r:r.url==BASE+'/api/v1/exercises' and r.request.method=='POST') as created:
        page.get_by_role('button',name='훈련 만들기',exact=True).click()
    exercise=created.value.json();eid=exercise['id'];page.get_by_role('button',name='건물·지도·자원',exact=False).click();designer=page.locator('.building-designer')
    resources=page.locator('.site-resource-editor');resources.get_by_role('combobox',name='추가할 주변 자원',exact=True).select_option('PARKING');resources.get_by_role('button',name='주변 자원 추가',exact=True).click();resources.get_by_role('textbox',name='주변 자원 이름',exact=True).fill('가상 주차장 GUI');resources.get_by_role('spinbutton',name='자원 동서 위치 (m)',exact=True).fill('-35')
    expect(designer.get_by_role('combobox',name='가상 용도 프리셋',exact=True).locator('option')).to_have_count(10)
    designer.get_by_role('combobox',name='가상 용도 프리셋',exact=True).select_option('공장');designer.get_by_role('button',name='가상 치수 제안 적용',exact=True).click()
    designer.get_by_role('spinbutton',name='지하층 수',exact=True).fill('1');designer.get_by_role('combobox',name='지붕 형식',exact=True).select_option('GABLE');designer.get_by_role('combobox',name='편집할 층',exact=True).select_option('-1')
    designer.get_by_role('button',name='층 윤곽 그리기',exact=True).click();plan=designer.get_by_role('img');rect=plan.bounding_box();assert rect
    for x,y in [(.25,.3),(.75,.3),(.75,.7),(.25,.7)]:plan.click(position={'x':rect['width']*x,'y':rect['height']*y})
    designer.get_by_role('button',name='층 윤곽 4점 적용',exact=True).click()
    designer.get_by_role('combobox',name='추가할 내부 요소',exact=True).select_option('COMPARTMENT');designer.get_by_role('button',name='내부 요소 추가',exact=True).click()
    designer.get_by_role('textbox',name='내부 요소 이름',exact=True).fill('가상 지하 방화구획 GUI');designer.get_by_role('spinbutton',name='내부 폭 (m)',exact=True).fill('6');designer.get_by_role('spinbutton',name='내부 깊이 (m)',exact=True).fill('8');designer.get_by_role('spinbutton',name='내부 동서 위치 (m)',exact=True).fill('3')
    original_id=designer.locator('[data-feature-id]').get_attribute('data-feature-id')
    designer.get_by_role('combobox',name='추가할 내부 요소',exact=True).select_option('STAIR');designer.get_by_role('button',name='내부 요소 추가',exact=True).click();designer.get_by_role('spinbutton',name='내부 동서 위치 (m)',exact=True).fill('-4')
    designer.get_by_role('button',name='선택 건물·구역 복제',exact=True).click();designer.get_by_role('combobox',name='편집할 층',exact=True).select_option('-1')
    assert designer.locator('[data-feature-id]').get_attribute('data-feature-id')!=original_id
    with page.expect_response(lambda r:r.url==BASE+f'/api/v1/exercises/{eid}' and r.request.method=='PUT') as saved:
        page.get_by_role('button',name='변경 저장',exact=True).click()
    assert saved.value.ok,saved.value.text();expect(page.get_by_role('button',name='변경 저장',exact=True)).to_be_disabled()
    stored=context.request.get(BASE+'/api/v1/exercises/'+eid).json()['exercise'];assert len(stored['subject']['buildings'])==4
    assert stored['subject']['buildings'][0]['floor_outlines'][0]['floor']==-1
    assert stored['subject']['buildings'][0]['roof_style']=='GABLE'
    assert next(f for f in stored['subject']['features'] if f['name']=='가상 주차장 GUI')['x']==-35
    assert stored['subject']['interior_verified'] is False
    page.get_by_role('button',name='훈련 상황판',exact=True).click()
    expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id','')
    preview=page.locator('.three-host canvas');expect(preview).to_be_visible()
    preview.evaluate("node=>node.dataset.previewProbe='same-synthetic-preview'")
    page.wait_for_timeout(1400)
    expect(preview).to_have_attribute('data-preview-probe','same-synthetic-preview')
    page.get_by_role('button',name='훈련 제작',exact=True).click();page.get_by_role('button',name='건물·지도·자원',exact=False).click()
    with page.expect_download(timeout=60000) as download:
        designer.get_by_role('button',name='가상 장면 GLB·JSON 내보내기',exact=True).click()
    output=Path('artifacts/browser')/(engine+'-synthetic-scene-package.zip');download.value.save_as(output)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())=={'scene.glb','scene.json','provenance.json','TRAINING_ONLY.txt'}
        scene=json.loads(archive.read('scene.json'));provenance=json.loads(archive.read('provenance.json'))
        assert scene['training_only'] is True and scene['subject']['buildings'][0]['basement_floors']==1
        assert scene['subject']['interior_verified'] is False
        assert provenance['published'] is False
        for name,digest in provenance['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
        _,manifest=validate_model(archive.read('scene.glb'))
        assert manifest.triangles>0 and manifest.bounds[0][1]<-3
    def change(path,body):
        r=context.request.post(BASE+'/api/v1'+path,data=body,headers={'Idempotency-Key':uuid4().hex});assert r.ok,r.text();return r.json()
    def version():return context.request.get(BASE+'/api/v1/exercises/'+eid).json()['state_version']
    for assignment in exercise['assignments']:
        role=next(r for r in exercise['roles'] if r['id']==assignment['role_id'])
        change(f'/exercises/{eid}/readiness',{'expected_state_version':version(),'person_id':assignment['person_id'],'role_id':assignment['role_id'],'acknowledged_version':role['version'],'answers':{'report':1,'mission':0,'handover':2},'explanation':'합성 생성기 자동시험. 실제 참가자 검수 아님.'})
        change(f'/exercises/{eid}/readiness/review',{'expected_state_version':version(),'person_id':assignment['person_id'],'role_id':assignment['role_id'],'approved':True,'note':'합성 자동시험. 실제 구두/기관 승인 아님.'})
    change(f'/exercises/{eid}/rehearse',{'expected_state_version':version()});change(f'/exercises/{eid}/publish',{'expected_state_version':version(),'note':'합성 생성기 자동검증. 기관 승인 아님.'});sid=change(f'/exercises/{eid}/sessions',{})['id']
    delayed=[]
    def hold_first_snapshot(route):
        if delayed:return route.continue_()
        delayed.append((route,route.fetch().json()))
    page.route(BASE+f'/api/v1/sessions/{sid}',hold_first_snapshot)
    page.reload();page.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
    expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
    assert delayed,'The actual REST snapshot was not intercepted'
    before=context.request.get(BASE+'/api/v1/sessions/'+sid).json()
    change(f'/sessions/{sid}/control',{'expected_state_version':before['state_version'],'operation':'start'})
    latest=context.request.get(BASE+'/api/v1/sessions/'+sid).json()['state_version']
    expect(page.locator('[data-session-id]')).to_have_attribute('data-state-version',str(latest))
    assert delayed[0][1]['state_version']<latest
    page.evaluate("""()=>{const node=document.querySelector('[data-session-id]');window.__studioVersions=[];window.__studioVersionObserver=new MutationObserver(()=>window.__studioVersions.push(Number(node.dataset.stateVersion)));window.__studioVersionObserver.observe(node,{attributes:true,attributeFilter:['data-state-version']});}""")
    for route,snapshot in delayed:route.fulfill(status=200,content_type='application/json',body=json.dumps(snapshot))
    page.wait_for_timeout(150)
    observed=page.evaluate('()=>{window.__studioVersionObserver.disconnect();return window.__studioVersions;}')
    assert all(value>=latest for value in observed),{'latest':latest,'observed':observed}
    assert page.locator('[data-session-id]').get_attribute('data-state-version')==str(latest),'Delayed REST response replaced the newer WebSocket state'
    page.unroute(BASE+f'/api/v1/sessions/{sid}',hold_first_snapshot)
    page.get_by_role('combobox',name='표시할 층',exact=True).select_option('-1');page.get_by_role('button',name='내부 도식 절개',exact=True).click();page.get_by_role('combobox',name='3D 시점',exact=True).select_option('top')
    expect(page.locator('.three-host canvas')).to_be_visible();page.wait_for_timeout(1000);page.locator('.scene-view').screenshot(path=f'artifacts/browser/{engine}-generator-basement-cutaway.png')
    Path(f'artifacts/browser/{engine}-generator-package-check.json').write_text(json.dumps({'synthetic_only':True,'zip_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'glb_triangles':manifest.triangles,'glb_nodes':len(manifest.nodes),'min_y':manifest.bounds[0][1],'actual_av_verified':False,'institutional_approval':False},indent=2),encoding='utf-8')
