from tests.conftest import mutate


def test_ac37_independent_solo_without_ai_or_facilitator(client):
    client.post('/api/v1/auth/demo',json={'profile':'person-05'})
    created=client.post('/api/v1/practice',json={'role_id':'safety_officer','difficulty':'BEGINNER','template':'factory'})
    assert created.status_code==201,created.text
    sid=created.json()['id']
    state=client.get('/api/v1/sessions/'+sid).json()
    assert state['mode']=='SOLO' and state['practice']['self_practice']
    assert len(state['my_role_ids'])==1
    def control(op,**kwargs):
        version=client.get('/api/v1/sessions/'+sid).json()['state_version']
        return mutate(client,f'/practice/{sid}/control',{'expected_state_version':version,'operation':op,**kwargs})
    assert control('start').status_code==200
    assert control('release',event_id='EV-01').status_code==200
    state=client.get('/api/v1/sessions/'+sid).json()
    assert '모의 동료' in state['messages'][0]['sender']
    assert '초급 도움말' in state['messages'][0]['text']
    for stage in ('RECEIVED','ACKNOWLEDGED','VERIFIED','REPORTED'):
        version=client.get('/api/v1/sessions/'+sid).json()['state_version']
        response=mutate(client,f'/sessions/{sid}/actions',{'expected_state_version':version,'event_id':'EV-01','role_id':'safety_officer','person_id':'person-05','stage':stage,'text':'출처와 불확실성을 구분해 승인된 보고선에 전달합니다.'})
        assert response.status_code==200,response.text
    state=client.get('/api/v1/sessions/'+sid).json()
    assert state['practice_feedback'][0]['action_seq']==state['actions'][-1]['seq']
    assert control('pause').status_code==200
    assert control('resume').status_code==200
    assert control('end',reason='개인 합성 연습 종료').status_code==200
    client.post('/api/v1/auth/demo',json={'profile':'person-04'})
    assert client.get('/api/v1/sessions/'+sid).status_code==403
    assert sid not in [s['id'] for s in client.get('/api/v1/sessions').json()]
