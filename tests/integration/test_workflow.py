import copy
import json
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from apps.api.application import create_app
from apps.api.storage import events
from sqlalchemy import select
from tests.conftest import control,ex_version,mutate,prepare,release_n,session_version


def test_ac06_07_full_readiness_and_immutable_publication(client):
    assert client.post('/api/v1/exercises/exercise-demo/sessions').status_code==409
    bad=mutate(client,'/exercises/exercise-demo/publish',{'expected_state_version':ex_version(client),'note':'무검증 발행 시도'})
    assert bad.status_code==422
    sid=prepare(client)
    ex=client.get('/api/v1/exercises/exercise-demo').json()
    assert ex['exercise']['publication']['note'].startswith('자동시험')
    assert ex['exercise']['rehearsal_report']['paths_visited']==10
    assert len(ex['exercise']['readiness'])==7
    save=client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex['state_version'],'exercise':ex['exercise']},headers={'Idempotency-Key':uuid4().hex})
    assert save.status_code==409
    s=client.get('/api/v1/sessions/'+sid).json()
    assert s['exercise']['published'] and s['status']=='READY'


def test_readiness_retries_reset_review_and_role_version(client):
    body={'expected_state_version':ex_version(client),'person_id':'person-01','role_id':'incident_commander','acknowledged_version':1,'answers':{'report':0,'mission':1,'handover':0},'explanation':'가상 자동시험 응답입니다.'}
    assert mutate(client,'/exercises/exercise-demo/readiness',body).status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()
    assert data['exercise']['readiness']['person-01:incident_commander']['score']==0
    ex=data['exercise'];ex['roles'][0]['tasks'][0]='추가 기관 임무 초안'
    r=client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':data['state_version'],'exercise':ex},headers={'Idempotency-Key':uuid4().hex})
    assert r.status_code==200
    updated=client.get('/api/v1/exercises/exercise-demo').json()
    assert updated['exercise']['roles'][0]['version']==2
    body['expected_state_version']=updated['state_version']
    assert mutate(client,'/exercises/exercise-demo/readiness',body).status_code==422
    base=client.get('/api/v1/roles/templates').json()
    assert base['readonly'] and base['roles'][0]['version']==1


def test_ac19_atomic_release_idempotency_conflict(app,client,session_id):
    sid=session_id;v=session_version(client,sid);key=uuid4().hex
    payload={'expected_state_version':v,'operation':'release','event_id':'EV-01'}
    one=client.post(f'/api/v1/sessions/{sid}/control',json=payload,headers={'Idempotency-Key':key})
    two=client.post(f'/api/v1/sessions/{sid}/control',json=payload,headers={'Idempotency-Key':key})
    assert one.status_code==two.status_code==200 and one.json()==two.json()
    assert client.post(f'/api/v1/sessions/{sid}/control',json={**payload,'event_id':'EV-02'},headers={'Idempotency-Key':key}).status_code==409
    assert mutate(client,f'/sessions/{sid}/control',payload).status_code==409
    s=client.get(f'/api/v1/sessions/{sid}').json()
    assert s['scene']['B01-F02-Z01']['smoke']==1
    assert len(s['messages'])==1 and s['messages'][0]['event_seq']==s['seq']
    with app.state.store.engine.connect() as conn:
        logs=conn.execute(select(events.c.payload).where(events.c.session_id==sid)).scalars().all()
    assert len(logs)==2 and logs[-1]['kind']=='INJECT_RELEASED'


def test_release_conflict_rolls_back_entire_transaction(client,session_id,app):
    sid=session_id
    # Corrupt only the local test aggregate, to prove a conflicting before-value cannot partially apply.
    v=session_version(client,sid)
    app.state.store.mutate('session',sid,'org-synthetic',v,'test','TEST_CONFLICT',lambda s:s['scene']['B01-F02-Z01'].update(smoke=2))
    before=client.get(f'/api/v1/sessions/{sid}').json()
    assert control(client,sid,'release',event_id='EV-01').status_code==409
    after=client.get(f'/api/v1/sessions/{sid}').json()
    assert after['seq']==before['seq'] and after['messages']==before['messages'] and after['state_version']==before['state_version']


def test_ac24_message_closed_loop_and_decision(client,session_id):
    sid=session_id;release_n(client,sid,1)
    for stage in ['RECEIVED','ACKNOWLEDGED','VERIFIED','REPORTED','DECIDED','REPLIED','CLOSED']:
        r=mutate(client,f'/sessions/{sid}/actions',{'expected_state_version':session_version(client,sid),'event_id':'EV-01','role_id':'situation_officer','person_id':'person-06','stage':stage,'action_type':'verify_information','text':'가상 자동시험: 출처 확인과 보고를 수행했습니다.','visibility':'PUBLIC','truth_status':'CONFIRMED'})
        assert r.status_code==200,r.text
    s=client.get(f'/api/v1/sessions/{sid}').json()
    assert len(s['messages'][0]['stages'])==7
    assert len({a['seq'] for a in s['actions']})==7
    r=mutate(client,f'/sessions/{sid}/decisions',{'expected_state_version':s['state_version'],'summary':'정보 재확인 후 안전통제 우선 수행','role_id':'safety_officer','report_at_seconds':600,'event_id':'EV-01','visibility':'PUBLIC'})
    assert r.status_code==200
    assert client.get(f'/api/v1/sessions/{sid}').json()['decisions'][-1]['role_id']=='safety_officer'


