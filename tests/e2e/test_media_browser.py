"""Opt-in actual synthetic video encoding/playback. AV remains a test fixture."""
import os
import time
import json
from pathlib import Path
from uuid import uuid4
import pytest
from tests.asset_fixtures import synthetic_video
from tests.e2e.test_asset_browser import asset_browser

BASE='http://127.0.0.1:8011'
pytestmark=pytest.mark.skipif(os.getenv('RUN_MEDIA_BROWSER_TESTS')!='1',reason='Explicit synthetic native codec/browser fixture required')


def wait_media(page,predicate,arg=None,timeout=30000):
    """Poll read-only media properties without an eval-based page timer/CSP bypass."""
    deadline=time.monotonic()+timeout/1000
    expression=predicate if '=>' in predicate else '()=>('+predicate+')'
    while time.monotonic()<deadline:
        if page.evaluate(expression,arg):return
        page.wait_for_timeout(100)
    raise AssertionError('Media condition did not become true: '+predicate)


def assert_playback_sync(first,second):
    # Browser calls are sequential; compensate their measured sampling delay.
    # Compare both media clocks at the same wall-clock instant.
    sample='video=>({time:video.currentTime,at:Date.now(),paused:video.paused,seeking:video.seeking,ready:video.readyState,hidden:document.hidden,target:video.closest(".video-playback").querySelector(".media-transport>span").textContent})'
    a=first.evaluate(sample);b=second.evaluate(sample)
    drift=abs((a['time']-b['time'])-(a['at']-b['at'])/1000)
    path=Path('artifacts/browser')/(os.getenv('BROWSER_ENGINE','chromium')+'-media-clock-sample.json')
    path.write_text(json.dumps({'first':a,'second':b,'corrected_drift':drift},ensure_ascii=False,indent=2),encoding='utf-8')
    assert not a['paused'] and not b['paused'] and drift<.6,{'first':a,'second':b,'corrected_drift':drift}


