import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from apps.api.configuration_files import digest
from apps.api.storage import records


def upload(client, operation, data, key=None):
    return client.post('/api/v1/configurations/' + operation,
        files={'file': ('training.json', data, 'application/json')},
        headers={'Idempotency-Key': key or uuid4().hex})


def test_export_import_is_a_new_unapproved_draft_and_replays_are_idempotent(client, app):
    exported = client.get('/api/v1/exercises/exercise-demo/configuration')
    assert exported.status_code == 200 and 'attachment' in exported.headers['content-disposition']
    document = exported.json()
    assert digest(document['configuration']) == document['sha256']
    # An imported document must never activate its supplied approval records.
    document['configuration'].update(published=True, rehearsal_passed=True, readiness={'person': {'score': 100}},
        reviews={'person': {'approved': True}}, organization_approval='SYNTHETIC_DO_NOT_TRUST')
    document['sha256'] = digest(document['configuration'])
    content = json.dumps(document).encode()
    before = len(client.get('/api/v1/exercises').json())
    preview = upload(client, 'preview', content)
    assert preview.status_code == 200 and preview.json()['events'] >= 10
    assert len(client.get('/api/v1/exercises').json()) == before
    key = uuid4().hex
    imported = upload(client, 'import', content, key)
    assert imported.status_code == 201
    assert upload(client, 'import', content, key).json() == imported.json()
    assert len(client.get('/api/v1/exercises').json()) == before + 1
    new = client.get('/api/v1/exercises/' + imported.json()['id']).json()['exercise']
    assert not new['published'] and not new['rehearsal_passed'] and new['readiness'] == new['reviews'] == {}
    assert new['organization_approval'] == '' and new['subject']['source']['rights'] == 'unknown'
    assert new['subject']['asset_bindings'] == [] and new['asset_reviews'] == []
    assert client.get('/api/v1/exercises/exercise-demo').json()['exercise']['id'] == 'exercise-demo'
    document['configuration']['name'] = 'Changed synthetic configuration'
    document['sha256'] = digest(document['configuration'])
    assert upload(client, 'import', json.dumps(document).encode(), key).status_code == 409


@pytest.mark.parametrize('profile', ['board', 'observer', 'person-01', 'evaluator'])
def test_configuration_files_are_never_exposed_to_non_editing_roles(client, profile):
    data = client.get('/api/v1/exercises/exercise-demo/configuration').content
    client.post('/api/v1/auth/demo', json={'profile': profile})
    assert client.get('/api/v1/exercises/exercise-demo/configuration').status_code == 403
    assert upload(client, 'preview', data).status_code == 403
    assert upload(client, 'import', data).status_code == 403


@pytest.mark.parametrize('kind', ['checksum', 'duplicate', 'version', 'unknown', 'runtime-settings', 'oversize'])
def test_invalid_files_never_create_an_exercise(client, kind):
    document = client.get('/api/v1/exercises/exercise-demo/configuration').json()
    if kind == 'checksum':
        document['configuration']['name'] = 'Tampered'
    elif kind == 'version':
        document['schema_version'] = 2
    elif kind == 'unknown':
        document['secret'] = 'SYNTHETIC_NEVER_ECHO'
    elif kind == 'runtime-settings':
        document = {'schema_version': 1, 'settings': {'ASSET_SCAN_APPROVED': True}}
    content = json.dumps(document).encode()
    if kind == 'duplicate':
        content = content.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1')
    if kind == 'oversize':
        content = b' ' * (2 * 1024 * 1024 + 1)
    before = len(client.get('/api/v1/exercises').json())
    response = upload(client, 'import', content)
    assert response.status_code in (413, 422)
    assert 'SYNTHETIC_NEVER_ECHO' not in response.text
    assert len(client.get('/api/v1/exercises').json()) == before


def test_failed_atomic_import_rolls_back_all_created_records(client, app, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    import apps.api.storage as module
    data = client.get('/api/v1/exercises/exercise-demo/configuration').content
    before = len(client.get('/api/v1/exercises').json())
    original = module.Store.log

    def fail(*args, **kwargs):
        raise IntegrityError('synthetic import rollback', {}, None)

    monkeypatch.setattr(module.Store, 'log', fail)
    assert upload(client, 'import', data).status_code == 409
    monkeypatch.setattr(module.Store, 'log', original)
    assert len(client.get('/api/v1/exercises').json()) == before


def test_configuration_import_export_are_organization_scoped(client, app):
    from apps.api.auth import issue_token
    from fastapi import HTTPException
    data = client.get('/api/v1/exercises/exercise-demo/configuration').content
    token = issue_token(app.state.store, {'id': 'synthetic-other-facilitator', 'role': 'facilitator',
        'organization_id': 'synthetic-other', 'name': 'Synthetic other organization', 'person_id': None})
    client.cookies.clear()
    client.cookies.set('studio_session', token)
    assert client.get('/api/v1/exercises/exercise-demo/configuration').status_code == 404
    imported = upload(client, 'import', data)
    assert imported.status_code == 201
    with pytest.raises(HTTPException) as error:
        app.state.store.load('exercise', imported.json()['id'], 'org-synthetic')
    assert error.value.status_code == 404


def test_simultaneous_import_replays_commit_one_configuration(app):
    from concurrent.futures import ThreadPoolExecutor
    store = app.state.store
    key = uuid4().hex

    def create(_):
        id = 'exercise-' + uuid4().hex[:12]
        return store.create_idempotent('exercise', id, 'synthetic-parallel', {'id': id},
            'synthetic-operator', key, {'configuration_sha256': '0' * 64})

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(8)))
    assert len({result['id'] for result in results}) == 1
    assert len(store.list('exercise', 'synthetic-parallel')) == 1
