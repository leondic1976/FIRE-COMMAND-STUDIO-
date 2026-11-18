import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from screen.server import create_screen_app
from web.server import WebSettings
from apps.api.auth import issue_token


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    now = [1000.]
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'index.html').write_text('synthetic screen UI')
    app = create_screen_app(tmp_path / 'private', WebSettings(port=8090, public_url='http://127.0.0.1:8090'), public, lambda: now[0])
    with TestClient(app, base_url='http://127.0.0.1:8090') as client:
        assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code == 200
        yield app, client, now
    app.state.store.engine.dispose()


def create(client):
    scenario = client.get('/api/screen/scenarios').json()[0]['id']
    r = client.post('/api/screen/runs', json={'scenario_id': scenario}, headers={'Idempotency-Key': uuid4().hex})
    assert r.status_code == 201, r.text
    return r.json()['id']


def control(client, id, action, key=None, **extra):
    version = client.get('/api/screen/runs/' + id).json()['state_version']
    return client.post(f'/api/screen/runs/{id}/commands', json={'expected_state_version': version, 'action': action, **extra}, headers={'Idempotency-Key': key or uuid4().hex})


def test_real_server_timing_atomic_projection_idempotency_and_tenant_boundary(system):
    app, client, now = system
    id = create(client)
    key = uuid4().hex
    version = client.get('/api/screen/runs/' + id).json()['state_version']
    command = {'expected_state_version': version, 'action': 'start'}
    first = client.post(f'/api/screen/runs/{id}/commands', json=command, headers={'Idempotency-Key': key})
    assert client.post(f'/api/screen/runs/{id}/commands', json=command, headers={'Idempotency-Key': key}).json() == first.json()
    now[0] += 59
    app.state.screen_tick()
    assert not client.get('/api/screen/board/' + id).json()['messages']
    now[0] += 1
    app.state.screen_tick()
    state = client.get('/api/screen/board/' + id).json()
    assert state['messages'][0]['elapsed'] == 60 and state['scene']['entities'][0]['smoke'] == 3
    assert control(client, id, 'note', note='PRIVATE_SYNTHETIC_SCREEN_NOTE').is_success
    public = client.get('/api/screen/board/' + id).text
    assert all(secret not in public for secret in ['private_prompt', 'PRIVATE_SYNTHETIC_SCREEN_NOTE', 'victim-a', 'next_event'])
    other = issue_token(app.state.store, {'id': 'other', 'role': 'facilitator', 'organization_id': 'other-org'})
    client.cookies.set('studio_session', other)
    assert client.get('/api/screen/board/' + id).status_code == 404


def test_board_cannot_edit_and_websocket_always_uses_public_projection(system):
    app, client, now = system
    id = create(client)
    assert control(client, id, 'note', note='PRIVATE_WS_NOTE').is_success
    with client.websocket_connect('ws://127.0.0.1:8090/ws/screen/board/' + id, headers={'Origin': 'http://127.0.0.1:8090'}) as ws:
        data = ws.receive_json()
        assert 'notes' not in data and 'scenario' not in data and 'PRIVATE_WS_NOTE' not in json.dumps(data)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('ws://127.0.0.1:8090/ws/screen/' + id, headers={'Origin': 'https://other.invalid'}):
            pass
    client.post('/api/v1/auth/demo', json={'profile': 'board'})
    assert client.get('/api/screen/scenarios').status_code == 403
    assert client.get('/api/screen/catalog').status_code == 403
    assert client.post('/api/screen/runs', json={'scenario_id': 'warehouse-first'}).status_code == 403
    assert client.post(f'/api/screen/runs/{id}/commands', json={'expected_state_version': 1, 'action': 'start'}).status_code == 403


def test_json_import_export_and_real_data_gate(system):
    app, client, now = system
    scenario_id = client.get('/api/screen/scenarios').json()[0]['id']
    value = client.get(f'/api/screen/scenarios/{scenario_id}').json()
    value['scenario']['site']['target_mode'] = 'REAL'
    result = client.put(f'/api/screen/scenarios/{scenario_id}', json={'expected_state_version': value['state_version'], 'scenario': value['scenario']}, headers={'Idempotency-Key': uuid4().hex})
    assert result.is_success
    assert client.post('/api/screen/runs', json={'scenario_id': scenario_id}, headers={'Idempotency-Key': uuid4().hex}).status_code == 422
    exported = client.get(f'/api/screen/scenarios/{scenario_id}/download').json()
    assert exported['site']['target_mode'] == 'APPROXIMATE'
    key = uuid4().hex
    for _ in range(2):
        r = client.post('/api/screen/scenarios/import', files={'file': ('scenario.json', json.dumps(exported).encode(), 'application/json')}, headers={'Idempotency-Key': key})
        assert r.status_code == 201
    assert len(client.get('/api/screen/scenarios').json()) == 2
    for bad in [b'{"schema_version":1,"schema_version":1}', b'{"schema_version":NaN}', b'[]', b'x' * (2 * 1024 * 1024 + 1)]:
        assert client.post('/api/screen/scenarios/import', files={'file': ('bad.json', bad)}, headers={'Idempotency-Key': uuid4().hex}).status_code == 422


