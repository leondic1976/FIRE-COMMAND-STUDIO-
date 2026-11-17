import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from apps.api.application import create_app,DEMO_ORG
from apps.api.auth import issue_token
from apps.api.storage import asset_blobs
from scripts.backup_restore import backup,restore
from tests.asset_fixtures import FixtureScanner,glb,photo
from tests.conftest import ex_version,prepare


@pytest.fixture
def assets(tmp_path):
    scanner=FixtureScanner()
    app=create_app('sqlite:///'+(tmp_path/'assets.db').as_posix(),True,asset_scanner=scanner)
    with TestClient(app) as client:
        assert client.post('/api/v1/auth/demo',json={'profile':'facilitator'}).status_code==200
        yield client,app,scanner
    app.state.store.engine.dispose()


def provenance(classification='SYNTHETIC'):
    return {'label':'합성 시험 모델/사진','creator':'합성 코드 생성기','license_scope':'자동시험 합성 자료. 실제 이용권·기관 승인 아님.',
            'source':{'provider':'프로젝트 합성 자료','as_of':'2026-11-17','classification':classification,'rights':'approved','reviewer':'FORGED','confidence':'verified'}}


def upload(client,content=None,name='synthetic.glb',key=None,source=None):
    return client.post('/api/v1/exercises/exercise-demo/assets',files={'file':(name,content if content is not None else glb(),'application/octet-stream')},
        data={'expected_state_version':str(ex_version(client)),'provenance':json.dumps(source or provenance(),ensure_ascii=False)},headers={'Idempotency-Key':key or uuid4().hex})


def attach(client,aid,key=None,**changes):
    mapping={'building_id':'B01','purpose':'MODEL','visibility':'PUBLIC','floor_map':{'0':1,'1':2,'2':3},'object_map':{'2':'B01-F03-Z01'}}
    extra=changes.pop('mapping',{});mapping.update(extra)
    return client.post(f'/api/v1/exercises/exercise-demo/assets/{aid}/attach',json={
        'expected_state_version':ex_version(client),'mapping':mapping,'rights_confirmed':True,'note':'PRIVATE_SYNTHETIC_REVIEW_NOTE',**changes},headers={'Idempotency-Key':key or uuid4().hex})


def test_upload_does_not_attach_and_idempotency_does_not_rescan(assets):
    client,app,scanner=assets
    before=client.get('/api/v1/exercises/exercise-demo').json();key=uuid4().hex
    first=upload(client,key=key);assert first.status_code==201,first.text
    assert first.json()['status']=='VALIDATED' and first.json()['structural_check']=='PASSED'
    assert first.json()['provenance']['source']['rights']=='unknown'
    assert not first.json()['provenance']['source']['reviewer']
    assert len(scanner.calls)==2 and client.get('/api/v1/exercises/exercise-demo').json()==before
    assert upload(client,key=key).json()==first.json() and len(scanner.calls)==2
    assert upload(client,key=key,source={**provenance(),'label':'다른 자료'}).status_code==409
    aid=first.json()['id'];preview=client.get(f'/api/v1/assets/{aid}/preview')
    assert preview.status_code==200 and hashlib.sha256(preview.content).hexdigest()==first.json()['canonical_sha256']
    assert 'no-store' in preview.headers['cache-control'] and preview.headers['x-content-type-options']=='nosniff'


def test_explicit_review_mapping_and_save_forgery_rejection(assets):
    client,app,scanner=assets;aid=upload(client).json()['id']
    before=ex_version(client)
    for changes in [{'rights_confirmed':False},{'mapping':{'floor_map':{'0':1}}},{'mapping':{'object_map':{'2':'B02'}}}, {'mapping':{'unit_scale':1000}}]:
        assert attach(client,aid,**changes).status_code==422
        assert ex_version(client)==before
    assert attach(client,aid).status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    binding=data['subject']['asset_bindings'][0]
    assert binding['manifest']['bounds']==[[-2,0,-2],[2,9,2]]
    assert binding['source']['rights']=='approved' and binding['source']['reviewer']=='facilitator'
    assert not data['subject']['interior_verified'] and not data['rehearsal_passed']
    data['subject']['asset_bindings'][0]['visibility']='STAFF'
    assert client.put('/api/v1/exercises/exercise-demo',json={'expected_state_version':ex_version(client),'exercise':data},headers={'Idempotency-Key':uuid4().hex}).status_code==422


