"""Opt-in VWorld settings, bounded search, and an isolated public SDK frame."""
import argparse
from collections import defaultdict, deque
import getpass
import html
import json
from pathlib import Path
import re
from threading import Lock
import time
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, Response
from pydantic import Field, ValidationError, model_validator

from apps.api.auth import identity, require
from apps.api.runtime_settings import SettingsError, atomic_json, strict_json
from web.server import canonical_origin, private_directory, read_server_settings
from .contracts import Strict

SEARCH_URL = 'https://api.vworld.kr/req/search'
SDK_URL = 'https://map.vworld.kr/js/webglMapInit.js.do'


class VWorldSettings(Strict):
    schema_version: int = Field(default=1, ge=1, le=1)
    enabled: bool = False
    browser_key: str = Field(default='', max_length=200, repr=False)
    search_key: str = Field(default='', max_length=200, repr=False)
    registered_origin: str = Field(default='', max_length=500)
    terms_confirmed: bool = False

    @model_validator(mode='after')
    def complete(self):
        for value in [self.browser_key, self.search_key]:
            if value and not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', value):
                raise ValueError('Invalid key')
        if self.registered_origin:
            from urllib.parse import urlsplit
            parsed = urlsplit(self.registered_origin)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                raise ValueError('Root HTTP(S) origin required')
            self.registered_origin = canonical_origin(self.registered_origin)
        if self.enabled and not (self.browser_key and self.registered_origin and self.terms_confirmed):
            raise ValueError('Enabled service requires explicit settings')
        return self


def load(directory):
    path = Path(directory) / 'vworld.json'
    if not path.exists():
        return VWorldSettings()
    try:
        return VWorldSettings.model_validate(strict_json(path.read_bytes(), 16384))
    except (SettingsError, ValidationError, ValueError):
        raise SettingsError('브이월드 비공개 JSON의 버전·키·서비스 주소·이용조건 확인을 점검하세요.') from None


class Search(Strict):
    query: str = Field(min_length=2, max_length=120)
    kind: str = Field(default='place', pattern='^(place|road|parcel)$')


class SearchLimit:
    def __init__(self, clock=time.monotonic):
        self.clock, self.lock, self.users, self.total = clock, Lock(), defaultdict(deque), deque()

    def take(self, user):
        with self.lock:
            now = self.clock()
            for key in list(self.users):
                while self.users[key] and self.users[key][0] <= now - 60:
                    self.users[key].popleft()
                if not self.users[key]:
                    del self.users[key]
            while self.total and self.total[0] <= now - 60:
                self.total.popleft()
            if len(self.total) >= 120 or len(self.users[user]) >= 12:
                raise HTTPException(429, '검색 호출이 많습니다. 잠시 후 다시 시도하세요.')
            self.total.append(now)
            self.users[user].append(now)


