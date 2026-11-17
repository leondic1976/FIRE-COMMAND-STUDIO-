"""Local desktop lifecycle uses real loopback HTTP and isolated synthetic data."""
import json
import os
from pathlib import Path
import socket

import httpx
import pytest

from apps.desktop import APPLICATION_ID
from apps.desktop.runtime import AlreadyRunning, DesktopService, InstanceLock, SETTINGS_KEYS, data_directory, running_instance, stop_instance


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in ['PYTHON_DOTENV_DISABLED','TRAINING_MODE','COOKIE_SECURE','AI_PROVIDER','ALLOWED_ORIGINS','DATABASE_URL', *SETTINGS_KEYS]:
        monkeypatch.setenv(key, os.environ.get(key, ''))


def test_default_storage_is_per_user_and_not_installation(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'user-local'))
    assert data_directory() == (tmp_path / 'user-local' / 'FIRECommandStudio').resolve()
    with pytest.raises(ValueError):
        data_directory(Path(tmp_path.anchor))


def test_instance_lock_rejects_peer_and_can_be_reacquired(tmp_path):
    first, second = InstanceLock(tmp_path), InstanceLock(tmp_path)
    first.acquire()
    try:
        with pytest.raises(AlreadyRunning):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_port_collision_shutdown_authority_and_stale_descriptor(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        service = DesktopService(tmp_path, port)
        try:
            url = service.start()
            assert int(url.rsplit(':', 1)[1]) != port
            assert service.socket.getsockname()[0] == '127.0.0.1'
            with httpx.Client(base_url=url, trust_env=False) as client:
                assert client.get('/_desktop/status').json()['application'] == APPLICATION_ID
                assert client.post('/_desktop/shutdown').status_code == 403
                assert client.post('/_desktop/shutdown', headers={'X-Desktop-Key':'synthetic-invalid'}).status_code == 403
                assert client.post('/_desktop/shutdown', headers={'Origin':'https://untrusted.invalid'}).status_code == 403
            assert running_instance(tmp_path)['url'] == url
            with pytest.raises(AlreadyRunning):
                DesktopService(tmp_path, 0).start()
            assert stop_instance(tmp_path)
        finally:
            service.stop()
        assert running_instance(tmp_path) is None
        assert not (tmp_path / 'instance.json').exists()
    (tmp_path / 'instance.json').write_text(json.dumps({'port':'https://untrusted.invalid'}))
    assert running_instance(tmp_path) is None
    assert stop_instance(tmp_path) is False


def test_desktop_restart_preserves_synthetic_exercise_and_database(tmp_path):
    service = DesktopService(tmp_path, 0)
    try:
        with httpx.Client(base_url=service.start(), trust_env=False) as client:
            assert client.post('/api/v1/auth/demo', json={'profile':'facilitator'}).status_code == 200
            response = client.post('/api/v1/exercises', json={'template':'factory','name':'합성 설치형 재시작 검증'})
            assert response.status_code == 201
            eid = response.json()['id']
    finally:
        service.stop()
    assert (tmp_path / 'storage' / 'studio.db').is_file()
    restarted = DesktopService(tmp_path, 0)
    try:
        with httpx.Client(base_url=restarted.start(), trust_env=False) as client:
            assert client.post('/api/v1/auth/demo', json={'profile':'facilitator'}).status_code == 200
            assert client.get('/api/v1/exercises/' + eid).json()['exercise']['name'] == '합성 설치형 재시작 검증'
    finally:
        restarted.stop()


def test_backup_restore_and_corruption_preserve_current_records(tmp_path):
    service = DesktopService(tmp_path, 0)
    try:
        url = service.start()
        with httpx.Client(base_url=url, trust_env=False) as client:
            client.post('/api/v1/auth/demo', json={'profile':'facilitator'})
            first = client.post('/api/v1/exercises', json={'template':'factory','name':'합성 복원 기준'}).json()['id']
            backup = tmp_path / 'chosen-backup.db'
            service.create_backup(backup)
            second = client.post('/api/v1/exercises', json={'template':'factory','name':'합성 복원 전 보존'}).json()['id']
        manifest = backup.with_suffix('.db.manifest.json')
        original = manifest.read_bytes()
        metadata = json.loads(original)
        metadata['sha256'] = '0' * 64
        manifest.write_text(json.dumps(metadata))
        with pytest.raises(ValueError, match='해시'):
            service.restore_backup(backup)
        assert running_instance(tmp_path)['url'] == url
        manifest.write_bytes(original)
        result = service.restore_backup(backup)
        assert result['restored'] and (tmp_path / 'backups' / result['previous_backup']).is_file()
        with httpx.Client(base_url=service.url, trust_env=False) as client:
            client.post('/api/v1/auth/demo', json={'profile':'facilitator'})
            assert client.get('/api/v1/exercises/' + first).status_code == 200
            assert client.get('/api/v1/exercises/' + second).status_code == 404
        from scripts.backup_restore import restore
        previous = tmp_path / 'check-previous.db'
        restore(tmp_path / 'backups' / result['previous_backup'], previous)
        import sqlite3
        with sqlite3.connect(previous) as connection:
            assert connection.execute('SELECT count(*) FROM records WHERE id=?', (second,)).fetchone()[0] == 1
    finally:
        service.stop()


def test_restore_start_failure_rolls_back_to_current_data(tmp_path, monkeypatch):
    service = DesktopService(tmp_path, 0)
    try:
        with httpx.Client(base_url=service.start(), trust_env=False) as client:
            client.post('/api/v1/auth/demo', json={'profile':'facilitator'})
            old = tmp_path / 'older.db'
            service.create_backup(old)
            created = client.post('/api/v1/exercises', json={'template':'factory','name':'합성 복원 실패 복구'}).json()['id']
        start = service.start
        attempts = 0
        def fail_once():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError('Synthetic restored-start failure')
            return start()
        monkeypatch.setattr(service, 'start', fail_once)
        with pytest.raises(RuntimeError, match='Synthetic'):
            service.restore_backup(old)
        assert attempts == 2 and running_instance(tmp_path)
        with httpx.Client(base_url=service.url, trust_env=False) as client:
            client.post('/api/v1/auth/demo', json={'profile':'facilitator'})
            assert client.get('/api/v1/exercises/' + created).status_code == 200
    finally:
        service.stop()


def test_private_settings_expose_only_approved_public_map_key(tmp_path, monkeypatch):
    (tmp_path / 'settings.env').write_text('VITE_KAKAO_MAPS_APPROVED=true\nVITE_KAKAO_JAVASCRIPT_KEY=' + '0' * 32 + '\nDATA_GOV_BUILDING_KEY=SYNTHETIC_PRIVATE_PROVIDER_KEY\nDATABASE_URL=sqlite:///DO_NOT_USE.db\n', encoding='utf-8')
    service = DesktopService(tmp_path, 0)
    try:
        with httpx.Client(base_url=service.start(), trust_env=False) as client:
            result = client.get('/_desktop/map-config').json()
            assert result == {'approved':True, 'public_key':'0' * 32}
            assert 'SYNTHETIC_PRIVATE_PROVIDER_KEY' not in json.dumps(result)
            monkeypatch.setenv('VITE_KAKAO_JAVASCRIPT_KEY', 'f' * 32)
            assert client.get('/_desktop/map-config').json() == result
            assert service.app.state.store.url.endswith('/storage/studio.db')
        assert not Path('DO_NOT_USE.db').exists()
    finally:
        service.stop()
