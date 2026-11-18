"""Synthetic contracts; no live VWorld key or external request is used."""
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.auth import issue_token
from apps.api.runtime_settings import atomic_json, SettingsError
from screen.server import create_screen_app
from screen.vworld import load, Search, SearchLimit, search_provider, VWorldSettings
from web.server import WebSettings

FAKE_KEY = 'SYNTHETIC_NOT_A_REAL_VWORLD_KEY'


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    private, public = tmp_path / 'private', tmp_path / 'public'
    private.mkdir(); public.mkdir()
    (public / 'index.html').write_text('Synthetic main')
    (public / 'map-frame.html').write_text('<html><head></head><body>synthetic frame</body></html>')
    config = VWorldSettings(enabled=True, browser_key=FAKE_KEY, registered_origin='http://127.0.0.1:8090', terms_confirmed=True)
    atomic_json(private / 'vworld.json', config.model_dump())
    app = create_screen_app(private, WebSettings(port=8090, public_url='http://127.0.0.1:8090'), public)
    with TestClient(app, base_url='http://127.0.0.1:8090') as client:
        assert client.get('/api/screen/maps/vworld/status').status_code == 401
        assert client.get('/map-frame.html').status_code == 401
        client.post('/api/v1/auth/demo', json={'profile': 'facilitator'})
        yield app, client, private
    app.state.store.engine.dispose()


def test_settings_default_disabled_and_invalid_secret_is_redacted(tmp_path):
    assert not load(tmp_path).enabled
    for extra in [{'enabled': True}, {'browser_key': 'private\ninput'}, {'registered_origin': 'https://example.com/?key=bad'}, {'schema_version': True}]:
        with pytest.raises(ValidationError):
            VWorldSettings(**extra)
    (tmp_path / 'vworld.json').write_text(json.dumps({'browser_key': 'PRIVATE_BAD_KEY\n'}))
    with pytest.raises(SettingsError) as error:
        load(tmp_path)
    assert 'PRIVATE_BAD_KEY' not in str(error.value)


def test_search_uses_fixed_https_bounded_results_and_address_title_fallback():
    settings = VWorldSettings(enabled=True, browser_key=FAKE_KEY, registered_origin='http://127.0.0.1:8090', terms_confirmed=True)
    def handler(request):
        assert str(request.url).startswith('https://api.vworld.kr/req/search?')
        q = request.url.params
        assert q['key'] == FAKE_KEY and q['type'] == 'address' and q['category'] == 'road'
        assert q['size'] == '8' and q['query'] == '공개 주소'
        return httpx.Response(200, json={'response': {'status': 'OK', 'result': {'items': [{'id': 'synthetic', 'address': {'road': '가상 도로 1', 'bldnm': '가상 건물'}, 'point': {'x': '127.0', 'y': '37.5'}}]}}})
    result = search_provider(settings, Search(query='공개 주소', kind='road'), httpx.MockTransport(handler))
    assert result == [{'id': 'synthetic', 'title': '가상 건물', 'address': '가상 도로 1', 'latitude': 37.5, 'longitude': 127.0}]
    for response in [httpx.Response(302, headers={'Location': 'https://example.invalid/'}), httpx.Response(200, json={'response': {'status': 'ERROR', 'error': {'text': FAKE_KEY}}}), httpx.Response(200, content=b'x' * (256 * 1024 + 1))]:
        with pytest.raises(HTTPException) as error:
            search_provider(settings, Search(query='공개 주소'), httpx.MockTransport(lambda _: response))
        assert error.value.status_code == 502 and FAKE_KEY not in str(error.value.detail)
    assert search_provider(settings, Search(query='없는 장소'), httpx.MockTransport(lambda _: httpx.Response(200, json={'response': {'status': 'NOT_FOUND'}}))) == []


def test_separate_search_key_never_replaces_the_browser_sdk_key():
    settings = VWorldSettings(enabled=True, browser_key=FAKE_KEY, search_key='SYNTHETIC_SERVER_SEARCH_ONLY',
        registered_origin='http://127.0.0.1:8090', terms_confirmed=True)
    def handler(request):
        assert request.url.params['key'] == 'SYNTHETIC_SERVER_SEARCH_ONLY'
        return httpx.Response(200, json={'response': {'status': 'NOT_FOUND'}})
    assert search_provider(settings, Search(query='공개 장소'), httpx.MockTransport(handler)) == []
    assert settings.browser_key == FAKE_KEY


def test_search_limits_recover_after_window():
    now = [100.]
    limiter = SearchLimit(lambda: now[0])
    for _ in range(12): limiter.take('fictional-user')
    with pytest.raises(HTTPException) as error: limiter.take('fictional-user')
    assert error.value.status_code == 429
    now[0] += 61
    limiter.take('fictional-user')


