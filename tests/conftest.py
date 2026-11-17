from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from apps.api.application import create_app


@pytest.fixture
def app(tmp_path):
    instance = create_app(f"sqlite:///{(tmp_path/'studio.db').as_posix()}", True)
    yield instance
    instance.state.store.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code == 200
        yield c


def mutate(client, path, body):
    return client.post('/api/v1'+path, json=body, headers={'Idempotency-Key': uuid4().hex})


def ex_version(client, id='exercise-demo'):
    return client.get('/api/v1/exercises/'+id).json()['state_version']


def session_version(client, id):
    return client.get('/api/v1/sessions/'+id).json()['state_version']


def prepare(client, id='exercise-demo'):
    data = client.get('/api/v1/exercises/'+id).json()['exercise']
    for a in data['assignments']:
        role = next(r for r in data['roles'] if r['id'] == a['role_id'])
        result = mutate(client, f'/exercises/{id}/readiness', {'expected_state_version': ex_version(client,id), 'person_id': a['person_id'], 'role_id': a['role_id'], 'acknowledged_version': role['version'], 'answers': {'report':1,'mission':0,'handover':2}, 'explanation':'확인한 정보와 미확인 정보를 분리해 승인된 보고경로로 임무 결과를 보고합니다.'})
        assert result.status_code == 200, result.text
        result = mutate(client, f'/exercises/{id}/readiness/review', {'expected_state_version': ex_version(client,id), 'person_id': a['person_id'], 'role_id': a['role_id'], 'approved': True, 'note':'자동시험용 가상 응답: 업무·보고선·권한 설명 확인'})
        assert result.status_code == 200, result.text
    result = mutate(client, f'/exercises/{id}/rehearse', {'expected_state_version': ex_version(client,id)})
    assert result.status_code == 200, result.text
    result = mutate(client, f'/exercises/{id}/publish', {'expected_state_version': ex_version(client,id),'note':'자동시험용 합성 시나리오 승인. 기관 정규 승인 아님.'})
    assert result.status_code == 200, result.text
    result = client.post(f'/api/v1/exercises/{id}/sessions')
    assert result.status_code == 201, result.text
    return result.json()['id']


@pytest.fixture
def session_id(client):
    sid=prepare(client)
    r=mutate(client,f'/sessions/{sid}/control',{'expected_state_version':session_version(client,sid),'operation':'start'})
    assert r.status_code==200,r.text
    return sid


def control(client,sid,op,**values):
    return mutate(client,f'/sessions/{sid}/control',{'expected_state_version':session_version(client,sid),'operation':op,**values})


def release_n(client,sid,n):
    for i in range(1,n+1):
        r=control(client,sid,'release',event_id=f'EV-{i:02}')
        assert r.status_code==200,r.text