def test_ac27_pause_undo_replay_and_reconnect(client,session_id):
    sid=session_id;release_n(client,sid,2)
    assert control(client,sid,'pause').status_code==200
    first=client.get(f'/api/v1/sessions/{sid}').json()['elapsed_seconds'];time.sleep(.03)
    second=client.get(f'/api/v1/sessions/{sid}').json()['elapsed_seconds'];assert first==second
    assert control(client,sid,'undo',reason='가상 자동시험 되돌림 검증').status_code==200
    s=client.get(f'/api/v1/sessions/{sid}').json()
    assert s['scene']['ROAD01']['closed'] is False
    assert s['messages'][-1]['reverted']
    replay=client.get(f'/api/v1/sessions/{sid}/replay?seq=3').json()
    assert replay['scene']['ROAD01']['closed'] is True
    assert replay['status']=='REPLAY'
    assert control(client,sid,'resume').status_code==200
    with client.websocket_connect(f'/ws/v1/sessions/{sid}') as ws:
        snapshot=ws.receive_json()
        assert snapshot['state_version']==session_version(client,sid)
        assert snapshot['state']['scene']==client.get(f'/api/v1/sessions/{sid}').json()['scene']


def test_ac20_neighbor_exposure_same_event(client,session_id):
    release_n(client,session_id,5)
    s=client.get('/api/v1/sessions/'+session_id).json()
    assert s['scene']['B02']['warning'] is True
    assert s['scene']['PERIMETER01']['radius']==30
    assert s['scene']['ENT01']['closed'] is True
    assert s['messages'][-1]['id']=='EV-05'


def test_ac31_aar_evidence_improvements_and_approval(client,session_id):
    sid=session_id;release_n(client,sid,1)
    r=mutate(client,f'/sessions/{sid}/actions',{'expected_state_version':session_version(client,sid),'event_id':'EV-01','role_id':'situation_officer','person_id':'person-06','stage':'RECEIVED','text':'가상 출처와 미확인 정보 수신 확인'})
    assert r.status_code==200
    s=client.get(f'/api/v1/sessions/{sid}').json()
    o={'expected_state_version':s['state_version'],'person_id':'person-06','role_id':'situation_officer','event_id':'EV-01','action_seq':s['actions'][-1]['seq'],'criterion':'awareness','score':2,'evidence':'가상 메시지 수신 시각과 정보 출처를 확인한 기록','strength':'출처 구분','improvement':'후속 보고 확인','uncertainty':'구두 발언 전체는 미기록'}
    assert mutate(client,f'/sessions/{sid}/observations',o).status_code==200
    s=client.get(f'/api/v1/sessions/{sid}').json();oid=s['observations'][0]['id']
    assert mutate(client,f'/sessions/{sid}/improvements',{'expected_state_version':s['state_version'],'title':'정보 재확인 보고 연습','owner_role_id':'situation_officer','due_date':'2026-12-01','observation_id':oid,'retraining':'다른 가상 상황에서 보고·확인 반복','evidence':''}).status_code==200
    s=client.get(f'/api/v1/sessions/{sid}').json();iid=s['improvements'][0]['id']
    assert mutate(client,f'/sessions/{sid}/improvements/{iid}/complete',{'expected_state_version':s['state_version'],'evidence':'자동시험용 재훈련 수행 근거 기록','note':'가상 관찰 증거 확인'}).status_code==200
    assert control(client,sid,'end',reason='가상 자동시험 종료').status_code==200
    assert mutate(client,f'/sessions/{sid}/aar/approve',{'expected_state_version':session_version(client,sid),'note':'자동시험용 근거·개선 연결 검토'}).status_code==200
    aar=client.get(f'/api/v1/sessions/{sid}/aar').json()
    assert aar['observations'][0]['id']==aar['improvements'][0]['observation_id']
    assert aar['approval'] and aar['ai_provider']=='disabled'
    assert aar['improvements'][0]['status']=='COMPLETED'
    assert aar['improvements'][0]['evidence']=='자동시험용 재훈련 수행 근거 기록'
    md=client.get(f'/api/v1/sessions/{sid}/aar?format=markdown')
    assert md.status_code==200 and '재훈련' in md.text and '정보 재확인 보고 연습' in md.text and 'KST' in md.text


def test_ac32_end_to_end_without_ai(client,session_id):
    release_n(client,session_id,10)
    assert control(client,session_id,'end',reason='AI OFF 전체 흐름').status_code==200
    aar=client.get(f'/api/v1/sessions/{session_id}/aar').json()
    assert len([e for e in aar['timeline'] if e['kind']=='INJECT_RELEASED'])==10
    assert aar['training_only'] and aar['ai_provider']=='disabled'


def test_ac35_process_restart_preserves_snapshot(client,session_id,app):
    release_n(client,session_id,4)
    before=client.get('/api/v1/sessions/'+session_id).json()
    restarted=create_app(app.state.store.url,True)
    with TestClient(restarted) as c:
        c.post('/api/v1/auth/demo',json={'profile':'facilitator'})
        after=c.get('/api/v1/sessions/'+session_id).json()
    assert before['seq']+1==after['seq'] and before['scene']==after['scene']
    assert after['status']=='PAUSED' and after['log'][-1]['kind']=='SESSION_RECOVERED'
    assert before['exercise']==after['exercise'] and before['log']==after['log'][:-1]
    restarted.state.store.engine.dispose()


def test_cloning_resets_people_dates_readiness_approval(client):
    prepare(client)
    cloned=client.post('/api/v1/exercises/exercise-demo/clone').json()
    assert not cloned['published'] and not cloned['rehearsal_passed']
    assert cloned['assignments']==[] and cloned['persons']==[]
    assert cloned['readiness']=={} and cloned['reviews']=={}
    assert cloned['subject']['source']['rights']=='unknown'
