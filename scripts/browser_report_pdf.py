"""Render the genuine synthetic browser-test AAR through the application UI."""
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:8010'


def export(role_card=False):
    report = json.loads(Path('artifacts/browser/aar-chromium.json').read_text(encoding='utf-8'))
    output = Path('output/pdf')
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1080})
        assert context.request.get(BASE + '/api/v1/auth/profiles').json()['demo'] is True
        assert context.request.post(BASE + '/api/v1/auth/demo', data={'profile': 'facilitator'}).ok
        sessions = context.request.get(BASE + '/api/v1/sessions').json()
        sid = next(session['id'] for session in sessions if session['name'] == report['name'])
        state=context.request.get(BASE+'/api/v1/sessions/'+sid).json()
        page = context.new_page()
        page.goto(BASE)
        if role_card:
            page.get_by_label('훈련 선택').select_option(state['exercise_id'])
            page.get_by_role('button',name='임무 숙지',exact=True).click()
            expect(page.locator('.personal-card h2')).to_be_visible()
        else:
            page.get_by_role('combobox', name='훈련 실행본 선택').select_option(sid)
            expect(page.locator('.exercise-switch')).to_contain_text(report['name'])
            page.get_by_role('button', name='관찰·강평', exact=True).click()
            page.get_by_role('button', name='인쇄·PDF', exact=True).click()
            expect(page.get_by_role('dialog')).to_be_visible()
        page.emulate_media(media='print')
        filename='synthetic-role-card-verification.pdf' if role_card else 'synthetic-aar-verification.pdf'
        page.pdf(path=str(output / filename), format='A4', print_background=True, prefer_css_page_size=True)
        context.close()
        browser.close()
    print('Exported synthetic PDF through the real application UI.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role-card',action='store_true')
    export(parser.parse_args().role_card)
