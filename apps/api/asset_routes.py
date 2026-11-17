"""Tenant-scoped private asset storage, review and audience-checked content."""
import asyncio
import hashlib
import json

from fastapi import Depends,File,Form,Header,HTTPException,UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from . import engine
from .asset_contracts import AssetAttach,AssetDetach,AssetProvenance
from .asset_validation import AssetValidationError,normalize_photo,validate_model
from .media_validation import MediaUnavailable
from .auth import identity,require
from .domain import AssetBinding,AssetMapping,AssetReview,Exercise,utcnow
from .requests import Versioned
from .safety import MAX_ASSET_BYTES
from .storage import fingerprint


def install_asset_routes(app):
    store=app.state.store;scanner=app.state.asset_scanner;processor=app.state.media_processor;slots=asyncio.Semaphore(2);inflight=asyncio.Semaphore(4)

    def key(value):
        if not value:raise HTTPException(428,'Idempotency-Key 헤더가 필요합니다.')
        if not 8<=len(value)<=100:raise HTTPException(400,'멱등키는8~100자입니다.')
        return value

    def load_exercise(id,user):
        payload,version=store.load('exercise',id,user['organization_id'])
        return Exercise.model_validate({k:v for k,v in payload.items() if k!='state_version'}),version

    async def inspect(data,kind):
        scan=await scanner.scan(data)
        checks={'scan':scan.model_dump(mode='json'),'canonical_scan':None,'manifest':None,
                'canonical_sha256':None,'canonical_bytes':0,'structural_check':'NOT_RUN','reason':scan.detail}
        if scan.status!='CLEAN':
            return checks,'REJECTED' if scan.status=='INFECTED' else 'QUARANTINED',data if scan.status!='INFECTED' else None,None
        try:
            canonical,manifest=await run_in_threadpool(processor.normalize if kind=='VIDEO' else validate_model if kind=='GLB' else normalize_photo,data)
        except MediaUnavailable as error:
            checks['reason']=str(error)
            return checks,'QUARANTINED',data,None
        except AssetValidationError as error:
            checks.update(structural_check='FAILED',reason=str(error))
            return checks,'REJECTED',None,None
        canonical_scan=await scanner.scan(canonical)
        checks.update(structural_check='PASSED',manifest=manifest.model_dump(mode='json'),canonical_scan=canonical_scan.model_dump(mode='json'))
        if canonical_scan.status!='CLEAN':
            checks['reason']='정규화본의 악성코드 검사를 통과하지 못했습니다.'
            return checks,'REJECTED' if canonical_scan.status=='INFECTED' else 'QUARANTINED',data if canonical_scan.status!='INFECTED' else None,None
        checks.update(canonical_sha256=hashlib.sha256(canonical).hexdigest(),canonical_bytes=len(canonical),reason='검사·정규화 완료. 이용권·좌표·층/객체 연결의 사람 검토가 필요합니다.')
        return checks,'VALIDATED',None,canonical

    @app.get('/api/v1/assets/status')
    def asset_status(user=Depends(identity)):
        require(user,'edit')
        return {**scanner.status(),'formats':['GLB','PNG','JPEG','MP4','WEBM'],'max_bytes':MAX_ASSET_BYTES,'ifc_conversion_available':False,'video_processing':processor.status()}

    @app.get('/api/v1/assets')
    def asset_list(user=Depends(identity)):
        require(user,'edit')
        return store.asset_summaries(user['organization_id'])

    @app.post('/api/v1/exercises/{id}/assets',status_code=201)
    async def intake(id:str,file:UploadFile=File(...),provenance:str=Form(...),expected_state_version:int=Form(...),
                     user=Depends(identity),idempotency_key:str|None=Header(None)):
        require(user,'edit');key(idempotency_key)
        if inflight.locked():raise HTTPException(429,'자산 처리 대기 한도에 도달했습니다. 잠시 후 재시도하세요.',headers={'Retry-After':'2'})
        async with inflight:return await intake_file(id,file,provenance,expected_state_version,user,idempotency_key)

    async def intake_file(id,file,provenance,expected_state_version,user,idempotency_key):
        try:source=AssetProvenance.model_validate_json(provenance)
        except (ValidationError,ValueError):raise HTTPException(422,'출처·이용범위 메타데이터 계약이 올바르지 않습니다.') from None
        name=file.filename or ''
        if '/' in name or '\\' in name or len(name)>160:raise HTTPException(422,'파일 이름·경로가 올바르지 않습니다.')
        extension=name.lower().rsplit('.',1)[-1]
        if extension not in ['glb','png','jpg','jpeg','mp4','webm']:raise HTTPException(422,'GLB/PNG/JPEG/MP4/WebM만 입력하세요. IFC는 승인된 오프라인 변환 후 GLB로 검사합니다.')
        data=await file.read(MAX_ASSET_BYTES+1)
        if not data or len(data)>MAX_ASSET_BYTES:raise HTTPException(413,'자산은15MiB 이하의 비어 있지 않은 파일이어야 합니다.')
        kind='GLB' if extension=='glb' else 'VIDEO' if extension in ['mp4','webm'] else 'PHOTO'
        signature=data.startswith(b'glTF') if kind=='GLB' else (data.startswith(b'\x1a\x45\xdf\xa3') or len(data)>=12 and data[4:8]==b'ftyp') if kind=='VIDEO' else (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff'))
        if not signature:
            raise HTTPException(422,'확장자와 실제 파일 형식이 일치하지 않습니다.')
        raw_sha=hashlib.sha256(data).hexdigest()
        if source.conversion_claim and (kind!='GLB' or source.conversion_claim.output_sha256!=raw_sha):
            raise HTTPException(422,'오프라인 변환 기록의 출력 해시와 입력 GLB가 일치하지 않습니다.')
        fp=fingerprint({'actor':user['id'],'exercise':id,'sha256':raw_sha,'provenance':source.model_dump(mode='json'),'kind':kind})
        aid='asset-'+hashlib.sha256((user['organization_id']+'\0'+idempotency_key).encode()).hexdigest()[:32]
        def existing():
            try:prior,_=store.load('asset',aid,user['organization_id'])
            except HTTPException as exc:
                if exc.status_code==404:return None
                raise
            if prior['fingerprint']!=fp:raise HTTPException(409,'같은 멱등키에 다른 자산 요청을 사용할 수 없습니다.')
            return prior
        prior=existing()
        if prior:return prior
        exercise,version=load_exercise(id,user)
        if exercise.published:raise HTTPException(409,'발행본의 자산은 고정됩니다. 복제본에서 검토하세요.')
        if version!=expected_state_version:raise HTTPException(409,'훈련 버전이 변경됐습니다.')
        count,used=store.asset_usage(user['organization_id'])
        if count>=500 or used+len(data)>200*1024*1024:
            raise HTTPException(413,'기관 자산 저장 한도를 초과했습니다.')
        async with slots:checks,status,original,canonical=await inspect(data,kind)
        if load_exercise(id,user)[1]!=version:raise HTTPException(409,'검사 중 훈련이 변경됐습니다. 새 버전에서 다시 확인하세요.')
        count,used=store.asset_usage(user['organization_id'])
        if count>=500 or used+len(original or b'')+len(canonical or b'')>200*1024*1024:raise HTTPException(413,'정규화 후 기관 자산 저장 한도를 초과했습니다.')
        source.source=source.source.model_copy(update={'rights':'unknown','reviewer':'','confidence':'unverified'})
        payload={'id':aid,'exercise_id':id,'created_by':user['id'],'created_at':utcnow(),'state_version':1,
                 'fingerprint':fp,'kind':kind,'mime':{'GLB':'model/gltf-binary','PHOTO':'image/png','VIDEO':'video/webm'}[kind],
                 'original_sha256':raw_sha,'original_bytes':len(data),'stored_bytes':len(original or b'')+len(canonical or b''),
                 'provenance':source.model_dump(mode='json'),'status':status,'scan_history':[],**checks}
        try:return store.create_asset(aid,user['organization_id'],payload,original,canonical,user['id'])
        except HTTPException as exc:
            if exc.status_code==409:
                prior=existing()
                if prior:return prior
            raise

    @app.get('/api/v1/assets/{asset_id}')
    def metadata(asset_id:str,user=Depends(identity)):
        require(user,'edit');data,version=store.load('asset',asset_id,user['organization_id'])
        return {**data,'state_version':version}

    @app.post('/api/v1/assets/{asset_id}/scan')
    async def rescan(asset_id:str,body:Versioned,user=Depends(identity),idempotency_key:str|None=Header(None)):
        require(user,'edit');key(idempotency_key)
        if inflight.locked():raise HTTPException(429,'자산 처리 대기 한도에 도달했습니다. 잠시 후 재시도하세요.',headers={'Retry-After':'2'})
        async with inflight:return await rescan_file(asset_id,body,user,idempotency_key)

    async def rescan_file(asset_id,body,user,idempotency_key):
        payload,version=store.load('asset',asset_id,user['organization_id'])
        request={}
        def terminal(data):raise HTTPException(409,'격리 상태의 현재 버전만 재검사할 수 있습니다.')
        if payload['status']!='QUARANTINED' or body.expected_state_version!=version:
            return store.mutate('asset',asset_id,user['organization_id'],body.expected_state_version,user['id'],'ASSET_RESCANNED',terminal,key=idempotency_key,request=request)
        data=store.asset_bytes(asset_id,user['organization_id'],True)
        async with slots:checks,status,original,canonical=await inspect(data,payload['kind'])
        if store.asset_usage(user['organization_id'])[1]-payload['stored_bytes']+len(original or b'')+len(canonical or b'')>200*1024*1024:raise HTTPException(413,'재검사 후 기관 자산 저장 한도를 초과했습니다.')
        def change(value):
            value['scan_history'].append({'scan':value['scan'],'canonical_scan':value['canonical_scan'],'at':utcnow()})
            if len(value['scan_history'])>100:raise HTTPException(422,'자산 검사 이력 한도에 도달했습니다.')
            value.update(checks);value.update(status=status,stored_bytes=len(original or b'')+len(canonical or b''))
        return store.mutate('asset',asset_id,user['organization_id'],body.expected_state_version,user['id'],'ASSET_RESCANNED',change,key=idempotency_key,request=request,blob_update=(original,canonical))

    def content(asset_id,user,binding=None):
        asset,_=store.load('asset',asset_id,user['organization_id'])
        if asset['status']!='VALIDATED' or asset['scan']['status']!='CLEAN' or asset['canonical_scan']['status']!='CLEAN':
            raise HTTPException(409,'검사·정규화가 완료된 자산만 표시할 수 있습니다.')
        if binding and (binding['sha256']!=asset['canonical_sha256'] or binding['source']['rights']!='approved'):
            raise HTTPException(409,'승인 자산 해시·이용권 불일치')
        data=store.asset_bytes(asset_id,user['organization_id'])
        if hashlib.sha256(data).hexdigest()!=asset['canonical_sha256']:raise HTTPException(409,'자산 무결성 검사를 통과하지 못했습니다.')
        return Response(data,media_type=asset['mime'],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                        'ETag':'"'+asset['canonical_sha256']+'"','Content-Disposition':'inline; filename="'+asset_id+{'GLB':'.glb','PHOTO':'.png','VIDEO':'.webm'}[asset['kind']]+'"'})

    @app.get('/api/v1/assets/{asset_id}/preview')
    def preview(asset_id:str,user=Depends(identity)):
        require(user,'edit');return content(asset_id,user)

    @app.post('/api/v1/exercises/{id}/assets/{asset_id}/attach')
    def attach(id:str,asset_id:str,body:AssetAttach,user=Depends(identity),idempotency_key:str|None=Header(None)):
        require(user,'edit');key(idempotency_key)
        if not body.rights_confirmed:raise HTTPException(422,'이용권·공개범위·좌표/층·객체 연결 검토 확인이 필요합니다.')
        asset,_=store.load('asset',asset_id,user['organization_id'])
        if asset['status']!='VALIDATED' or asset['scan']['status']!='CLEAN' or asset['canonical_scan']['status']!='CLEAN':raise HTTPException(409,'검사·정규화를 통과한 자산만 연결할 수 있습니다.')
        source=asset['provenance']['source'];mapping=body.mapping
        if source['classification']=='INTERNAL' and mapping.visibility!='STAFF':raise HTTPException(422,'내부 자산은 진행·평가 전용으로만 연결하세요.')
        if mapping.purpose not in {'GLB':{'MODEL'},'PHOTO':{'FACADE','REFERENCE'},'VIDEO':{'VIDEO'}}[asset['kind']]:raise HTTPException(422,'GLB는 모델, 사진은 외벽/참고, 영상은 사건 영상으로 연결하세요.')
        def change(value):
            exercise=Exercise.model_validate({k:v for k,v in value.items() if k!='state_version'})
            if exercise.published:raise HTTPException(409,'발행본의 자산 연결은 고정됩니다.')
            building=next((b for b in exercise.subject.buildings if b.id==mapping.building_id),None)
            if not building:raise HTTPException(422,'대상 건물이 없습니다.')
            if exercise.subject.target_mode=='VIRTUAL' and source['classification']!='SYNTHETIC' and mapping.purpose not in ['REFERENCE','VIDEO']:raise HTTPException(422,'실제 모델/외벽 사진은 실제·혼합 모드를 명시하세요.')
            if mapping.purpose=='MODEL':
                if mapping.photo_face!='NORTH':raise HTTPException(422,'사진 면 선택은 외벽 사진에만 사용합니다.')
                nodes={str(node['index']) for node in asset['manifest']['nodes']}
                if set(mapping.floor_map)!=nodes or not set(mapping.object_map)<=nodes:raise HTTPException(422,'모든 메시 객체를 층0(외관 전체) 또는 실제 층에 연결하세요.')
                if any(floor>building.floors or floor < -building.basement_floors for floor in mapping.floor_map.values()):raise HTTPException(422,'모델 층이 대상물 지상/지하 층수 범위를 벗어납니다.')
                for node,feature_id in mapping.object_map.items():
                    feature=next((f for f in exercise.subject.features if f.id==feature_id),None)
                    if not feature or feature.building_id!=building.id or feature.floor!=mapping.floor_map[node]:raise HTTPException(422,'모델 객체·대상물 구역의 건물/층이 일치하지 않습니다.')
                bounds=asset['manifest']['bounds'];size=[(bounds[1][i]-bounds[0][i])*mapping.unit_scale for i in range(3)]
                if not (0.5<=size[0]<=600 and 0.5<=size[2]<=600 and 1<=size[1]<=1000):raise HTTPException(422,'단위 보정 후 모델 크기가 지원 범위를 벗어납니다.')
            elif mapping.floor_map or mapping.object_map or mapping.unit_scale!=1 or mapping.rotation_y!=0 or mapping.offset!=[0,0,0]:
                raise HTTPException(422,'사진/영상에는 모델 좌표·층 매핑을 적용하지 않습니다.')
            if mapping.purpose in ['MODEL','FACADE'] and any(b.building_id==mapping.building_id and b.purpose in ['MODEL','FACADE'] and b.purpose!=mapping.purpose for b in exercise.subject.asset_bindings):
                raise HTTPException(422,'GLB는 내장 재질을 사용합니다. 외벽사진은 근사 모델에 연결하거나 참고 사진으로 보관하세요.')
            binding_id='binding-'+hashlib.sha256((id+'\0'+mapping.building_id+'\0'+mapping.purpose+('\0'+asset_id if mapping.purpose in ['REFERENCE','VIDEO'] else '')).encode()).hexdigest()[:32]
            approved={**source,'rights':'approved','reviewer':user['id'],'confidence':'simulated' if source['classification']=='SYNTHETIC' else 'approximate'}
            binding=AssetBinding(**mapping.model_dump(),id=binding_id,asset_id=asset_id,sha256=asset['canonical_sha256'],
                kind=asset['kind'],mime=asset['mime'],label=asset['provenance']['label'],source=approved,manifest=asset['manifest'],reviewed_at=utcnow())
            prior=next((value for value in exercise.subject.asset_bindings if value.id==binding_id),None)
            exercise.subject.asset_bindings=[b for b in exercise.subject.asset_bindings if b.id!=binding_id]+[binding]
            exercise.asset_reviews.append(AssetReview(asset_id=asset_id,binding_id=binding_id,actor_id=user['id'],at=utcnow(),note=body.note,action='ATTACH',mapping=mapping,
                prior_mapping=prior.model_dump(include=set(AssetMapping.model_fields)) if prior else None,supersedes_asset_id=prior.asset_id if prior else None))
            if mapping.purpose in ['MODEL','FACADE']:
                building.accuracy='SIMULATED' if source['classification']=='SYNTHETIC' else 'APPROXIMATE'
                exercise.subject.interior_verified=False
                if exercise.subject.model_accuracy=='VERIFIED':exercise.subject.model_accuracy='APPROXIMATE'
                if source['classification']!='SYNTHETIC' and building.id==exercise.subject.buildings[0].id:
                    exercise.subject.source=binding.source.model_copy(update={'provider':binding.source.provider+' / 모델·사진 검토 범위 한정'})
                    exercise.subject.model_accuracy='APPROXIMATE'
            exercise.revision+=1;exercise.rehearsal_passed=False;exercise.rehearsal_report=None;exercise.publication=None
            try:validated=Exercise.model_validate(exercise.model_dump(mode='json'))
            except ValidationError:raise HTTPException(422,'자산 연결 결과가 계약/크기 한도를 벗어납니다.') from None
            value.clear();value.update(validated.model_dump(mode='json'))
        return store.mutate('exercise',id,user['organization_id'],body.expected_state_version,user['id'],'ASSET_ATTACHED',change,key=idempotency_key,request={'asset_id':asset_id,**body.model_dump(mode='json',exclude={'expected_state_version'})})

    @app.post('/api/v1/exercises/{id}/assets/{binding_id}/detach')
    def detach(id:str,binding_id:str,body:AssetDetach,user=Depends(identity),idempotency_key:str|None=Header(None)):
        require(user,'edit');key(idempotency_key)
        def change(value):
            if value['published']:raise HTTPException(409,'발행본의 자산 연결은 고정됩니다.')
            bindings=value['subject'].get('asset_bindings',[])
            prior=next((binding for binding in bindings if binding['id']==binding_id),None)
            if not prior:raise HTTPException(404,'연결된 자산이 없습니다.')
            if len(value.get('asset_reviews',[]))>=500:raise HTTPException(422,'자산 검토 이력 한도에 도달했습니다.')
            value['subject']['asset_bindings']=[binding for binding in bindings if binding['id']!=binding_id]
            value.setdefault('asset_reviews',[]).append(AssetReview(asset_id=prior['asset_id'],binding_id=binding_id,actor_id=user['id'],at=utcnow(),note=body.note,action='DETACH',prior_mapping={key:prior.get(key,field.default) for key,field in AssetMapping.model_fields.items()},supersedes_asset_id=prior['asset_id']).model_dump(mode='json'))
            value.update(revision=value['revision']+1,rehearsal_passed=False,rehearsal_report=None,publication=None)
            try:Exercise.model_validate({k:v for k,v in value.items() if k!='state_version'})
            except ValidationError:raise HTTPException(422,'자산 연결 해제 결과가 계약·이력 한도를 벗어납니다.') from None
        return store.mutate('exercise',id,user['organization_id'],body.expected_state_version,user['id'],'ASSET_DETACHED',change,key=idempotency_key,request={'binding_id':binding_id,'note':body.note})

    def bound_content(subject,asset_id,user):
        binding=next((binding for binding in subject.get('asset_bindings',[]) if binding['asset_id']==asset_id),None)
        if not binding:raise HTTPException(404,'이 화면에 공개된 자산이 없습니다.')
        return content(asset_id,user,binding)

    @app.get('/api/v1/exercises/{id}/assets/{asset_id}/content')
    def exercise_content(id:str,asset_id:str,user=Depends(identity)):
        require(user,'edit');exercise,_=load_exercise(id,user)
        return bound_content(exercise.subject.model_dump(mode='json'),asset_id,user)

    @app.get('/api/v1/sessions/{id}/assets/{asset_id}/content')
    def session_content(id:str,asset_id:str,seq:int|None=None,user=Depends(identity)):
        require(user,'view');session,_=store.load('session',id,user['organization_id'])
        if seq is not None:
            if seq<0 or seq>session['seq']:raise HTTPException(422,'재생 시퀀스 범위를 벗어났습니다.')
            session=engine.replay_state(session,seq)
        return bound_content(engine.project(session,user)['subject'],asset_id,user)

    @app.get('/api/v1/board/sessions/{id}/assets/{asset_id}/content')
    def board_content(id:str,asset_id:str,seq:int|None=None,user=Depends(identity)):
        require(user,'view');session,_=store.load('session',id,user['organization_id'])
        if seq is not None:
            if seq<0 or seq>session['seq']:raise HTTPException(422,'재생 시퀀스 범위를 벗어났습니다.')
            session=engine.replay_state(session,seq)
        return bound_content(engine.project(session,{**user,'role':'board','person_id':None})['subject'],asset_id,user)