def test_quarantine_requires_successful_rescan_and_retry_is_idempotent(assets):
    client,app,scanner=assets;scanner.result='NOT_CONFIGURED'
    asset=upload(client).json();aid=asset['id']
    assert asset['status']=='QUARANTINED' and asset['structural_check']=='NOT_RUN'
    assert client.get(f'/api/v1/assets/{aid}/preview').status_code==409
    assert attach(client,aid).status_code==409
    scanner.result='CLEAN';key=uuid4().hex
    path=f'/api/v1/assets/{aid}/scan';body={'expected_state_version':1}
    first=client.post(path,json=body,headers={'Idempotency-Key':key})
    assert first.status_code==200
    count=len(scanner.calls)
    assert client.post(path,json=body,headers={'Idempotency-Key':key}).json()==first.json()
    assert len(scanner.calls)==count
    assert client.get(f'/api/v1/assets/{aid}').json()['status']=='VALIDATED'
    assert attach(client,aid).status_code==200


@pytest.mark.parametrize('scan_status',['INFECTED','ERROR'])
def test_failed_scans_never_expose_content(assets,scan_status):
    client,app,scanner=assets;scanner.result=scan_status
    asset=upload(client).json()
    assert asset['status']==('REJECTED' if scan_status=='INFECTED' else 'QUARANTINED')
    assert asset['manifest'] is None and client.get(f"/api/v1/assets/{asset['id']}/preview").status_code==409
    assert attach(client,asset['id']).status_code==409


def test_photo_normalization_rights_and_internal_publication(assets):
    client,app,scanner=assets
    asset=upload(client,photo(),name='synthetic.png',source=provenance('INTERNAL')).json()
    preview=client.get(f"/api/v1/assets/{asset['id']}/preview")
    assert preview.status_code==200 and b'SYNTHETIC_PRIVATE' not in preview.content
    assert attach(client,asset['id'],mapping={'purpose':'REFERENCE','floor_map':{},'object_map':{}}).status_code==422
    assert attach(client,asset['id'],mapping={'purpose':'REFERENCE','visibility':'STAFF','floor_map':{},'object_map':{}}).status_code==200


def test_public_and_staff_asset_bytes_match_rest_and_ws_projection(assets):
    client,app,scanner=assets
    public=upload(client).json()['id'];assert attach(client,public).status_code==200
    private=upload(client,photo(),name='synthetic.png').json()['id']
    assert attach(client,private,mapping={'purpose':'REFERENCE','visibility':'STAFF','floor_map':{},'object_map':{}}).status_code==200
    sid=prepare(client)
    board_path=f'/api/v1/board/sessions/{sid}'
    assert client.get(board_path+f'/assets/{public}/content').status_code==200
    assert client.get(board_path+f'/assets/{private}/content').status_code==404
    assert client.get(f'/api/v1/sessions/{sid}/assets/{private}/content').status_code==200
    client.post('/api/v1/auth/demo',json={'profile':'board'})
    state=client.get('/api/v1/sessions/'+sid)
    assert state.status_code==200 and private not in state.text and 'PRIVATE_SYNTHETIC_REVIEW_NOTE' not in state.text
    assert client.get(f'/api/v1/sessions/{sid}/assets/{private}/content').status_code==404
    assert client.get(f'/api/v1/sessions/{sid}/assets/{public}/content').status_code==200
    assert client.get(f'/api/v1/assets/{public}/preview').status_code==403
    assert client.get(f'/api/v1/assets/{public}').status_code==403
    with client.websocket_connect('/ws/v1/sessions/'+sid) as websocket:
        frame=json.dumps(websocket.receive_json(),ensure_ascii=False)
        assert private not in frame and 'PRIVATE_SYNTHETIC_REVIEW_NOTE' not in frame


def test_cross_tenant_asset_and_content_are_hidden(assets):
    client,app,scanner=assets;aid=upload(client).json()['id'];assert attach(client,aid).status_code==200
    sid=prepare(client)
    client.cookies.set('studio_session',issue_token(app.state.store,{'id':'other','name':'다른 가상 기관','role':'admin','organization_id':'org-other','person_id':None}))
    for path in [f'/assets/{aid}',f'/assets/{aid}/preview',f'/sessions/{sid}/assets/{aid}/content',f'/exercises/exercise-demo/assets/{aid}/content']:
        assert client.get('/api/v1'+path).status_code==404
    assert client.get('/api/v1/assets').json()==[]


def test_published_assets_are_frozen_and_clones_need_new_review(assets):
    client,app,scanner=assets;aid=upload(client).json()['id'];assert attach(client,aid).status_code==200
    sid=prepare(client)
    assert attach(client,aid).status_code==409
    assert upload(client).status_code==409
    clone=client.post('/api/v1/exercises/exercise-demo/clone').json()
    assert not clone['subject']['asset_bindings'] and not clone['asset_reviews']
    assert client.get(f"/api/v1/exercises/{clone['id']}/assets/{aid}/content").status_code==404
    assert client.get(f'/api/v1/sessions/{sid}/assets/{aid}/content').status_code==200


