"""Environment annotations remain readable and obey the public projection."""
import os
import json
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from tests.conftest import prepare,control
from tests.e2e.test_asset_browser import asset_browser

BASE='http://127.0.0.1:8011'
pytestmark=pytest.mark.skipif(os.getenv('RUN_ENVIRONMENT_BROWSER_TESTS')!='1',reason='Explicit synthetic environment/browser check required')


def test_environment_summary_3d_2d_and_private_public_state(asset_browser):
    from playwright.sync_api import expect
    context=asset_browser
    with httpx.Client(base_url=BASE) as client:
        assert client.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
        created=client.post('/api/v1/exercises',json={'template':'factory','name':'GUI 합성 환경 주석 '+uuid4().hex[:8]}).json()
        envelope=client.get('/api/v1/exercises/'+created['id']).json();exercise=envelope['exercise'];eid=exercise['id']
        exercise['subject']['features'].append({'id':'ENV-PRIVATE','name':'합성 환경 주석','kind':'ZONE','building_id':None,'floor':0,'x':0,'z':0,'state':{'rain':0,'wind':0,'power':True}})
        exercise['events'][0]['visibility']='PRIVATE';exercise['events'][0]['recipient_role_ids']=[exercise['roles'][0]['id']]
        for field,before,after in [('rain',0,2),('wind',0,7),('power',True,False)]:exercise['events'][0]['patches'].append({'feature_id':'ENV-PRIVATE','field':field,'before':before,'after':after,'visual_kind':'ILLUSTRATIVE'})
        response=client.put('/api/v1/exercises/'+eid,json={'expected_state_version':envelope['state_version'],'exercise':exercise},headers={'Idempotency-Key':uuid4().hex});assert response.status_code==200,response.text
        sid=prepare(client,eid);assert control(client,sid,'start').status_code==200
    page=context.new_page();page.goto(BASE);page.get_by_label('가상 사용자').select_option('facilitator');page.get_by_role('button',name='스튜디오 입장',exact=True).click();page.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
    public=context.new_page();public.goto(BASE+'/board/'+sid)
    for target in [page,public]:expect(target.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
    page.locator('[data-candidate-id="EV-01"]').get_by_role('button',name='승인·공개',exact=True).click()
    details=page.locator('.scene-state-summary');details.locator('summary').click()
    notes=['강우 연출 2단계','바람 강도 7 (연출)','정전 (연출)']
    for note in notes:expect(details).to_contain_text(note)
    public.locator('.scene-state-summary summary').click()
    for note in notes:expect(public.locator('.scene-state-summary')).not_to_contain_text(note)
    projected=context.request.get(BASE+'/api/v1/board/sessions/'+sid).json()
    assert projected['scene']['ENV-PRIVATE']=={'rain':0,'wind':0,'power':True}
    no_webgl="""(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(['webgl','webgl2','experimental-webgl'].includes(type))return null;return original.call(this,type,...args);};})();"""
    fallback=context.new_page();fallback.add_init_script(no_webgl);fallback.goto(BASE);fallback.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
    region=fallback.get_by_role('region',name='2D 상황판 상태 목록',exact=True);expect(region).to_be_visible()
    for note in notes:expect(region).to_contain_text(note)
    region.focus();fallback.keyboard.press('End');last=region.locator('.scene-state-list li').last
    bounds=last.evaluate("""node=>{const rect=n=>{const r=n.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height,clientHeight:n.clientHeight,scrollHeight:n.scrollHeight,scrollTop:n.scrollTop,overflow:getComputedStyle(n).overflow};};const ancestors=[];for(let p=node;p;p=p.parentElement)ancestors.push({tag:p.tagName,class:p.className,...rect(p)});return {viewport:[innerWidth,innerHeight],ancestors};}""")
    Path(f'artifacts/browser/{os.getenv("BROWSER_ENGINE","chromium")}-environment-end-bounds.json').write_text(json.dumps(bounds,indent=2),encoding='utf-8')
    expect(last).to_be_in_viewport(ratio=1,timeout=3000)
    shared=context.new_page();shared.add_init_script(no_webgl);shared.goto(BASE+'/board/'+sid)
    public_region=shared.get_by_role('region',name='2D 상황판 상태 목록',exact=True);expect(public_region).to_be_visible()
    for note in notes:expect(public_region).not_to_contain_text(note)
