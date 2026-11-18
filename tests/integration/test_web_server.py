import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.runtime_settings import SettingsError
from web.server import WebSettings, create_web_app, read_server_settings


@pytest.fixture
def isolated_environment(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('VITE_KAKAO_MAPS_APPROVED', raising=False)
    monkeypatch.delenv('VITE_KAKAO_JAVASCRIPT_KEY', raising=False)


def test_web_build_is_served_with_deep_links_and_private_json_stays_private(tmp_path, isolated_environment):
    frontend = tmp_path / 'public'
    (frontend / 'assets').mkdir(parents=True)
    (frontend / 'index.html').write_text('<html>synthetic web frontend</html>')
    (frontend / 'assets/app.js').write_text('/* synthetic */')
    data = tmp_path / 'private'
    app = create_web_app(data, frontend_directory=frontend)
    try:
        with TestClient(app, base_url='http://127.0.0.1:8080') as client:
            assert client.get('/').text == client.get('/board/synthetic').text == '<html>synthetic web frontend</html>'
            assert client.get('/assets/app.js').status_code == 200
            assert client.get('/settings.json').text == '<html>synthetic web frontend</html>'
            assert client.get('/api/v1/settings.json').status_code == 404
            assert (data / 'settings.json').is_file() and (data / 'server.json').is_file()
            assert client.get('/api/v1/runtime/map-config').json() == {'approved': False, 'public_key': ''}
            assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}, headers={'Origin': 'https://other.invalid'}).status_code == 403
            assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}, headers={'Origin': 'http://127.0.0.1:8080'}).status_code == 200
            assert client.get('/api/v1/health', headers={'Host': 'attacker.invalid'}).status_code == 400
    finally:
        app.state.store.engine.dispose()


def test_production_requires_accounts_and_secure_cookies(tmp_path, isolated_environment):
    import os
    original_cookie_setting = os.getenv('COOKIE_SECURE')
    from apps.api.auth import password_hash
    from apps.api.storage import accounts
    settings = WebSettings(mode='production', host='0.0.0.0', public_url='https://training.invalid')
    app = create_web_app(tmp_path / 'data', settings)
    assert os.getenv('COOKIE_SECURE') == original_cookie_setting
    identity = {'id': 'synthetic-admin', 'name': 'Synthetic administrator', 'role': 'admin', 'organization_id': 'synthetic-web', 'person_id': None}
    try:
        with app.state.store.engine.begin() as connection:
            connection.execute(accounts.insert().values(organization_id='synthetic-web', username='synthetic-admin',
                password_hash=password_hash('synthetic-test-password-only'), identity=identity))
        with TestClient(app, base_url='https://training.invalid') as client:
            assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code in (403, 404)
            assert client.get('/api/v1/auth/me').status_code == 401
            result = client.post('/api/v1/auth/login', json={'organization_id': 'synthetic-web', 'username': 'synthetic-admin', 'password': 'synthetic-test-password-only'}, headers={'Origin': settings.public_url})
            assert result.status_code == 200 and 'Secure' in result.headers['set-cookie'] and 'HttpOnly' in result.headers['set-cookie']
            assert client.get('/api/v1/auth/me').json()['organization_id'] == 'synthetic-web'
    finally:
        app.state.store.engine.dispose()


@pytest.mark.parametrize('values', [
    {'host': '0.0.0.0'}, {'mode': 'production'},
    {'mode': 'production', 'public_url': 'https://training.invalid', 'development_origins': ['http://127.0.0.1:8015']},
    {'public_url': 'http://example.invalid'}, {'public_url': 'http://user:secret@127.0.0.1:8080'},
    {'public_url': 'http://127.0.0.1:8080/path'}, {'public_url': 'http://127.0.0.1:8080?token=value'},
])
def test_unsafe_web_configuration_is_rejected(values):
    with pytest.raises(ValidationError):
        WebSettings(**values)


def test_server_json_changes_are_versioned_and_keep_a_backup(tmp_path):
    initial = read_server_settings(tmp_path)
    changed = read_server_settings(tmp_path, {'port': 8081})
    assert changed.port == 8081 and changed.public_url == 'http://127.0.0.1:8081'
    assert json.loads((tmp_path / 'server.previous.json').read_text()) == initial.model_dump()
    assert read_server_settings(tmp_path) == changed
    (tmp_path / 'server.json').write_text('{"schema_version":99}')
    with pytest.raises(SettingsError):
        read_server_settings(tmp_path)


def test_public_directory_cannot_be_used_as_private_storage():
    from pathlib import Path
    with pytest.raises(SettingsError):
        create_web_app(Path('web/dist/private'))


def test_parallel_runtime_construction_never_inherits_another_instances_database(tmp_path, isolated_environment, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from apps.api.runtime_settings import SettingsDocument, runtime_environment
    import web.server as module
    ready = Event()
    load = module.load_settings

    def observed_load(directory):
        ready.set()
        return load(directory)

    monkeypatch.setattr(module, 'load_settings', observed_load)
    wrong = tmp_path / 'another-instance.db'
    with ThreadPoolExecutor(max_workers=1) as executor:
        with runtime_environment(SettingsDocument(), {'DATABASE_URL': 'sqlite:///' + wrong.as_posix()}):
            future = executor.submit(create_web_app, tmp_path / 'own-data')
            assert ready.wait(5)
        app = future.result(timeout=15)
    try:
        assert app.state.store.engine.url.database == (tmp_path / 'own-data/storage/studio.db').as_posix()
        assert not wrong.exists()
    finally:
        app.state.store.engine.dispose()