def search_provider(settings, body, transport=None):
    params = {'service': 'search', 'request': 'search', 'version': '2.0', 'format': 'json',
              'crs': 'EPSG:4326', 'size': 8, 'page': 1, 'query': body.query.strip(),
              'type': 'place' if body.kind == 'place' else 'address',
              'key': settings.search_key or settings.browser_key, 'domain': settings.registered_origin}
    if body.kind != 'place':
        params['category'] = body.kind
    try:
        # Never log a request URL/exception: the provider requires the key in its query.
        with httpx.Client(timeout=httpx.Timeout(6, connect=3), follow_redirects=False, transport=transport) as client:
            with client.stream('GET', SEARCH_URL, params=params) as response:
                if response.status_code != 200:
                    raise ValueError('Provider response')
                chunks, length = [], 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 256 * 1024:
                        raise ValueError('Provider size')
                    chunks.append(chunk)
        data = strict_json(b''.join(chunks), 256 * 1024)['response']
        if data['status'] == 'NOT_FOUND':
            return []
        if data['status'] != 'OK':
            raise ValueError('Provider rejected request')
        result = []
        for item in data['result']['items'][:8]:
            point = item['point']
            if isinstance(point['x'], bool) or isinstance(point['y'], bool):
                raise ValueError('Provider coordinate type')
            latitude, longitude = float(point['y']), float(point['x'])
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError('Provider coordinates')
            address = item.get('address', {})
            result.append({'id': str(item.get('id', ''))[:100], 'title': str(item.get('title') or address.get('bldnm') or address.get('road') or address.get('parcel') or '검색 결과')[:200],
                'address': str(item.get('address', {}).get('road') or item.get('address', {}).get('parcel') or '')[:240],
                'latitude': latitude, 'longitude': longitude})
        return result
    except (httpx.HTTPError, SettingsError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        raise HTTPException(502, '브이월드 검색에 연결하지 못했습니다. 인증키·등록 주소·사용량·서비스 상태를 확인하세요.') from None


def install(app, router, access):
    settings = load(app.state.runtime_directory)
    app.state.vworld_settings = settings
    limiter = SearchLimit()
    origins = {app.state.runtime_settings.public_url, *app.state.runtime_settings.development_origins}

    def ready():
        return settings.enabled and settings.registered_origin in origins

    def bootstrap(run_id=None):
        if not ready():
            raise HTTPException(409, '브이월드 설정이 필요합니다. 비공개 인증키·등록 주소와 이용조건을 확인하세요.')
        return {'frame_url': '/map-frame.html' + ('?' + urlencode({'run_id': run_id}) if run_id else ''),
                'version': '3.0', 'origin': settings.registered_origin}

    @router.get('/maps/vworld/status')
    def status(user=Depends(identity)):
        require(user, 'view')
        return {'provider': 'vworld', 'configured': bool(ready()), 'enabled': settings.enabled,
                'registered_origin': settings.registered_origin, 'real_service_verified': False,
                'coverage': '제공되는 지역·건물별3D/실사는 실제 현장에서 확인해야 합니다.'}

    @router.get('/maps/vworld/bootstrap')
    def preview_bootstrap(user=Depends(identity)):
        require(user, 'edit')
        return bootstrap()

    @app.get('/map-frame.html')
    def frame(run_id: str | None = None, user=Depends(identity)):
        if run_id:
            run, _ = access(run_id, user)
            if run['scene']['site'].get('map_provider', 'local') != 'vworld':
                raise HTTPException(409, '브이월드 실행본이 아닙니다.')
        else:
            require(user, 'edit')
        bootstrap(run_id)
        path = app.state.frontend_directory / 'map-frame.html'
        if not path.is_file():
            raise HTTPException(503, '브이월드 화면 빌드가 필요합니다.')
        sdk = SDK_URL + '?' + urlencode({'version': '3.0', 'apiKey': settings.browser_key})
        # A parser-inserted script preserves the SDK's official document.write loader.
        content = path.read_text(encoding='utf-8').replace('<head>', '<head><script src="' + html.escape(sdk, quote=True) + '"></script>', 1)
        return Response(content, media_type='text/html')

    @router.get('/board/{id}/vworld')
    def board_bootstrap(id: str, user=Depends(identity)):
        run, _ = access(id, user)
        if run['scene']['site'].get('map_provider', 'local') != 'vworld':
            raise HTTPException(409, '브이월드를 사용하는 실행본이 아닙니다.')
        return bootstrap(id)

    @router.post('/maps/vworld/search')
    def search(body: Search, user=Depends(identity)):
        require(user, 'edit')
        if not ready():
            raise HTTPException(409, '브이월드 인증키와 서비스 URL 설정이 필요합니다.')
        if not body.query.strip() or any(ord(c) < 32 for c in body.query):
            raise HTTPException(422, '검색할 장소나 주소를 확인하세요.')
        limiter.take(user['organization_id'] + ':' + user['id'])
        return {'items': search_provider(settings, body, getattr(app.state, 'vworld_test_transport', None)),
                'source': '브이월드 검색API · 위치/건물 정확도 별도 확인'}

    @app.middleware('http')
    async def isolate_frame(request, call_next):
        response = await call_next(request)
        if request.url.path == '/map-frame.html':
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Referrer-Policy'] = 'origin'
            response.headers['Content-Security-Policy'] = (
                f"default-src 'none'; script-src {' '.join(sorted(origins))} 'unsafe-inline' 'unsafe-eval' https://*.vworld.kr:*; "
                f"style-src {' '.join(sorted(origins))} 'unsafe-inline' https://*.vworld.kr:*; img-src data: blob: https://*.vworld.kr:*; "
                "connect-src https://*.vworld.kr:*; font-src data: https://*.vworld.kr:*; "
                "worker-src blob: https://*.vworld.kr:*; child-src blob:; frame-src 'none'; "
                f"object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors {' '.join(sorted(origins))}; sandbox allow-scripts")
        else:
            policy = response.headers.get('Content-Security-Policy', '')
            response.headers['Content-Security-Policy'] = re.sub(r"frame-src [^;]*", "frame-src 'self'", policy)
        # Only public build resources may be imported by the opaque-origin map frame.
        if request.url.path.startswith('/assets/') and request.url.path.endswith(('.js', '.css')):
            response.headers['Access-Control-Allow-Origin'] = '*'
        return response


def main():
    parser = argparse.ArgumentParser(description='브이월드 비공개 JSON 설정. 키는 숨김 입력하며 출력하지 않습니다.')
    parser.add_argument('operation', choices=['configure', 'check', 'disable'])
    parser.add_argument('--data-dir', type=Path, default=Path('runtime/screen'))
    args = parser.parse_args()
    directory = private_directory(args.data_dir, Path(__file__).parent / 'dist')
    server = read_server_settings(directory, {'port': 8090} if not (directory / 'server.json').exists() else None)
    settings = load(directory)
    if args.operation == 'configure':
        print('등록할 서비스 URL:', server.public_url)
        print('발급 화면에서 WebGL3D·검색 사용과 정확한 서비스 주소/이용조건을 확인하세요. 키를 채팅에 보내지 마세요.')
        key = getpass.getpass('본인 발급 브이월드 키 (숨김): ').strip()
        search_key = getpass.getpass('검색 전용 키가 따로 있으면 입력, 같은 키면 Enter (숨김): ').strip()
        confirmed = input('서비스 주소 등록·이용조건과 지도 좌표 외부 조회를 확인했습니까? [y/N]: ').strip().lower() == 'y'
        if not confirmed:
            raise SettingsError('확인되지 않아 저장하지 않았습니다.')
        try:
            settings = VWorldSettings(enabled=True, browser_key=key, search_key=search_key, registered_origin=server.public_url, terms_confirmed=True)
        except ValidationError:
            raise SettingsError('키 형식을 확인하세요. 입력값은 출력하지 않습니다.') from None
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / 'vworld.json', settings.model_dump())
        print('비공개 JSON을 저장했습니다. SCREEN 서버 재시작 후 현장 설정에서 브이월드를 선택하세요.')
    elif args.operation == 'disable':
        settings.enabled = False
        atomic_json(directory / 'vworld.json', settings.model_dump())
        print('브이월드를 비활성으로 저장했습니다. 서버를 재시작하세요.')
    else:
        print(json.dumps({'enabled': settings.enabled, 'key_present': bool(settings.browser_key),
            'origin_matches': settings.registered_origin == server.public_url, 'terms_confirmed': settings.terms_confirmed,
            'actual_service_verified': False}))


if __name__ == '__main__':
    try:
        main()
    except (SettingsError, OSError):
        raise SystemExit('브이월드 비공개 설정을 완료하지 못했습니다. 파일 권한·설정 형식을 확인하세요.') from None