def test_unapproved_assets_are_quarantined_and_cannot_be_published(system):
    app, client, now = system
    key = uuid4().hex
    r = client.post('/api/screen/assets', files={'file': ('synthetic.png', b'not-real-photo')}, data={'source': '{"name":"Synthetic rights test"}'}, headers={'Idempotency-Key': key})
    assert r.status_code == 201 and r.json()['status'] == 'QUARANTINED'
    id = r.json()['id']
    retry = client.post('/api/screen/assets', files={'file': ('synthetic.png', b'not-real-photo')}, data={'source': '{"name":"Synthetic rights test"}'}, headers={'Idempotency-Key': key})
    assert retry.json()['id'] == id and len(client.get('/api/screen/assets').json()) == 1
    assert client.get('/api/screen/assets/' + id + '/content').status_code == 409
    assert client.post('/api/screen/assets/' + id + '/review', json={'expected_state_version': 1, 'rights_confirmed': True, 'reference': 'Synthetic only'}, headers={'Idempotency-Key': uuid4().hex}).status_code == 409


def test_synthetic_clean_assets_need_explicit_review_and_run_binding(system):
    from tests.asset_fixtures import FixtureScanner, glb, photo
    app, client, _ = system
    app.state.asset_scanner = FixtureScanner()
    ids = []
    for name, content in [('synthetic.glb', glb()), ('synthetic.png', photo())]:
        upload = client.post('/api/screen/assets', files={'file': (name, content)}, data={'source': '{"name":"Synthetic fixture, not a real facility","rights":"Authored test data"}'}, headers={'Idempotency-Key': uuid4().hex})
        assert upload.status_code == 201 and upload.json()['status'] == 'VALIDATED'
        id = upload.json()['id']
        assert client.get('/api/screen/assets/' + id + '/content').status_code == 409
        result = client.post('/api/screen/assets/' + id + '/review', json={'expected_state_version': 1, 'rights_confirmed': True, 'reference': 'Synthetic test review; not institutional approval'}, headers={'Idempotency-Key': uuid4().hex})
        assert result.status_code == 200 and client.get('/api/screen/assets/' + id + '/content').status_code == 200
        ids.append(id)
    scenario = client.get('/api/screen/scenarios').json()[0]['id']
    value = client.get('/api/screen/scenarios/' + scenario).json()
    value['scenario']['buildings'][0].update(model_asset_id=ids[0], facade_assets={'A': ids[1]})
    assert client.put('/api/screen/scenarios/' + scenario, json={'expected_state_version': value['state_version'], 'scenario': value['scenario']}, headers={'Idempotency-Key': uuid4().hex}).is_success
    id = create(client)
    client.post('/api/v1/auth/demo', json={'profile': 'board'})
    assert client.get('/api/screen/assets/' + ids[0] + '/content').status_code == 403
    assert client.get(f'/api/screen/board/{id}/assets/' + ids[0]).status_code == 200
    assert client.get(f'/api/screen/board/{id}/assets/unknown').status_code == 404


def test_asset_scene_budget_counts_each_instance_and_blocks_preview(system):
    app, client, _ = system
    scenario_id = client.get('/api/screen/scenarios').json()[0]['id']
    value = client.get('/api/screen/scenarios/' + scenario_id).json()['scenario']
    app.state.store.create('screen_asset', 'synthetic-budget-fixture', 'org-synthetic', {'id': 'synthetic-budget-fixture',
        'status': 'APPROVED', 'kind': 'GLB', 'bytes': 1000, 'manifest': {'triangles': 200000, 'texture_pixels': 0}})
    for building in value['buildings']:
        building['model_asset_id'] = 'synthetic-budget-fixture'
    assert client.post('/api/screen/scenarios/validate', json=value).status_code == 422
