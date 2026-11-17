from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api import engine
from apps.api.seeds import demo_exercise


def test_clock_requires_identity_and_never_exposes_session_information(app):
    with TestClient(app) as client:
        assert client.get('/api/v1/clock').status_code == 401
        assert client.get('/api/v1/health').json()['schema_version'] == 2
        for profile in ('facilitator', 'board', 'observer', 'person-01'):
            assert client.post('/api/v1/auth/demo', json={'profile': profile}).status_code == 200
            before = datetime.now(timezone.utc)
            response = client.get('/api/v1/clock')
            after = datetime.now(timezone.utc)
            assert response.status_code == 200
            data = response.json()
            assert set(data) == {'server_time', 'training_only'}
            assert data['training_only'] is True
            assert before <= datetime.fromisoformat(data['server_time']) <= after
            assert response.headers['cache-control'] == 'no-store'


def test_projection_clock_and_elapsed_are_sampled_at_the_same_instant():
    session = engine.new_session('synthetic-clock', demo_exercise())
    session.update(status='RUNNING', elapsed_seconds=12.5,
                   clock_started_at='2026-11-17T00:00:00+00:00')
    projection = engine.project(session, {'role': 'board', 'organization_id': 'org-synthetic'})
    sampled = datetime.fromisoformat(projection['clock_sampled_at'])
    expected = 12.5 + (sampled - datetime.fromisoformat(session['clock_started_at'])).total_seconds()
    assert abs(projection['elapsed_seconds'] - expected) <= .0051
    assert 'exercise' not in projection and 'candidates' not in projection
