"""Background browser checks for the static installer download page."""
import json
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


BASE = 'http://127.0.0.1:8020'
OUT = Path('artifacts/download-site')
RELEASE = json.loads(Path('site/release.json').read_text(encoding='utf-8'))


def verify():
    OUT.mkdir(parents=True, exist_ok=True)
    result = []
    with sync_playwright() as playwright:
        for engine in ['chromium', 'firefox']:
            browser = getattr(playwright, engine).launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            errors, outside = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(BASE + '/') else (outside.append(route.request.url.split('?')[0]), route.abort())[-1])
            for width in [1440, 390]:
                page.set_viewport_size({'width': width, 'height': 1000})
                page.goto(BASE + '/')
                expect(page.locator('#download-state')).to_contain_text('v0.1.0')
                assert page.locator('.download').count() == 2
                for anchor in page.locator('.download').all():
                    expect(anchor).to_have_attribute('href', RELEASE['download_url'])
                    assert anchor.get_attribute('aria-disabled') is None
                expect(page.locator('#sha')).to_have_text(RELEASE['sha256'])
                expect(page.locator('#signature')).to_contain_text('전자서명 없음')
                expect(page.locator('#release-link')).to_have_attribute('href', RELEASE['release_url'])
                assert page.locator('img[src="assets/board-preview.png"]').evaluate('(el)=>el.complete&&el.naturalWidth===1380')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.keyboard.press('Tab')
                expect(page.locator('.skip')).to_be_focused()
                page.keyboard.press('Enter')
                assert page.url.endswith('#main')
                page.locator('#copy-sha').click()
                expect(page.locator('#copy-status')).not_to_be_empty()
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(OUT / f'{engine}-{width}.png'), full_page=True)
                result.append({'engine': engine, 'width': width, 'download_checksum_keyboard_layout': True})
            # Corrupted or incomplete metadata must never enable another download source.
            for change in [{'download_url': 'https://example.invalid/other.exe'}, {'status': 'preparing'}, {'sha256': 'invalid'}]:
                bad = {**RELEASE, **change}
                page.route('**/release.json', lambda route, request, body=bad: route.fulfill(json=body))
                page.goto(BASE + '/')
                expect(page.locator('#download-state')).not_to_contain_text('상태를 확인하고 있습니다')
                for anchor in page.locator('.download').all():
                    expect(anchor).to_have_attribute('aria-disabled', 'true')
                    expect(anchor).to_have_attribute('href', '#release')
                page.unroute('**/release.json')
            assert not errors and not outside, (errors, outside)
            context.close()
            browser.close()
    return {'base_url': BASE, 'responsive_browser_checks': result, 'invalid_release_metadata_rejected': 6,
            'page_errors': 0, 'external_runtime_requests': 0, 'synthetic_image_only': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=BASE, choices=[BASE, 'https://leondic1976.github.io/FIRE-COMMAND-STUDIO-'])
    args = parser.parse_args()
    BASE = args.base
    if BASE.startswith('https://'):
        OUT = Path('artifacts/github-pages')
    result = verify()
    (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
