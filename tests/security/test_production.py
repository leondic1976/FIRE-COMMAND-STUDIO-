from fastapi.testclient import TestClient
from apps.api.auth import password_hash
from apps.api.application import create_app
from apps.api.storage import accounts


def test_production_disables_demo_and_checks_institutional_password(tmp_path):
    app=create_app(f"sqlite:///{(tmp_path/'prod.db').as_posix()}",False)
    user={'id':'synthetic-admin','name':'합성 운영자','role':'admin','organization_id':'org-test','person_id':None}
    with app.state.store.engine.begin() as conn:
        conn.execute(accounts.insert().values(organization_id='org-test',username='synthetic-admin',password_hash=password_hash('only-synthetic-test-password'),identity=user))
    with TestClient(app,base_url='https://testserver') as c:
        assert c.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==404
        assert c.get('/api/v1/auth/profiles').json()['profiles']==[]
        bad={'organization_id':'org-test','username':'synthetic-admin','password':'wrong'}
        assert c.post('/api/v1/auth/login',json=bad).status_code==401
        bad['password']='only-synthetic-test-password'
        assert c.post('/api/v1/auth/login',json=bad).status_code==200
        assert c.get('/api/v1/exercises').json()==[]
        assert c.get('/api/docs').status_code==404
    app.state.store.engine.dispose()
