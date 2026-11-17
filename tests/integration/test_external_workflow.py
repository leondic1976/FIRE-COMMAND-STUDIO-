import copy
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.application import DEMO_ORG,create_app
from apps.api.external_data import ExternalSettings
from apps.api.auth import issue_token
from tests.conftest import ex_version, mutate, prepare
from tests.unit.test_external_data import BUILDING,KEY,PATH,envelope


@pytest.fixture
def external_client(tmp_path):
    calls=[]
    payload={'value':envelope([BUILDING])}
    def reply(request):
        calls.append(request)
        return httpx.Response(200,json=payload['value'])
    settings=ExternalSettings(approved=True,approval_reference='합성 응답 통합시험 설정. 기관 승인 아님.',
        building_key=KEY,weather_key=KEY,hydrant_key=KEY,hydrant_path=PATH,hydrant_catalog_url='https://www.data.go.kr/data/15000000/openapi.do')
    app=create_app('sqlite:///'+(tmp_path/'external.db').as_posix(),True,external_settings=settings,external_transport=httpx.MockTransport(reply))
    with TestClient(app) as client:
        assert client.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
        yield client,payload,calls,app
    app.state.store.engine.dispose()


def preview(client,provider='building_registry',key=None,**query):
    data={'building_registry':{'sigunguCd':'11680','bjdongCd':'10300','bun':'0012'},
          'weather':{'base_date':'20261117','base_time':'0600','nx':60,'ny':127},'hydrant':{}}[provider]|query
    return client.post('/api/v1/exercises/exercise-demo/external-data/preview',json={
        'expected_state_version':ex_version(client),'request':{'provider':provider,'query':data}},
        headers={'Idempotency-Key':key or uuid4().hex})


def use_real_mode(client):
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    data['subject']['target_mode']='REAL'
    assert client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':data},
                      headers={'Idempotency-Key':uuid4().hex}).status_code==200


def apply(client,intake,**extra):
    return mutate(client,f'/exercises/exercise-demo/external-data/{intake}/apply',{
        'expected_state_version':ex_version(client),'selected_ids':[BUILDING['mgmBldrgstPk']],
        'building_id':'B01','fields':['name','use','floors'],'approved_for_training':True,
        'note':'합성 시험용 자료 검토. 실제 이용권·기관 승인 아님.',**extra})


def test_fetch_is_immutable_does_not_apply_and_retries_are_idempotent(external_client):
    client,payload,calls,app=external_client
    before=client.get('/api/v1/exercises/exercise-demo').json()
    key=uuid4().hex
    first=preview(client,key=key)
    assert first.status_code==200,first.text
    assert first.json()['batch']['source']['rights']=='unknown'
    assert client.get('/api/v1/exercises/exercise-demo').json()==before
    assert preview(client,key=key).json()==first.json() and len(calls)==1
    assert preview(client,key=key,bun='0013').status_code==409
    assert KEY not in first.text


def test_review_apply_geometry_provenance_and_no_verified_interior(external_client):
    client,payload,calls,app=external_client
    intake=preview(client).json()['id']
    assert apply(client,intake).status_code==422  # Explicit real/virtual choice first.
    use_real_mode(client)
    before=ex_version(client)
    assert apply(client,intake,approved_for_training=False).status_code==422
    assert ex_version(client)==before
    response=apply(client,intake)
    assert response.status_code==200,response.text
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    subject=data['subject']
    assert subject['buildings'][0]['floors']==4 and subject['buildings'][0]['name']==BUILDING['bldNm']
    assert any(feature['id']=='B01-F04-Z01' for feature in subject['features'])
    assert subject['model_accuracy']=='APPROXIMATE' and not subject['interior_verified']
    assert subject['source']['reviewer'] and subject['external_layers'][0]['raw_sha256']
    assert data['external_reviews'][0]['note'].startswith('합성 시험용') and not data['rehearsal_passed']


def test_lower_floors_missing_rows_and_bad_mapping_are_atomic(external_client):
    client,payload,calls,app=external_client
    payload['value']=envelope([{**BUILDING,'grndFlrCnt':2}])
    intake=preview(client).json()['id']
    use_real_mode(client)
    before=client.get('/api/v1/exercises/exercise-demo').json()
    for changes in [{'selected_ids':['not-present']},{'building_id':'B99'},{}]:
        assert apply(client,intake,**changes).status_code==422
        assert client.get('/api/v1/exercises/exercise-demo').json()==before


def test_direct_edit_cannot_forge_external_approval_or_source(external_client):
    client,payload,calls,app=external_client
    intake=preview(client).json()['id']
    use_real_mode(client)
    assert apply(client,intake).status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    data['external_reviews'][0]['actor_id']='fake'
    assert client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':data},
                      headers={'Idempotency-Key':uuid4().hex}).status_code==422


