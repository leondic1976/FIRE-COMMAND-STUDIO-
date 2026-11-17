"""Real browser interactions against a loopback-only synthetic HTTP adapter."""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark=pytest.mark.skipif(os.getenv('RUN_EXTERNAL_BROWSER_TESTS')!='1',reason='Explicit synthetic UI fixture required')
BASE='http://127.0.0.1:8011'


def test_public_data_review_apply_and_reference_labels():
    from playwright.sync_api import sync_playwright,expect
    engine=os.getenv('BROWSER_ENGINE','chromium')
    assert engine in {'chromium','firefox'}
    Path('artifacts/browser').mkdir(parents=True,exist_ok=True)
    with sync_playwright() as pw:
        browser=getattr(pw,engine).launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        errors=[]
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        # The application and provider fixtures must not contact an outside host.
        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(BASE+'/') else route.abort())
        page.goto(BASE)
        page.get_by_label('가상 사용자').select_option('facilitator')
        with page.expect_response(lambda response:response.url==BASE+'/api/v1/sessions') as initial_sessions:
            page.get_by_role('button',name='스튜디오 입장').click()
        expect(page.get_by_role('heading',name='공동 상황판단 훈련',exact=True)).to_be_visible()
        if initial_sessions.value.json():
            expect(page.locator('[data-session-id]')).not_to_have_attribute('data-session-id','')
        page.get_by_role('button',name='새 훈련',exact=True).click()
        try:
            expect(page.get_by_role('dialog',name='새 훈련 만들기',exact=True)).to_be_visible()
            page.get_by_label('훈련명 (선택)').fill('합성 공공자료 UI 시험 '+uuid4().hex[:8])
        except Exception:
            page.screenshot(path=f'artifacts/browser/{engine}-external-create-failure.png',full_page=True)
            Path(f'artifacts/browser/{engine}-external-create-failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
            raise
        with page.expect_response(lambda r:r.url==BASE+'/api/v1/exercises' and r.request.method=='POST') as created:
            page.get_by_role('button',name='훈련 만들기',exact=True).click()
        exercise_id=created.value.json()['id']
        page.get_by_role('button',name='훈련 대상물',exact=False).click()
        panel=page.locator('.external-data-panel')
        # Raw intake must leave the exercise unchanged until explicit review.
        panel.get_by_role('textbox',name='시군구 코드 (5자리)',exact=True).fill('11680')
        panel.get_by_role('textbox',name='법정동 코드 (5자리)',exact=True).fill('10300')
        panel.get_by_role('textbox',name='본번 (4자리)',exact=True).fill('0012')
        panel.get_by_role('button',name='수집·미리보기',exact=True).click()
        expect(panel.get_by_role('heading',name='수집 후보 1개 / 제공처 전체 1개')).to_be_visible()
        data=context.request.get(BASE+'/api/v1/exercises/'+exercise_id).json()['exercise']
        assert data['subject']['buildings'][0]['floors']==3 and not data['subject']['external_layers']
        panel.get_by_label('건물명',exact=True).check()
        panel.get_by_label('출처·이용권·기준시각·좌표·선택 속성을 검토했고 훈련 초안에 반영합니다. 기관 정규 출시 승인이 아닙니다.',exact=True).check()
        private_note='합성 자료 검토 메모 · 공동화면 공개 금지'
        panel.get_by_role('textbox',name='기준자료 검토·정정 메모').fill(private_note)
        panel.screenshot(path=f'artifacts/browser/{engine}-external-review.png')
        # A real-source import needs an explicit target-mode choice.
        panel.get_by_role('button',name='검토한 항목을 초안에 반영',exact=True).click()
        expect(page.get_by_text('실제 공간자료는 실제/혼합 대상물 모드를 명시한 뒤 반영하세요.',exact=False)).to_be_visible()
        page.get_by_role('combobox',name='대상물 구분',exact=True).select_option('REAL')
        panel.get_by_role('button',name='검토한 항목을 초안에 반영',exact=True).click()
        expect(panel.locator('.external-preview')).to_have_count(0)
        page.get_by_role('button',name='건물·지도·자원',exact=False).click()
        expect(page.get_by_role('spinbutton',name='층수',exact=True)).to_have_value('4')
        expect(page.get_by_role('textbox',name='건물명',exact=True)).to_have_value('합성 API 시험동 · 실제 건물 아님')
        page.get_by_role('button',name='훈련 대상물',exact=False).click()
        # Weather is a time/grid reference, not an automatic scene-wind command.
        panel.get_by_role('combobox',name='공공 자료 종류',exact=True).select_option('weather')
        panel.get_by_role('group',name='관측 기준일 (KST)',exact=True).locator('input').fill('2026-11-17')
        panel.get_by_role('group',name='관측 기준시각 (KST 정시)',exact=True).locator('input').fill('06:00')
        panel.get_by_role('spinbutton',name='관측 격자 NX',exact=True).fill('60')
        panel.get_by_role('spinbutton',name='관측 격자 NY',exact=True).fill('127')
        panel.get_by_role('button',name='수집·미리보기',exact=True).click()
        expect(panel.get_by_text('2.5 m/s',exact=False)).to_be_visible()
        panel.get_by_label('출처·이용권·기준시각·좌표·선택 속성을 검토했고 훈련 초안에 반영합니다. 기관 정규 출시 승인이 아닙니다.',exact=True).check()
        panel.get_by_role('textbox',name='기준자료 검토·정정 메모').fill(private_note)
        panel.get_by_role('button',name='검토한 항목을 초안에 반영',exact=True).click()
        expect(panel.locator('.external-preview')).to_have_count(0)
        panel.get_by_role('combobox',name='공공 자료 종류',exact=True).select_option('hydrant')
        panel.get_by_role('button',name='수집·미리보기',exact=True).click()
        panel.get_by_label('수집 항목 SYNTHETIC-H02 선택',exact=True).check()
        panel.get_by_label('출처·이용권·기준시각·좌표·선택 속성을 검토했고 훈련 초안에 반영합니다. 기관 정규 출시 승인이 아닙니다.',exact=True).check()
        panel.get_by_role('textbox',name='기준자료 검토·정정 메모').fill(private_note)
        panel.get_by_role('button',name='검토한 항목을 초안에 반영',exact=True).click()
        expect(panel.locator('.external-preview')).to_have_count(0)
        data=context.request.get(BASE+'/api/v1/exercises/'+exercise_id).json()['exercise']
        assert len(data['subject']['external_layers'])==3
        water=[f for f in data['subject']['features'] if f['data_origin']=='REFERENCE']
        assert len(water)==1 and water[0]['state']['water']=='UNCONFIRMED'
        assert not any('wind' in f['state'] for f in data['subject']['features'])
        assert len(data['external_reviews'])==3
        page.reload()
        page.get_by_label('훈련 선택').select_option(exercise_id)
        page.get_by_role('button',name='훈련 제작',exact=True).click()
        page.get_by_role('button',name='훈련 대상물',exact=False).click()
        panel=page.locator('.external-data-panel')
        panel.locator('.reference-facts summary').click()
        expect(panel.get_by_role('heading',name='기상청 초단기실황',exact=True)).to_be_visible()
        expect(panel.locator('.reference-facts')).not_to_contain_text(private_note)
        panel.screenshot(path=f'artifacts/browser/{engine}-external-applied.png')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'artifacts/browser/{engine}-external-mobile.png',full_page=True)
        # Existing baseline tests cover full readiness UI. Prepare this fixture
        # through the same server gates to inspect the frozen AAR references.
        def version():
            return context.request.get(BASE+'/api/v1/exercises/'+exercise_id).json()['state_version']
        def change(path,body):
            response=context.request.post(BASE+'/api/v1'+path,data=body,headers={'Idempotency-Key':uuid4().hex})
            assert response.ok,response.text()
            return response.json()
        for assignment in data['assignments']:
            role=next(role for role in data['roles'] if role['id']==assignment['role_id'])
            change(f'/exercises/{exercise_id}/readiness',{'expected_state_version':version(),'person_id':assignment['person_id'],
                'role_id':assignment['role_id'],'acknowledged_version':role['version'],
                'answers':{'report':1,'mission':0,'handover':2},'explanation':'합성 API 준비. 실제 참가자 이해도 시험 아님.'})
            change(f'/exercises/{exercise_id}/readiness/review',{'expected_state_version':version(),'person_id':assignment['person_id'],
                'role_id':assignment['role_id'],'approved':True,'note':'합성 UI 시험 준비. 실제 기관 검토 아님.'})
        change(f'/exercises/{exercise_id}/rehearse',{'expected_state_version':version()})
        change(f'/exercises/{exercise_id}/publish',{'expected_state_version':version(),'note':'합성 UI 자료 스냅샷 시험. 기관 승인 아님.'})
        session=change(f'/exercises/{exercise_id}/sessions',{})
        page.set_viewport_size({'width':1440,'height':1000})
        page.reload()
        selector=page.get_by_role('combobox',name='훈련 실행본 선택')
        if selector.input_value()!=session['id']:selector.select_option(session['id'])
        expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',session['id'])
        selector.select_option(session['id'])
        expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',session['id'])
        page.get_by_role('button',name='관찰·강평',exact=True).click()
        page.get_by_role('button',name='인쇄·PDF',exact=True).click()
        report=page.get_by_role('dialog')
        expect(report.get_by_role('heading',name='7. 발행 당시 공공 기준자료',exact=True)).to_be_visible()
        expect(report).to_contain_text('2.5 m/s')
        expect(report).to_contain_text('현재 사용 가능 여부 미확인')
        expect(report).not_to_contain_text(private_note)
        if engine=='chromium' and os.getenv('GENERATE_EXTERNAL_PDF')=='1':
            Path('output/pdf').mkdir(parents=True,exist_ok=True)
            page.pdf(path='output/pdf/external-reference-chromium.pdf',format='A4',print_background=True,
                display_header_footer=True,header_template='<span></span>',
                footer_template='<div style="width:100%;text-align:center;font-size:8px">TRAINING ONLY · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                margin={'top':'14mm','bottom':'16mm','left':'12mm','right':'12mm'})
        page.keyboard.press('Escape')
        Path(f'artifacts/browser/{engine}-external-errors.json').write_text(json.dumps(errors,ensure_ascii=False),encoding='utf-8')
        context.close()
        browser.close()
        assert not errors,errors