def test_tampered_canonical_bytes_fail_integrity_check(assets):
    client,app,scanner=assets;aid=upload(client).json()['id'];assert attach(client,aid).status_code==200
    with app.state.store.engine.begin() as conn:conn.execute(update(asset_blobs).where(asset_blobs.c.asset_id==aid).values(canonical=b'corrupt'))
    assert client.get(f'/api/v1/exercises/exercise-demo/assets/{aid}/content').status_code==409


def test_asset_blob_backup_restore_and_reopen(assets,tmp_path):
    client,app,scanner=assets;aid=upload(client).json()['id'];assert attach(client,aid).status_code==200
    expected=client.get(f'/api/v1/exercises/exercise-demo/assets/{aid}/content').content
    source=Path(app.state.store.url.removeprefix('sqlite:///'));archive=tmp_path/'backup.db';target=tmp_path/'restored.db'
    assert backup(source,archive)['schema_versions']==[1,2]
    restore(archive,target)
    recovered=create_app('sqlite:///'+target.as_posix(),True,asset_scanner=scanner)
    try:
        with TestClient(recovered) as restored:
            restored.post('/api/v1/auth/demo',json={'profile':'facilitator'})
            content=restored.get(f'/api/v1/exercises/exercise-demo/assets/{aid}/content')
            assert content.status_code==200 and content.content==expected
    finally:recovered.state.store.engine.dispose()


def test_old_schema_one_backup_upgrades_without_losing_records(tmp_path):
    path=tmp_path/'legacy.db'
    initial=create_app('sqlite:///'+path.as_posix(),True);initial.state.store.engine.dispose()
    with sqlite3.connect(path) as conn:
        conn.execute('DROP TABLE asset_blobs');conn.execute('DELETE FROM schema_versions WHERE version=2')
        before=conn.execute('SELECT count(*) FROM records').fetchone()[0]
    upgraded=create_app('sqlite:///'+path.as_posix(),True)
    try:
        with sqlite3.connect(path) as conn:
            assert conn.execute('SELECT version FROM schema_versions ORDER BY version').fetchall()==[(1,),(2,)]
            assert conn.execute('SELECT count(*) FROM records').fetchone()[0]==before
    finally:upgraded.state.store.engine.dispose()


def test_mapping_change_and_detach_keep_previous_reviewed_mapping(assets):
    client,app,scanner=assets;aid=upload(client).json()['id']
    assert attach(client,aid).status_code==200
    assert attach(client,aid,mapping={'offset':[8,0,3],'rotation_y':25}).status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    review=data['asset_reviews'][-1]
    assert review['prior_mapping']['offset']==[0,0,0] and review['mapping']['offset']==[8,0,3] and review['supersedes_asset_id']==aid
    binding=data['subject']['asset_bindings'][0]['id']
    response=client.post(f'/api/v1/exercises/exercise-demo/assets/{binding}/detach',json={'expected_state_version':ex_version(client),'note':'합성 자산 연결 해제'},headers={'Idempotency-Key':uuid4().hex})
    assert response.status_code==200
    data=client.get('/api/v1/exercises/exercise-demo').json()['exercise']
    assert not data['subject']['asset_bindings'] and data['asset_reviews'][-1]['prior_mapping']['offset']==[8,0,3]
    assert client.get(f'/api/v1/assets/{aid}/preview').status_code==200


def test_offline_conversion_claim_matches_bytes_but_does_not_approve_rights(assets):
    client,app,scanner=assets;raw=glb()
    source=provenance();source['conversion_claim']={'input_sha256':'1'*64,'output_sha256':'2'*64,'tool_manifest_sha256':'3'*64,'converter_version':'SYNTHETIC DECLARATION ONLY'}
    assert upload(client,raw,source=source).status_code==422 and not scanner.calls
    source['conversion_claim']['output_sha256']=hashlib.sha256(raw).hexdigest()
    result=upload(client,raw,source=source)
    assert result.status_code==201 and result.json()['provenance']['source']['rights']=='unknown'
    assert result.json()['provenance']['conversion_claim']==source['conversion_claim']


def test_aar_includes_frozen_asset_attribution_and_escapes_markdown(assets):
    client,app,scanner=assets;source=provenance();source['creator']='<script>SYNTHETIC</script>'
    aid=upload(client,source=source).json()['id'];assert attach(client,aid).status_code==200
    sid=prepare(client)
    report=client.get(f'/api/v1/sessions/{sid}/aar').json()
    assert report['asset_provenance'][0]['creator']==source['creator'] and report['asset_provenance'][0]['license_scope']==source['license_scope']
    markdown=client.get(f'/api/v1/sessions/{sid}/aar?format=markdown').text
    assert '&lt;script&gt;' in markdown and '<script>' not in markdown and aid in markdown