def test_replacement_is_reviewed_and_old_snapshot_remains(external_client):
    client,payload,calls,app=external_client
    first=preview(client).json()['id']
    use_real_mode(client)
    assert apply(client,first).status_code==200
    payload['value']=envelope([{**BUILDING,'grndFlrCnt':5}])
    second=preview(client).json()['id']
    assert apply(client,second).status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    assert len(data['subject']['external_layers'])==1
    assert data['external_reviews'][-1]['supersedes_import_id']==first
    assert client.get(f'/api/v1/exercises/exercise-demo/external-data/{first}').json()['batch']['records'][0]['fields']['floors_above']==4
    clone=client.post('/api/v1/exercises/exercise-demo/clone').json()
    assert not clone['subject']['external_layers'] and not clone['external_reviews']


def test_hydrant_coordinates_and_unknown_water_and_weather_reference(external_client):
    client,payload,calls,app=external_client
    use_real_mode(client)
    payload['value']={'data':[{'시설번호':'SYNTHETIC-H01','위도':37.5001,'경도':127.0002,'출수압력':'합성 수압'}],'totalCount':1}
    intake=preview(client,'hydrant').json()['id']
    assert apply(client,intake,selected_ids=['SYNTHETIC-H01']).status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    hydrant=next(feature for feature in data['subject']['features'] if feature['id'].startswith('HYD-'))
    assert 10<hydrant['x']<30 and -20<hydrant['z']<-5 and hydrant['state']['water']=='UNCONFIRMED'
    payload['value']=envelope([{'category':'WSD','baseDate':'20261117','baseTime':'0600','nx':60,'ny':127,'obsrValue':'2.5'}])
    intake=preview(client,'weather').json()['id']
    assert apply(client,intake,selected_ids=['WSD']).status_code==200
    result=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    assert len(result['subject']['external_layers'])==2
    assert result['subject']['external_layers'][-1]['records'][0]['fields']['value']==2.5
    assert not any('wind' in feature['state'] for feature in result['subject']['features'])


def test_internal_target_and_published_target_never_trigger_fetch(external_client):
    client,payload,calls,app=external_client
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    data['subject']['source']['classification']='INTERNAL'
    assert client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':data},headers={'Idempotency-Key':uuid4().hex}).status_code==200
    assert preview(client).status_code==403 and not calls
    data['subject']['source']['classification']='SYNTHETIC'
    assert client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':data},headers={'Idempotency-Key':uuid4().hex}).status_code==200
    prepare(client)
    assert preview(client).status_code==409 and not calls


def test_tenant_role_and_cross_exercise_intake_access(external_client):
    client,payload,calls,app=external_client
    intake=preview(client).json()['id']
    other=client.post('/api/v1/exercises',json={'template':'factory','name':'별도 가상 훈련'}).json()['id']
    assert client.get(f'/api/v1/exercises/{other}/external-data/{intake}').status_code==404
    client.post('/api/v1/auth/demo',json={'profile':'board'})
    assert client.get(f'/api/v1/exercises/exercise-demo/external-data/{intake}').status_code==403
    token=issue_token(app.state.store,{'id':'other-admin','role':'admin','name':'가상 다른 기관','organization_id':'other','person_id':None})
    client.cookies.set('studio_session',token)
    assert client.get(f'/api/v1/exercises/exercise-demo/external-data/{intake}').status_code==404


def test_failure_response_is_controlled_without_credentials(external_client):
    client,payload,calls,app=external_client
    payload['value']={'response':{'header':{'resultCode':'30','resultMsg':KEY}}}
    before=ex_version(client)
    response=preview(client)
    assert response.status_code==502 and KEY not in response.text and 'fallback' in response.text
    assert ex_version(client)==before


def test_reference_objects_cannot_be_forged_and_replacement_removes_stale_objects(external_client):
    client,payload,calls,app=external_client
    use_real_mode(client)
    payload['value']={'data':[{'시설번호':'old','위도':37.5001,'경도':127.0002}],'totalCount':1}
    intake=preview(client,'hydrant').json()['id']
    assert apply(client,intake,selected_ids=['old']).status_code==200
    original=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    reference=next(f for f in original['subject']['features'] if f['data_origin']=='REFERENCE')
    forged=copy.deepcopy(original)
    forged['subject']['features'][0]['data_origin']='REFERENCE'
    forged['subject']['features'][0]['source_layer_id']=reference['source_layer_id']
    response=client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':forged},headers={'Idempotency-Key':uuid4().hex})
    assert response.status_code==422
    payload['value']={'data':[{'시설번호':'new','위도':37.5002,'경도':127.0003}],'totalCount':1}
    intake=preview(client,'hydrant').json()['id']
    assert apply(client,intake,selected_ids=['new']).status_code==200
    updated=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    current=[f for f in updated['subject']['features'] if f['data_origin']=='REFERENCE']
    assert len(current)==1 and current[0]['id']!=reference['id']
    clone=client.post('/api/v1/exercises/exercise-demo/clone').json()
    assert not any(f['data_origin']=='REFERENCE' for f in clone['subject']['features'])


