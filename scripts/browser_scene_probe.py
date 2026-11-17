"""Record a bounded authenticated headless scene sample; not target-PC certification."""
import json
import argparse
import hashlib
import os
import re
import statistics
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE=os.getenv('STUDIO_BROWSER_BASE','http://127.0.0.1:8010')


def probe(ui_login=False):
    if BASE not in {'http://127.0.0.1:8010','http://127.0.0.1:8011'}:
        raise ValueError('Only the two isolated local demo servers may be sampled')
    report=json.loads(Path('artifacts/browser/aar-chromium.json').read_text(encoding='utf-8'))
    samples=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1920,'height':1080})
        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(BASE+'/') or route.request.url.startswith('blob:') else route.abort())
        if context.request.get(BASE+'/api/v1/auth/profiles').json()['demo'] is not True:
            raise RuntimeError('Synthetic demo environment required')
        page=context.new_page()
        if not ui_login:assert context.request.post(BASE+'/api/v1/auth/demo',data={'profile':'facilitator'}).ok
        start=time.monotonic()
        page.goto(BASE)
        if ui_login:
            page.get_by_label('가상 사용자').select_option('facilitator')
            page.get_by_role('button',name='스튜디오 입장',exact=True).click()
            page.get_by_role('combobox',name='훈련 실행본 선택').wait_for(state='visible')
        sessions=context.request.get(BASE+'/api/v1/sessions').json()
        sid=next(value['id'] for value in sessions if value['name']==report['name'])
        page.get_by_role('combobox',name='훈련 실행본 선택').select_option(sid)
        expect(page.locator('.exercise-switch')).to_contain_text(report['name'])
        expect(page.locator('[data-session-id]')).to_have_attribute('data-session-id',sid)
        page.locator('.three-host canvas,.scene-fallback[role="region"]').first.wait_for(state='visible')
        # A temporary Suspense placeholder is not a loaded scene. Allow two
        # actual browser animation frames after the selected scene is mounted.
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        ready=round(time.monotonic()-start,3)
        canvas=page.locator('.three-host canvas')
        renderer=canvas.evaluate('(canvas)=>{const gl=canvas.getContext("webgl2");const ext=gl?.getExtension("WEBGL_debug_renderer_info");return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null}') if canvas.count() else None
        for _ in range(10):
            page.wait_for_timeout(2000)
            label=page.locator('.performance').inner_text()
            match=re.search(r'(\d+)\s*FPS',label)
            samples.append({'elapsed_seconds':round(time.monotonic()-start,2),'displayed_fps':int(match.group(1)) if match else None,'display':label,'fallback_visible':page.locator('.scene-fallback').count()>0})
        measured=[sample['displayed_fps'] for sample in samples if sample['displayed_fps'] is not None]
        api_hash=hashlib.sha256()
        for path in sorted(Path('apps/api').glob('*.py')):api_hash.update(path.name.encode());api_hash.update(path.read_bytes())
        result={'kind':'LOCAL_HEADLESS_SCENE_SAMPLE','synthetic_only':True,'base_url':BASE,'browser_version':browser.version,'viewport':[1920,1080],
                'api_source_sha256':api_hash.hexdigest(),'frontend_build_index_sha256':hashlib.sha256(Path('dist/index.html').read_bytes()).hexdigest(),
                'demo_login_through_ui':ui_login,'readiness_scope':'Navigation, optional automated demo UI login, selected session, mounted canvas/genuine 2D fallback and two animation frames; includes automation overhead, excludes human thinking time.',
                'gpu_renderer':renderer,'authenticated_scene_ready_seconds':ready,'samples':samples,
                'median_displayed_fps':statistics.median(measured) if measured else None,
                'target_pc_verified':False,'actual_institutional_projector_verified':False,
                'note':'별도 headless 브라우저의 로컬 합성 장면 표본. 기관 기준 PC/GPU·LAN·실제 프로젝터 수용시험과 구분.'}
        context.close()
        browser.close()
    Path('artifacts/browser/scene-probe-final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'scene_ready_seconds':ready,'median_displayed_fps':result['median_displayed_fps'],'fallback':any(value['fallback_visible'] for value in samples)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui-login',action='store_true')
    probe(parser.parse_args().ui_login)
