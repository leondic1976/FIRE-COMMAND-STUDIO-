"""Synthetic processor/AV protocol tests; no claim of decoding real videos."""
import pytest
import asyncio
import httpx
import json
from fastapi.testclient import TestClient
from uuid import uuid4
from apps.api.application import create_app
from apps.api.domain import AssetManifest
from tests.asset_fixtures import FixtureScanner,glb
from tests.conftest import control,ex_version,prepare
from tests.integration.test_asset_workflow import attach,upload,assets,provenance

RAW=b'\x1a\x45\xdf\xa3SYNTHETIC_CONTAINER_PROTOCOL_ONLY'
CANONICAL=b'\x1a\x45\xdf\xa3SYNTHETIC_NORMALIZED_PROTOCOL_ONLY'


class ProtocolProcessor:
    def status(self):return {'configured':True,'real_host_or_av_verified':False,'reason':'SYNTHETIC PROTOCOL QA ONLY'}
    def normalize(self,data):
        assert data==RAW
        return CANONICAL,AssetManifest(width=320,height=180,duration_seconds=3,frame_rate=20,video_codec='vp8')


@pytest.fixture
def media(tmp_path):
    app=create_app('sqlite:///'+(tmp_path/'media.db').as_posix(),True,asset_scanner=FixtureScanner(),media_processor=ProtocolProcessor())
    with TestClient(app) as client:
        client.post('/api/v1/auth/demo',json={'profile':'facilitator'})
        yield client,app
    app.state.store.engine.dispose()


def create_binding(client,**mapping):
    result=upload(client,RAW,name='synthetic.webm');assert result.status_code==201,result.text
    aid=result.json()['id'];assert result.json()['status']=='VALIDATED'
    result=attach(client,aid,mapping={'purpose':'VIDEO','floor_map':{},'object_map':{},**mapping});assert result.status_code==200,result.text
    binding=client.get('/api/v1/exercises/exercise-demo').json()['exercise']['subject']['asset_bindings'][0]
    return aid,binding


def connect_cue(client,binding,event_index=0):
    data=client.get('/api/v1/exercises/exercise-demo').json();ex=data['exercise']
    ex['events'][event_index]['media_cues']=[{'binding_id':binding['id'],'feature_id':'B01-F02-Z01','clip_start_seconds':0,'clip_end_seconds':3}]
    result=client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':data['state_version'],'exercise':ex},headers={'Idempotency-Key':uuid4().hex});assert result.status_code==200,result.text


def test_video_without_approved_processor_stays_quarantined(assets):
    client,app,scanner=assets
    result=upload(client,RAW,name='synthetic.webm');assert result.status_code==201
    assert result.json()['kind']=='VIDEO' and result.json()['status']=='QUARANTINED'
    assert client.get('/api/v1/assets/'+result.json()['id']+'/preview').status_code==409
    assert len(scanner.calls)==1


def test_future_video_metadata_bytes_and_websocket_are_hidden_until_event_and_undo(media):
    client,app=media;aid,binding=create_binding(client);connect_cue(client,binding);sid=prepare(client)
    assert control(client,sid,'start').status_code==200
    content=f'/api/v1/board/sessions/{sid}/assets/{aid}/content'
    with client.websocket_connect('/ws/v1/board/'+sid) as socket:
        future=socket.receive_json()['state'];assert not future['subject']['asset_bindings']
        assert binding['id'] not in str(future) and aid not in str(future)
        assert client.get(content).status_code==404
        assert client.get(content+'?seq=1').status_code==404
        assert client.get(content+'?seq=999999').status_code==422
        assert control(client,sid,'release',event_id='EV-01').status_code==200
        shown=socket.receive_json()['state']
        assert shown['messages'][0]['media_cues'][0]['binding_id']==binding['id']
        assert shown['messages'][0]['event_seq']==shown['seq']
        assert shown['subject']['asset_bindings'][0]['asset_id']==aid
        release_seq=shown['seq']
        response=client.get(content);assert response.content==CANONICAL and response.headers['content-type'].startswith('video/webm')
        assert control(client,sid,'pause').status_code==200
        assert control(client,sid,'undo',reason='합성 영상 되돌림').status_code==200
    public=client.get('/api/v1/board/sessions/'+sid).json()
    assert not public['subject']['asset_bindings'] and not public['messages'][0]['media_cues']
    assert client.get(content).status_code==404
    assert client.get(content+f'?seq={release_seq}').content==CANONICAL
    assert client.get(content+'?seq=1').status_code==404
    report=client.get('/api/v1/sessions/'+sid+'/aar?format=markdown')
    assert '녹화 영상' in report.text and '클립 0.0~3.0초' in report.text and 'PRIVATE_SYNTHETIC_REVIEW_NOTE' not in report.text


def test_private_video_does_not_appear_on_board_or_clone(media):
    client,app=media;aid,binding=create_binding(client);connect_cue(client,binding,event_index=2)
    sid=prepare(client);assert control(client,sid,'start').status_code==200
    for eid in ['EV-01','EV-02','EV-03']:assert control(client,sid,'release',event_id=eid).status_code==200
    public=client.get('/api/v1/board/sessions/'+sid).json()
    assert not public['subject']['asset_bindings'] and aid not in str(public)
    assert client.get(f'/api/v1/board/sessions/{sid}/assets/{aid}/content').status_code==404
    clone=client.post('/api/v1/exercises/exercise-demo/clone').json()
    assert not clone['subject']['asset_bindings'] and all(not event['media_cues'] for event in clone['events'])
    client.post('/api/v1/auth/demo',json={'profile':'person-03'})
    assert client.get(f'/api/v1/sessions/{sid}/assets/{aid}/content').content==CANONICAL
    state=client.get('/api/v1/sessions/'+sid).json()
    assert state['messages'][-1]['media_cues'][0]['binding_id']==binding['id']
    client.post('/api/v1/auth/demo',json={'profile':'person-04'})
    assert client.get(f'/api/v1/sessions/{sid}/assets/{aid}/content').status_code==404


async def test_asset_queue_rejects_fifth_request_before_scan_or_storage(tmp_path):
    release=asyncio.Event()
    class BlockingScanner(FixtureScanner):
        async def scan(self,data):
            await release.wait()
            return await super().scan(data)
    scanner=BlockingScanner()
    app=create_app('sqlite:///'+(tmp_path/'bounded-queue.db').as_posix(),True,asset_scanner=scanner)
    tasks=[]
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8010') as client:
            assert (await client.post('/api/v1/auth/demo',json={'profile':'facilitator'})).status_code==200
            for _ in range(5):
                tasks.append(asyncio.create_task(client.post('/api/v1/exercises/exercise-demo/assets',files={'file':('synthetic.glb',glb(),'model/gltf-binary')},
                    data={'expected_state_version':'1','provenance':json.dumps(provenance())},headers={'Idempotency-Key':uuid4().hex})))
            completed,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED,timeout=3)
            assert completed,'Bounded queue should reject excess work before scanner completion'
            rejected=next(iter(completed)).result();assert rejected.status_code==429 and rejected.headers['retry-after']=='2'
            release.set();responses=await asyncio.gather(*tasks)
            assert sorted(response.status_code for response in responses)==[201,201,201,201,429]
            assert len(scanner.calls)==8
            assert len((await client.get('/api/v1/assets')).json())==4
    finally:
        release.set()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        app.state.store.engine.dispose()
