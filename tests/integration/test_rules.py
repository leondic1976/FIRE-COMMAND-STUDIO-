import time
from uuid import uuid4
from tests.conftest import control,ex_version,mutate,prepare,session_version


def test_ac25_action_condition_branch_requires_recorded_action(client):
    current=client.get('/api/v1/exercises/exercise-demo').json()
    ex=current['exercise'];ex['events'][1]['trigger']['kind']='ON_ACTION';ex['events'][1]['trigger']['action']='verify_site'
    result=client.put('/api/v1/exercises/exercise-demo',json={'exercise':ex,'expected_state_version':current['state_version']},headers={'Idempotency-Key':uuid4().hex})
    assert result.status_code==200,result.text
    sid=prepare(client)
    assert control(client,sid,'start').status_code==200
    assert control(client,sid,'release',event_id='EV-01').status_code==200
    assert control(client,sid,'release',event_id='EV-02').status_code==409
    assert mutate(client,f'/sessions/{sid}/actions',{'expected_state_version':session_version(client,sid),'event_id':'EV-01','role_id':'situation_officer','person_id':'person-06','stage':'RECEIVED','action_type':'verify_site','text':'가상 출처 재확인 조치'}).status_code==200
    assert control(client,sid,'release',event_id='EV-02').status_code==200
    assert client.get('/api/v1/sessions/'+sid).json()['scene']['ROAD01']['closed'] is True


def test_prepublished_timed_event_auto_release_is_idempotent(client):
    current=client.get('/api/v1/exercises/exercise-demo').json();ex=current['exercise']
    ex['events'][0]['trigger'].update(kind='AT_TIME',at_seconds=0,auto_release=True)
    assert client.put('/api/v1/exercises/exercise-demo',json={'exercise':ex,'expected_state_version':current['state_version']},headers={'Idempotency-Key':uuid4().hex}).status_code==200
    sid=prepare(client)
    assert control(client,sid,'start').status_code==200
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        state=client.get('/api/v1/sessions/'+sid).json()
        if state['messages']:break
        time.sleep(.05)
    assert len(state['messages'])==1 and state['messages'][0]['id']=='EV-01'
    time.sleep(.35)
    assert len(client.get('/api/v1/sessions/'+sid).json()['messages'])==1
