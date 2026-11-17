from uuid import uuid4
from tests.conftest import control,session_version


def test_defer_skip_keep_scene_atomic_history_private_and_idempotent(client,session_id):
    sid=session_id;path=f'/api/v1/sessions/{sid}/control'
    before=client.get(f'/api/v1/sessions/{sid}').json()
    assert control(client,sid,'defer',event_id='EV-01',reason='').status_code==422
    version=session_version(client,sid);key=uuid4().hex
    body={'expected_state_version':version,'operation':'defer','event_id':'EV-01','delay_seconds':60,'reason':'PRIVATE_DEFER_NOTE 합성 토론시간 확보'}
    first=client.post(path,json=body,headers={'Idempotency-Key':key});assert first.status_code==200
    assert client.post(path,json=body,headers={'Idempotency-Key':key}).json()==first.json()
    after=client.get(f'/api/v1/sessions/{sid}').json()
    assert after['scene']==before['scene'] and not after['messages']
    assert after['candidates'][0]['deferred_until']>=60
    assert len([entry for entry in after['log'] if entry['kind']=='EVENT_DEFER'])==1
    assert control(client,sid,'release',event_id='EV-01').status_code==409
    assert control(client,sid,'skip',event_id='EV-01',reason='PRIVATE_SKIP_NOTE 합성 관찰 대체').status_code==200
    after=client.get(f'/api/v1/sessions/{sid}').json()
    assert after['scene']==before['scene'] and not after['messages']
    assert after['candidates'][0]['id']=='EV-02'
    assert control(client,sid,'skip',event_id='EV-01',reason='반복 건너뛰기 거절').status_code==409
    public=client.get(f'/api/v1/board/sessions/{sid}').json()
    assert 'PRIVATE_DEFER_NOTE' not in str(public) and 'PRIVATE_SKIP_NOTE' not in str(public)
    assert 'candidates' not in public and 'log' not in public
    assert control(client,sid,'release',event_id='EV-02').status_code==200
    state=client.get(f'/api/v1/sessions/{sid}').json()
    assert len(state['messages'])==1 and state['messages'][0]['id']=='EV-02'
    assert state['scene']['ROAD01']['closed'] is True
