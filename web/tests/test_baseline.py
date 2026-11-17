"""Opt-in shared UI baseline; this is not a completed browser-only runtime."""
import os
from pathlib import Path

import httpx
import pytest


BASE = 'http://127.0.0.1:8015'
OUT = Path('artifacts/web-workspace-baseline')
pytestmark = pytest.mark.skipif(os.getenv('RUN_WEB_BASELINE_TESTS') != '1', reason='Isolated workspace baseline only')


@pytest.mark.parametrize('engine', ['chromium', 'firefox'])
def test_shared_web_workspace_bootstrap(engine):
    from playwright.sync_api import sync_playwright, expect

    with httpx.Client(base_url=BASE, trust_env=False) as client:
        assert client.get('/api/v1/health').json()['training_only']
        assert client.get('/api/v1/auth/profiles').json()['demo']
        assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'},
                           headers={'Origin': 'https://untrusted.invalid'}).status_code == 403
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        errors, outside = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(BASE + '/') else (outside.append(route.request.url.split('?')[0]), route.abort())[-1])
        try:
            page.goto(BASE)
            expect(page).to_have_title('FIRE-COMMAND STUDIO · 웹 훈련')
            page.get_by_label('가상 사용자').select_option('facilitator')
            page.get_by_role('button', name='스튜디오 입장').click()
            expect(page.get_by_role('heading', name='공동 상황판단 훈련', exact=True)).to_be_visible()
            expect(page.locator('.scene-view canvas')).to_be_visible(timeout=20000)
            assert page.locator('.building-strip button').count() == 3
            expect(page.locator('.scene-watermark')).to_contain_text('훈련용')
            page.get_by_role('button', name='훈련 제작', exact=True).click()
            expect(page.get_by_role('heading', name='훈련 제작 스튜디오', exact=True)).to_be_visible()
            assert not errors and not outside, (errors, outside)
            page.screenshot(path=str(OUT / (engine + '.png')), full_page=True)
        finally:
            context.close()
            browser.close()
