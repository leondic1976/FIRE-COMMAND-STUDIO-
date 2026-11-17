from fastapi.testclient import TestClient
from uuid import uuid4
from apps.api.application import create_app
from scripts.backup_restore import backup,restore
from tests.conftest import prepare,control


def test_synthetic_interior_survives_versioned_publication_atomic_event_replay_and_backup(client,app,tmp_path):
    response=client.get('/api/v1/exercises/exercise-demo').json();exercise=response['exercise']
    exercise['subject']['buildings'][0].update(basement_floors=1,roof_style='GABLE',wall_finish='METAL')
    room={'id':'B01-B01-ROOM-1','name':'가상 지하 방화구획','kind':'COMPARTMENT','building_id':'B01','floor':-1,'x':3,'z':4,'width':6,'depth':8,'height':2.5,'rotation':15,'state':{'closed':False}}
    exercise['subject']['features'].append(room)
    exercise['events'][0]['patches'].append({'feature_id':room['id'],'field':'closed','before':False,'after':True,'visual_kind':'ILLUSTRATIVE'})
    saved=client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':response['state_version'],'exercise':exercise},headers={'Idempotency-Key':uuid4().hex})
    assert saved.status_code==200,saved.text
    sid=prepare(client);assert control(client,sid,'start').status_code==200
    assert control(client,sid,'release',event_id='EV-01').status_code==200
    state=client.get('/api/v1/board/sessions/'+sid).json()
    assert state['scene'][room['id']]['closed'] is True
    assert state['subject']['buildings'][0]['basement_floors']==1
    assert next(f for f in state['subject']['features'] if f['id']==room['id'])['floor']==-1
    assert client.get(f'/api/v1/sessions/{sid}/replay?seq=0').json()['scene'][room['id']]['closed'] is False
    assert control(client,sid,'pause').status_code==200
    assert control(client,sid,'undo',reason='합성 지하 구획 되돌림').status_code==200
    assert client.get('/api/v1/board/sessions/'+sid).json()['scene'][room['id']]['closed'] is False
    source=app.state.store.engine.url.database;backup(source,tmp_path/'copy.db');restore(tmp_path/'copy.db',tmp_path/'restored.db')
    restored=create_app('sqlite:///'+(tmp_path/'restored.db').as_posix(),True)
    try:
        with TestClient(restored) as other:
            assert other.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
            data=other.get('/api/v1/sessions/'+sid).json()
            assert data['subject']['buildings'][0]['roof_style']=='GABLE'
            assert data['scene'][room['id']]['closed'] is False
            assert next(f for f in data['subject']['features'] if f['id']==room['id'])['rotation']==15
    finally:restored.state.store.engine.dispose()
