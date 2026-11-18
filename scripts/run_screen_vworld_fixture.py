"""Test-only synthetic provider configuration. Never use for a real service."""
import argparse
from pathlib import Path

import httpx
import uvicorn

from apps.api.runtime_settings import atomic_json
from screen.server import create_screen_app
from screen.vworld import VWorldSettings
from web.server import WebSettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('runtime/screen-vworld-browser-ci'))
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    runtime = (Path.cwd() / 'runtime').resolve()
    if not directory.is_relative_to(runtime) or not directory.name.startswith('screen-vworld-'):
        raise SystemExit('A new isolated runtime/screen-vworld-* fixture directory is required')
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory / 'vworld.json', VWorldSettings(enabled=True,
        browser_key='SYNTHETIC_NOT_A_REAL_VWORLD_KEY', registered_origin='http://127.0.0.1:8093', terms_confirmed=True).model_dump())
    app = create_screen_app(directory, WebSettings(port=8093, public_url='http://127.0.0.1:8093'))
    app.state.vworld_test_transport = httpx.MockTransport(lambda _: httpx.Response(200, json={
        'response': {'status': 'OK', 'result': {'items': [{'id': 'synthetic-place', 'title': '가상 브이월드 검색 건물',
            'address': {'road': '가상 검증 도로 1'}, 'point': {'x': '127.0', 'y': '37.5'}}]}}}))
    uvicorn.run(app, host='127.0.0.1', port=8093, access_log=False)


if __name__ == '__main__':
    main()
