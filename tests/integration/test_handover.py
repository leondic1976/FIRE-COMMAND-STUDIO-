from tests.conftest import control,mutate,release_n,session_version


def test_ac04_05_ordered_substitute_and_original_attribution(client,session_id):
    sid=session_id;release_n(client,sid,1)
    a={'expected_state_version':session_version(client,sid),'event_id':'EV-01','role_id':'safety_officer','person_id':'person-05','stage':'RECEIVED','text':'교체 전 안전요원의 현장 정보 수신 기록','visibility':'PUBLIC'}
    assert mutate(client,f'/sessions/{sid}/actions',a).status_code==200
    def handover(operation,**kwargs):
        return mutate(client,f'/sessions/{sid}/handovers',{'expected_state_version':session_version(client,sid),'operation':operation,'note':'가상 순환근무·부재 대체 시험',**kwargs})
    assert handover('propose',role_id='safety_officer',to_person_id='person-10').status_code==409
    assert handover('propose',role_id='safety_officer',to_person_id='person-09').status_code==200
    s=client.get('/api/v1/sessions/'+sid).json();h=s['handovers'][0]
    assert h['status']=='PROPOSED'
    assert handover('activate',handover_id=h['id'],note='앞 단계 없이 활성화').status_code==409
    for op,extra in [('accept',{'note':'대체 업무를 수락합니다.'}),('card',{'note':'현장 안전진단과 위험 보고 경로를 설명합니다.','answers':{'report':1,'mission':0,'handover':2},'acknowledged_version':1}),('review',{'note':'대체자의 핵심 임무·권한·보고선 구두 설명을 확인했습니다.'}),('handover',{'note':'인계·인수 내용을 상호 확인했습니다.','summary':'현재 가상 상황과 공개 정보를 공유했습니다.','unconfirmed':'소방용수 수압 미확인','pending_tasks':'위험구역 재확인 보고'}),('activate',{'note':'모든 인계 항목 확인 후 활성화'})]:
        r=handover(op,handover_id=h['id'],**extra)
        assert r.status_code==200,(op,r.text)
    s=client.get('/api/v1/sessions/'+sid).json()
    assert s['handovers'][0]['status']=='ACTIVE'
    old=[a for a in s['roster'] if a['role_id']=='safety_officer' and a['person_id']=='person-05'][0]
    assert old['status']=='ENDED'
    assert s['exercise']['assignments'][4]['person_id']=='person-05'
    assert s['exercise']['assignments'][4]['status']=='ACTIVE'
    assert s['actions'][0]['person_id']=='person-05'
    assert any(a['role_id']=='safety_officer' and a['person_id']=='person-09' and a['status']=='ACTIVE' for a in s['roster'])
    a.update(expected_state_version=s['state_version'],stage='ACKNOWLEDGED')
    assert mutate(client,f'/sessions/{sid}/actions',a).status_code==403


def test_ac08_transition_requires_real_approval_reference(client,session_id):
    sid=session_id
    assert control(client,sid,'transition',reason='인계 확인').status_code==409
    # Deliberately supplied synthetic test approval is not represented as an institution approval.
    store=client.app.state.store
    v=session_version(client,sid)
    store.mutate('session',sid,'org-synthetic',v,'test','TEST_APPROVAL',lambda s:s['exercise'].update(organization_approval='자동시험 전용 가상 승인 참조'))
    assert control(client,sid,'transition',reason='각 요원 부서 전환·인계·미완료 사항 공유 확인').status_code==200
    s=client.get('/api/v1/sessions/'+sid).json()
    assert s['stage']=='CONTROL_GROUP'
    event=s['log'][-1]['payload']
    assert event['departments']['situation_officer']=='대응계획부'
    assert event['departments']['resource_officer']=='자원지원부'