def test_review_notes_are_private_and_aar_uses_frozen_source_snapshot(external_client):
    client,payload,calls,app=external_client
    use_real_mode(client)
    intake=preview(client).json()['id']
    private='非公開검토메모-unique-sentinel'
    assert apply(client,intake,note=private).status_code==200
    sid=prepare(client)
    report=client.get(f'/api/v1/sessions/{sid}/aar').json()
    assert report['subject']['external_layers'][0]['import_id']==intake
    markdown=client.get(f'/api/v1/sessions/{sid}/aar?format=markdown').text
    assert intake in markdown and '발행 당시 공공 기준자료' in markdown
    client.post('/api/v1/auth/demo',json={'profile':'board'})
    response=client.get(f'/api/v1/sessions/{sid}')
    assert response.status_code==200 and private not in response.text and 'external_reviews' not in response.text
    assert response.json()['subject']['external_layers'][0]['import_id']==intake
    with client.websocket_connect('/ws/v1/sessions/'+sid) as websocket:
        snapshot=websocket.receive_json()
        assert private not in json.dumps(snapshot,ensure_ascii=False)
        assert snapshot['state']['subject']['external_layers'][0]['import_id']==intake
    client.post('/api/v1/auth/demo',json={'profile':'observer'})
    response=client.get(f'/api/v1/sessions/{sid}')
    assert response.status_code==200 and not response.json()['subject']['external_layers']
    assert BUILDING['bldNm'] not in response.text and private not in response.text
    with client.websocket_connect('/ws/v1/sessions/'+sid) as websocket:
        assert not websocket.receive_json()['state']['subject']['external_layers']


def test_external_apply_retries_do_not_duplicate_review_and_stale_updates_fail(external_client):
    client,payload,calls,app=external_client
    use_real_mode(client)
    intake=preview(client).json()['id']
    body={'expected_state_version':ex_version(client),'selected_ids':[BUILDING['mgmBldrgstPk']],
          'building_id':'B01','fields':['floors'],'approved_for_training':True,'note':'합성 자료 검토'}
    path=f'/api/v1/exercises/exercise-demo/external-data/{intake}/apply'
    key=uuid4().hex
    first=client.post(path,json=body,headers={'Idempotency-Key':key})
    assert first.status_code==200
    assert client.post(path,json=body,headers={'Idempotency-Key':key}).json()==first.json()
    assert client.post(path,json=body,headers={'Idempotency-Key':uuid4().hex}).status_code==409
    assert len(client.get('/api/v1/exercises/exercise-demo').json()['exercise']['external_reviews'])==1


def test_preview_quota_is_bounded_and_retries_do_not_consume_quota(external_client):
    client,payload,calls,app=external_client
    key=uuid4().hex
    assert preview(client,key=key).status_code==200
    for _ in range(25):assert preview(client,key=key).status_code==200
    for _ in range(19):assert preview(client).status_code==200
    assert preview(client).status_code==429 and len(calls)==20


def test_concurrent_draft_change_during_fetch_discards_intake(external_client):
    client,payload,calls,app=external_client
    registry=app.state.external_data
    original=registry.fetch
    async def changing_fetch(request):
        result=await original(request)
        _,version=app.state.store.load('exercise','exercise-demo',DEMO_ORG)
        app.state.store.mutate('exercise','exercise-demo',DEMO_ORG,version,'synthetic-race','TEST_DRAFT_CHANGE',lambda value:value.update({'name':'경합 중 수정된 합성 이름'}))
        return result
    registry.fetch=changing_fetch
    assert preview(client).status_code==409


def test_old_json_defaults_remain_readable_and_editable(external_client):
    client,payload,calls,app=external_client
    store=app.state.store
    _,version=store.load('exercise','exercise-demo',DEMO_ORG)
    def legacy(data):
        data.pop('external_reviews')
        data['subject'].pop('external_layers')
        for feature in data['subject']['features']:
            feature.pop('data_origin')
            feature.pop('source_layer_id')
    store.mutate('exercise','exercise-demo',DEMO_ORG,version,'fixture','SYNTHETIC_LEGACY_FIXTURE',legacy)
    response=client.get('/api/v1/exercises/exercise-demo')
    assert response.status_code==200
    data=response.json()['exercise']
    assert not data['external_reviews'] and not data['subject']['external_layers']
    assert all(feature['data_origin']=='SIMULATED' for feature in data['subject']['features'])
    data['name']='구버전 JSON 저장 호환 합성 시험'
    response=client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':data},headers={'Idempotency-Key':uuid4().hex})
    assert response.status_code==200,response.text
    assert preview(client).status_code==200