def test_video_intake_event_clock_pause_undo_reconnect_replay_and_aar(asset_browser):
    from playwright.sync_api import expect
    context=asset_browser;engine=os.getenv('BROWSER_ENGINE','chromium');page=context.new_page();page.goto(BASE)
    page.get_by_label('가상 사용자').select_option('facilitator')
    with page.expect_response(lambda response:response.url==BASE+'/api/v1/sessions') as sessions:
        page.get_by_role('button',name='스튜디오 입장',exact=True).click()
    expect(page.get_by_role('heading',name='공동 상황판단 훈련',exact=True)).to_be_visible()
    if sessions.value.json():expect(page.locator('[data-session-id]')).not_to_have_attribute('data-session-id','')
    page.get_by_role('button',name='새 훈련',exact=True).click()
    page.get_by_label('훈련명 (선택)').fill('GUI 합성 영상 시계 '+uuid4().hex[:8])
    with page.expect_response(lambda response:response.url==BASE+'/api/v1/exercises' and response.request.method=='POST') as created:
        page.get_by_role('button',name='훈련 만들기',exact=True).click()
    exercise=created.value.json();eid=exercise['id']
    page.get_by_role('button',name='건물·지도·자원',exact=False).click();panel=page.locator('.asset-panel')
    panel.get_by_role('textbox',name='자산 이름',exact=True).fill('GUI 합성 테스트패턴 영상')
    panel.get_by_role('textbox',name='제작·촬영 주체',exact=True).fill('합성 프레임 생성기')
    panel.get_by_role('textbox',name='자산 원천',exact=True).fill('수학적 테스트패턴과 사인파 · 실제 촬영 아님')
    panel.get_by_role('textbox',name='촬영·자료 기준일',exact=True).fill('2026-11-17')
    panel.get_by_role('textbox',name='이용허락·가공·내부 공개·재사용 범위',exact=True).fill('합성 UI 영상 검증. 실제 AV·기관 권리 승인과 무관.')
    panel.get_by_role('group',name='모델·사진·영상 파일 (15MiB 이하)',exact=True).locator('input').set_input_files({'name':'synthetic.mp4','mimeType':'video/mp4','buffer':synthetic_video()})
    with page.expect_response(lambda response:response.url==BASE+f'/api/v1/exercises/{eid}/assets' and response.request.method=='POST',timeout=60000) as uploaded:
        panel.get_by_role('button',name='격리 수집·검사',exact=True).click()
    intake=uploaded.value.json();assert intake['kind']=='VIDEO' and intake['status']=='VALIDATED'
    assert intake['scan']['provider']=='synthetic-protocol-fixture'
    wait_media(page,"document.querySelector('.asset-video-preview')?.readyState>=1")
    assert panel.locator('video').evaluate('video=>video.duration')>29
    panel.get_by_role('combobox',name='자산 공개 범위',exact=True).select_option('PUBLIC')
    panel.get_by_role('checkbox',name='이용권·공개범위·방향·단위·층/객체 연결을 검토했습니다.',exact=False).check()
    panel.get_by_role('textbox',name='자산 권리·좌표·대조 검토 메모',exact=True).fill('PRIVATE_VIDEO_REVIEW_SENTINEL 합성 권리/메타데이터 검토')
    panel.get_by_role('button',name='검토 후 초안에 연결',exact=True).click()
    expect(panel.locator('.asset-binding-row')).to_have_count(1)
    page.get_by_role('button',name='사건·메시지·분기',exact=False).click();editor=page.locator('.event-media-editor')
    editor.get_by_role('button',name='검토 영상 연결',exact=True).click()
    editor.get_by_role('combobox',name='영상 1 장면 객체',exact=True).select_option('B01-F02-Z01')
    editor.get_by_role('spinbutton',name='영상 1 클립 시작 (초)',exact=True).fill('1')
    editor.get_by_role('spinbutton',name='영상 1 클립 종료 (초)',exact=True).fill('25')
    page.get_by_role('button',name='변경 저장',exact=True).click()
    expect(page.get_by_role('button',name='변경 저장',exact=True)).to_be_disabled()
    page.reload();page.get_by_label('훈련 선택',exact=True).select_option(eid)
    page.get_by_role('button',name='훈련 제작',exact=True).click();page.get_by_role('button',name='사건·메시지·분기',exact=False).click()
    expect(page.get_by_role('spinbutton',name='영상 1 클립 시작 (초)',exact=True)).to_have_value('1')
    expect(page.get_by_role('spinbutton',name='영상 1 클립 종료 (초)',exact=True)).to_have_value('25')
    def version():return context.request.get(BASE+'/api/v1/exercises/'+eid).json()['state_version']
    def change(path,body):
        result=context.request.post(BASE+'/api/v1'+path,data=body,headers={'Idempotency-Key':uuid4().hex});assert result.ok,result.text();return result.json()
    for assignment in exercise['assignments']:
        role=next(item for item in exercise['roles'] if item['id']==assignment['role_id'])
        change(f'/exercises/{eid}/readiness',{'expected_state_version':version(),'person_id':assignment['person_id'],'role_id':assignment['role_id'],'acknowledged_version':role['version'],'answers':{'report':1,'mission':0,'handover':2},'explanation':'합성 영상 흐름 시험. 실제 참가자 숙지 아님.'})
        change(f'/exercises/{eid}/readiness/review',{'expected_state_version':version(),'person_id':assignment['person_id'],'role_id':assignment['role_id'],'approved':True,'note':'합성 자동시험용. 실제 구두/기관 승인 아님.'})
    change(f'/exercises/{eid}/rehearse',{'expected_state_version':version()});change(f'/exercises/{eid}/publish',{'expected_state_version':version(),'note':'합성 영상 흐름 검증. 기관 정규 승인 아님.'})
    session=change(f'/exercises/{eid}/sessions',{});sid=session['id']
    page.reload();selector=page.get_by_role('combobox',name='훈련 실행본 선택');selector.select_option(sid)
    expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
    expect(page.locator('.media-panel')).to_have_count(0)
    public=context.new_page();public.goto(BASE+'/board/'+sid)
    expect(public.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
    future=context.request.get(BASE+'/api/v1/board/sessions/'+sid).json();assert intake['id'] not in str(future)
    assert context.request.get(BASE+f"/api/v1/board/sessions/{sid}/assets/{intake['id']}/content").status==404
    page.get_by_role('button',name='훈련 시작',exact=True).click()
    page.locator('[data-candidate-id="EV-01"]').get_by_role('button',name='승인·공개',exact=True).click()
    for current in [page,public]:
        expect(current.locator('.media-watermark')).to_be_visible()
        wait_media(current,"document.querySelector('.media-panel video')?.readyState>=2 && !document.querySelector('.media-panel video').paused",timeout=30000)
        assert current.locator('.media-panel video').evaluate('video=>video.videoWidth')==320
        assert current.locator('.media-panel video').evaluate('video=>video.muted') is True
        expect(current.locator('.media-caption')).to_contain_text('B01-F02-Z01')
    first=page.locator('.media-panel video');second=public.locator('.media-panel video')
    assert_playback_sync(first,second)
    assert 'PRIVATE_VIDEO_REVIEW_SENTINEL' not in public.locator('body').inner_text()
    page.locator('.media-panel').screenshot(path=f'artifacts/browser/{engine}-media-live.png')
    page.get_by_role('button',name='일시정지',exact=True).click()
    for current in [page,public]:wait_media(current,"document.querySelector('.media-panel video')?.paused")
    frozen=first.evaluate('video=>video.currentTime');page.wait_for_timeout(450)
    assert abs(first.evaluate('video=>video.currentTime')-frozen)<.2
    page.get_by_role('button',name='재개',exact=True).click()
    wait_media(page,"!document.querySelector('.media-panel video').paused")
    wait_media(page,'(previous)=>document.querySelector(".media-panel video").currentTime>previous+.3',arg=frozen)
    public.reload();wait_media(public,"document.querySelector('.media-panel video')?.readyState>=2 && !document.querySelector('.media-panel video').paused",timeout=30000)
    assert_playback_sync(first,public.locator('.media-panel video'))
    page.get_by_role('button',name='일시정지',exact=True).click()
    page.get_by_role('button',name='최근 사건 되돌림',exact=True).click();page.get_by_label('실행 사유',exact=True).fill('합성 영상 사건 되돌림')
    page.get_by_role('button',name='기록 후 실행',exact=True).click()
    expect(page.locator('.media-panel')).to_have_count(0);expect(public.locator('.media-panel')).to_have_count(0)
    assert context.request.get(BASE+f"/api/v1/board/sessions/{sid}/assets/{intake['id']}/content").status==404
    page.get_by_role('button',name='기록·재생',exact=True).click();slider=page.get_by_role('slider',name='재생 시퀀스',exact=True)
    slider.focus();page.keyboard.press('Home');page.keyboard.press('ArrowRight');page.keyboard.press('ArrowRight')
    page.get_by_role('button',name='선택 시점 재생',exact=True).click()
    wait_media(page,"document.querySelector('.media-panel video')?.readyState>=2")
    replay=page.locator('.media-panel video');assert replay.evaluate('video=>video.paused')
    wait_media(page,'Math.abs(document.querySelector(".media-panel video").currentTime-1)<.3')
    page.locator('.media-panel').screenshot(path=f'artifacts/browser/{engine}-media-replay.png')
    slider.focus();page.keyboard.press('Home');page.get_by_role('button',name='선택 시점 재생',exact=True).click();expect(page.locator('.media-panel')).to_have_count(0)
    page.get_by_role('button',name='관찰·강평',exact=True).click();page.get_by_role('button',name='인쇄·PDF',exact=True).click();report=page.get_by_role('dialog')
    expect(report).to_contain_text('GUI 합성 테스트패턴 영상');expect(report).to_contain_text('클립 1~25초');expect(report).not_to_contain_text('PRIVATE_VIDEO_REVIEW_SENTINEL')
    expect(report).to_contain_text('장면 되돌림');expect(report).not_to_contain_text('SCENE_REVERTED')
    if engine=='chromium' and os.getenv('GENERATE_MEDIA_PDF')=='1':
        Path('output/pdf').mkdir(parents=True,exist_ok=True)
        page.pdf(path='output/pdf/media-provenance-chromium.pdf',format='A4',print_background=True,display_header_footer=True,header_template='<span></span>',footer_template='<div style="width:100%;text-align:center;font-size:8px">TRAINING ONLY · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',margin={'top':'14mm','bottom':'16mm','left':'12mm','right':'12mm'})
