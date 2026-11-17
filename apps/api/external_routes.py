"""Reviewable external data: immutable intake, explicit draft-only application."""
from __future__ import annotations

import hashlib
import json
import math
import time

from fastapi import Depends, Header, HTTPException
from pydantic import ValidationError

from .auth import identity, require
from .domain import Exercise, ExternalLayer, ExternalReview, Feature, utcnow
from .external_data import ExternalBatch, ProviderFailure
from .requests import ExternalApply, ExternalPreview


def install_external_routes(app):
    store=app.state.store
    registry=app.state.external_data
    quota={}

    def load_exercise(id,user):
        payload,version=store.load('exercise',id,user['organization_id'])
        payload.pop('state_version',None)
        return Exercise.model_validate(payload),version

    def checked_key(key):
        if not key:raise HTTPException(428,'Idempotency-Key 헤더가 필요합니다.')
        if not 8<=len(key)<=100:raise HTTPException(400,'멱등키는 8~100자입니다.')
        return key

    @app.post('/api/v1/exercises/{id}/external-data/preview')
    async def preview(id:str,body:ExternalPreview,user=Depends(identity),idempotency_key:str|None=Header(None)):
        require(user,'edit')
        key=checked_key(idempotency_key)
        fingerprint=hashlib.sha256(json.dumps({'actor':user['id'],'body':body.model_dump(mode='json')},sort_keys=True).encode()).hexdigest()
        intake_id='external-'+hashlib.sha256((user['organization_id']+'\0'+id+'\0'+key).encode()).hexdigest()[:32]
        def existing():
            try:prior,_=store.load('external_import',intake_id,user['organization_id'])
            except HTTPException as exc:
                if exc.status_code==404:return None
                raise
            if prior['fingerprint']!=fingerprint:raise HTTPException(409,'같은 멱등키에 다른 수집 요청을 사용할 수 없습니다.')
            return prior
        prior=existing()
        if prior:return prior
        exercise,version=load_exercise(id,user)
        if exercise.published:raise HTTPException(409,'발행본은 불변입니다. 복제본에서 자료를 검토하세요.')
        if version!=body.expected_state_version:raise HTTPException(409,'훈련 버전이 변경됐습니다. 새로고침하세요.')
        if exercise.subject.source.classification=='INTERNAL':
            raise HTTPException(403,'내부 대상물의 위치 정보를 외부 제공처로 조회할 수 없습니다. 승인된 오프라인 자료를 사용하세요.')
        quota_key=(user['organization_id'],user['id'],body.request.provider)
        now=time.monotonic()
        recent=[stamp for stamp in quota.get(quota_key,[]) if now-stamp<60]
        if len(recent)>=20:raise HTTPException(429,'외부 수집은 공급자별 분당20회로 제한합니다.')
        quota[quota_key]=recent+[now]
        try:
            batch=await registry.fetch(body.request)
        except ProviderFailure as error:
            status={'DISABLED':409,'TOO_LARGE':413,'TIMEOUT':504}.get(error.code,502)
            raise HTTPException(status,{'code':error.code,'message':error.message,'fallback':'로컬 도식·수동 입력으로 훈련을 계속할 수 있습니다.'}) from None
        _,current=load_exercise(id,user)
        if current!=version:raise HTTPException(409,'수집 중 훈련이 변경됐습니다. 새 버전에서 다시 확인하세요.')
        intake={'id':intake_id,'exercise_id':id,'exercise_version_at_fetch':version,'created_by':user['id'],
                'fingerprint':fingerprint,'status':'AWAITING_REVIEW','request':body.request.model_dump(mode='json'),
                'batch':batch.model_dump(mode='json'),'training_only':True}
        try:return store.create('external_import',intake_id,user['organization_id'],intake,user['id'])
        except HTTPException as exc:
            if exc.status_code!=409:raise
            prior=existing()
            if prior:return prior
            raise

    @app.get('/api/v1/exercises/{id}/external-data/{intake_id}')
    def read_intake(id:str,intake_id:str,user=Depends(identity)):
        require(user,'edit')
        load_exercise(id,user)
        intake,_=store.load('external_import',intake_id,user['organization_id'])
        if intake['exercise_id']!=id:raise HTTPException(404,'자료를 찾을 수 없습니다.')
        return intake

    @app.post('/api/v1/exercises/{id}/external-data/{intake_id}/apply')
    def apply_intake(id:str,intake_id:str,body:ExternalApply,user=Depends(identity),idempotency_key:str|None=Header(None)):
        require(user,'edit')
        checked_key(idempotency_key)
        if not body.approved_for_training:raise HTTPException(422,'이용권·출처·좌표·시각·반영 항목의 검토 확인이 필요합니다.')
        if len(set(body.selected_ids))!=len(body.selected_ids) or len(set(body.fields))!=len(body.fields):
            raise HTTPException(422,'중복 선택 항목이 있습니다.')
        intake,_=store.load('external_import',intake_id,user['organization_id'])
        if intake['exercise_id']!=id:raise HTTPException(404,'자료를 찾을 수 없습니다.')
        batch=ExternalBatch.model_validate(intake['batch'])
        lookup={record.external_id:record for record in batch.records}
        if any(record_id not in lookup for record_id in body.selected_ids):raise HTTPException(422,'수집본에 없는 항목입니다.')
        selected=[lookup[record_id] for record_id in body.selected_ids]
        def change(payload):
            original={key:value for key,value in payload.items() if key!='state_version'}
            exercise=Exercise.model_validate(original)
            if exercise.published:raise HTTPException(409,'발행본은 불변입니다. 복제본에서 반영하세요.')
            provider=batch.provider
            if provider!='weather' and exercise.subject.target_mode=='VIRTUAL':
                raise HTTPException(422,'실제 공간자료는 실제/혼합 대상물 모드를 명시한 뒤 반영하세요.')
            source=batch.source.model_copy(update={'rights':'approved','confidence':'approximate','reviewer':user['id']})
            layer_id=provider+'-'+(body.building_id if provider=='building_registry' else 'reference')
            prior=next((layer for layer in exercise.subject.external_layers if layer.id==layer_id),None)
            if provider=='building_registry':
                if len(selected)!=1 or not body.fields:raise HTTPException(422,'건물은 한 항목과 반영 속성을 선택하세요.')
                building=next((value for value in exercise.subject.buildings if value.id==body.building_id),None)
                if not building:raise HTTPException(422,'대상 건물이 없습니다.')
                record=selected[0]
                if 'floors' in body.fields:
                    floors=record.fields.get('floors_above')
                    if type(floors) is not int or not 1<=floors<=80:raise HTTPException(422,'표제부 층수가 모델 지원 범위1~80층이 아닙니다.')
                    if any(feature.building_id==building.id and feature.floor>floors for feature in exercise.subject.features):
                        raise HTTPException(422,'기존 구역·사건이 더 높은 층을 참조합니다. 구역/사건을 먼저 검토하세요.')
                    building.floors=floors
                    for floor in range(1,floors+1):
                        feature_id=f'{building.id}-F{floor:02}-Z01'
                        if not any(feature.id==feature_id for feature in exercise.subject.features):
                            exercise.subject.features.append(Feature(id=feature_id,name=f'{building.name} {floor}층 근사 구역',kind='ZONE',building_id=building.id,floor=floor,state={'smoke':0,'fire':0,'water':0,'casualties':0}))
                if 'name' in body.fields:building.name=record.name
                if 'use' in body.fields:
                    if not record.fields.get('use'):raise HTTPException(422,'표제부 용도가 없습니다. 반영 항목에서 제외하세요.')
                    building.use=str(record.fields['use'])
                building.accuracy='APPROXIMATE'
                exercise.subject.model_accuracy='APPROXIMATE'
                exercise.subject.interior_verified=False
                exercise.subject.source=source.model_copy(update={'provider':source.provider+' 속성 / 치수·배치는 사용자 근사'})
            elif provider=='hydrant':
                latitude=exercise.subject.latitude
                scale=111320*math.cos(math.radians(latitude))
                if abs(scale)<1:raise HTTPException(422,'이 위도에서는 지역 근사 좌표를 사용할 수 없습니다.')
                exercise.subject.features=[feature for feature in exercise.subject.features if feature.source_layer_id!=layer_id]
                for record in selected:
                    x=(float(record.fields['longitude'])-exercise.subject.longitude)*scale
                    z=-(float(record.fields['latitude'])-latitude)*111320
                    if abs(x)>2000 or abs(z)>2000:raise HTTPException(422,'선택한 시설이 대상물 중심2km 범위를 벗어납니다.')
                    feature_id='HYD-'+hashlib.sha256(record.external_id.encode()).hexdigest()[:16]
                    # A historic inventory/pressure entry never establishes live availability.
                    feature=Feature(id=feature_id,name=record.name,kind='HYDRANT',x=x,z=z,state={'water':'UNCONFIRMED'},data_origin='REFERENCE',source_layer_id=layer_id)
                    exercise.subject.features=[existing for existing in exercise.subject.features if existing.id!=feature_id]
                    exercise.subject.features.append(feature)
            layer=ExternalLayer(id=layer_id,import_id=intake_id,provider=provider,source=source,retrieved_at=batch.retrieved_at,
                raw_sha256=batch.raw_sha256,records=selected,warnings=batch.warnings)
            exercise.subject.external_layers=[value for value in exercise.subject.external_layers if value.id!=layer_id]+[layer]
            exercise.external_reviews.append(ExternalReview(import_id=intake_id,layer_id=layer_id,actor_id=user['id'],at=utcnow(),note=body.note,
                selected_ids=body.selected_ids,applied_fields=body.fields if provider=='building_registry' else [],supersedes_import_id=prior.import_id if prior else None))
            exercise.revision+=1
            exercise.rehearsal_passed=False
            exercise.rehearsal_report=None
            exercise.publication=None
            try:validated=Exercise.model_validate(exercise.model_dump(mode='json'))
            except ValidationError:
                raise HTTPException(422,'반영 결과가 대상물 크기·필드 계약과 맞지 않습니다.') from None
            payload.clear()
            payload.update(validated.model_dump(mode='json'))
        return store.mutate('exercise',id,user['organization_id'],body.expected_state_version,user['id'],'EXTERNAL_DATA_REVIEWED',change,
                            key=idempotency_key,request={'intake_id':intake_id,**body.model_dump(mode='json',exclude={'expected_state_version'})})