def test_private_json_atomic_write_recovers_only_transient_windows_share_lock(tmp_path, monkeypatch):
    import apps.api.runtime_settings as runtime
    original = runtime.os.replace
    attempts = []
    def transient(source, target):
        attempts.append(1)
        if len(attempts) == 1:
            error = PermissionError('Synthetic sharing violation')
            error.winerror = 32
            raise error
        return original(source, target)
    monkeypatch.setattr(runtime.os, 'replace', transient)
    monkeypatch.setattr(runtime.time, 'sleep', lambda _: None)
    atomic_json(tmp_path / 'private.json', {'value': 'synthetic'})
    assert len(attempts) == 2 and json.loads((tmp_path / 'private.json').read_text()) == {'value': 'synthetic'}
    def permanent(*_): raise PermissionError('Synthetic real permission denial')
    monkeypatch.setattr(runtime.os, 'replace', permanent)
    with pytest.raises(PermissionError): atomic_json(tmp_path / 'private.json', {'value': 'changed'})
    assert json.loads((tmp_path / 'private.json').read_text()) == {'value': 'synthetic'}


def test_cli_hidden_input_preserves_other_json_and_never_prints_key(tmp_path, monkeypatch, capsys):
    import screen.vworld as vworld
    private = tmp_path / 'private'
    monkeypatch.setattr('sys.argv', ['vworld', 'configure', '--data-dir', str(private)])
    monkeypatch.setattr(vworld.getpass, 'getpass', lambda _: FAKE_KEY)
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    vworld.main()
    assert FAKE_KEY not in capsys.readouterr().out
    assert load(private).enabled and load(private).browser_key == FAKE_KEY
    previous = (private / 'vworld.json').read_bytes()
    monkeypatch.setattr('builtins.input', lambda _: 'n')
    with pytest.raises(SettingsError): vworld.main()
    assert (private / 'vworld.json').read_bytes() == previous
    monkeypatch.setattr('sys.argv', ['vworld', 'check', '--data-dir', str(private)])
    vworld.main()
    assert FAKE_KEY not in capsys.readouterr().out


def test_keys_only_in_authorized_isolated_frame_and_board_tenant_access(system):
    app, client, _ = system
    for path in ['/api/screen/maps/vworld/status', '/api/screen/maps/vworld/bootstrap', '/api/screen/scenarios']:
        response = client.get(path)
        assert response.status_code == 200 and FAKE_KEY not in response.text
    main = client.get('/')
    assert 'unsafe-eval' not in main.headers['Content-Security-Policy']
    frame = client.get('/map-frame.html')
    assert frame.status_code == 200 and FAKE_KEY in frame.text
    policy = frame.headers['Content-Security-Policy']
    assert 'sandbox allow-scripts' in policy and 'allow-same-origin' not in policy
    assert "frame-ancestors http://127.0.0.1:8090" in policy
    assert "connect-src https://*.vworld.kr:*" in policy
    assert frame.headers['Cache-Control'] == 'no-store' and frame.headers['X-Frame-Options'] == 'SAMEORIGIN'
    scenario_id = client.get('/api/screen/scenarios').json()[0]['id']
    value = client.get('/api/screen/scenarios/' + scenario_id).json()
    value['scenario']['site'].update(map_provider='vworld', target_mode='APPROXIMATE')
    assert client.put('/api/screen/scenarios/' + scenario_id, json={'expected_state_version': value['state_version'], 'scenario': value['scenario']}, headers={'Idempotency-Key': uuid4().hex}).status_code == 200
    run = client.post('/api/screen/runs', json={'scenario_id': scenario_id}, headers={'Idempotency-Key': uuid4().hex}).json()['id']
    client.post('/api/v1/auth/demo', json={'profile': 'board'})
    assert client.get('/api/screen/maps/vworld/bootstrap').status_code == 403
    assert client.post('/api/screen/maps/vworld/search', json={'query': '공개 장소'}).status_code == 403
    assert client.get('/map-frame.html').status_code == 403
    assert client.get('/map-frame.html?run_id=' + run).status_code == 200
    assert client.get('/api/screen/board/' + run + '/vworld').json()['frame_url'].endswith('run_id=' + run)
    other = issue_token(app.state.store, {'id': 'other', 'role': 'board', 'organization_id': 'other-org'})
    client.cookies.set('studio_session', other)
    assert client.get('/map-frame.html?run_id=' + run).status_code == 404


def test_search_role_origin_and_error_redaction(system):
    app, client, _ = system
    app.state.vworld_test_transport = httpx.MockTransport(lambda _: httpx.Response(200, json={'response': {'status': 'ERROR', 'error': {'text': FAKE_KEY}}}))
    result = client.post('/api/screen/maps/vworld/search', json={'query': '공개 장소'})
    assert result.status_code == 502 and FAKE_KEY not in result.text
    assert client.post('/api/screen/maps/vworld/search', json={'query': '공개 장소'}, headers={'Origin': 'null'}).status_code == 403
    assert client.post('/api/screen/maps/vworld/search', json={'query': 'x'}).status_code == 422


def test_disabled_config_fails_without_any_provider_request(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    app = create_screen_app(tmp_path / 'private', WebSettings(port=8090, public_url='http://127.0.0.1:8090'))
    with TestClient(app, base_url='http://127.0.0.1:8090') as client:
        client.post('/api/v1/auth/demo', json={'profile': 'facilitator'})
        assert not client.get('/api/screen/maps/vworld/status').json()['configured']
        assert client.get('/api/screen/maps/vworld/bootstrap').status_code == 409
        assert client.post('/api/screen/maps/vworld/search', json={'query': '공개 장소'}).status_code == 409
        assert client.get('/map-frame.html').status_code == 409
    app.state.store.engine.dispose()
