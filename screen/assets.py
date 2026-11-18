"""Approved local models/photos; never scrape URLs or reuse street-view images."""
import asyncio
import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import Field, ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from apps.api.auth import identity, require
from apps.api.asset_validation import AssetValidationError, normalize_photo, validate_model
from apps.api.domain import utcnow
from apps.api.runtime_settings import SettingsError, strict_json
from apps.api.storage import records, asset_blobs, fingerprint
from sqlalchemy.exc import IntegrityError
from .contracts import Source, Strict


def approved(store, id, org):
    value, _ = store.load('screen_asset', id, org)
    if value['status'] != 'APPROVED':
        raise HTTPException(409, '자료의 검사·이용권 검수가 필요합니다.')
    return value


class Review(Strict):
    expected_state_version: int = Field(ge=1, strict=True)
    rights_confirmed: bool
    reference: str = Field(min_length=1, max_length=500)


def install_assets(app):
    router = APIRouter(prefix='/api/screen')
    store = app.state.store
    slots = asyncio.Semaphore(2)
    inflight = asyncio.Semaphore(4)

    @router.get('/assets')
    def listing(user=Depends(identity)):
        require(user, 'edit')
        return [{key: value.get(key) for key in ['id', 'kind', 'source', 'status', 'state_version', 'reason', 'bytes']} for value in store.list('screen_asset', user['organization_id'])]

    @router.post('/assets', status_code=201)
    async def upload(file: UploadFile = File(...), source: str = Form(...), user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'edit')
        if not idempotency_key or not 8 <= len(idempotency_key) <= 100:
            raise HTTPException(428, '8~100자 멱등키가 필요합니다.')
        if inflight.locked():
            raise HTTPException(429, '자료 처리 대기 한도를 초과했습니다.')
        async with inflight:
            try:
                provenance = Source.model_validate(strict_json(source.encode(), 4096)).model_dump(mode='json')
            except (ValidationError, SettingsError):
                raise HTTPException(422, '자료 출처를 확인하세요.') from None
            data = await file.read(8 * 1024 * 1024 + 1)
            if not data or len(data) > 8 * 1024 * 1024:
                raise HTTPException(413, '자료는0바이트 초과8MB 이하여야 합니다.')
            id = 'screen-asset-' + hashlib.sha256((user['organization_id'] + idempotency_key).encode()).hexdigest()[:24]
            fp = fingerprint({'actor': user['id'], 'source': provenance, 'sha256': hashlib.sha256(data).hexdigest()})
            def prior():
                try:
                    existing = store.load('screen_asset', id, user['organization_id'])[0]
                except HTTPException as error:
                    if error.status_code == 404:
                        return None
                    raise
                if existing['fingerprint'] != fp:
                    raise HTTPException(409, '같은 멱등키에 다른 자료를 사용할 수 없습니다.')
                return existing
            existing = prior()
            if existing is not None:
                return existing
            count, used = store.asset_usage(user['organization_id'])
            if count >= 100 or used + len(data) * 2 > 200 * 1024 * 1024:
                raise HTTPException(413, '기관 자료 저장 한도를 초과했습니다.')
            kind = 'GLB' if data[:4] == b'glTF' else 'PHOTO'
            canonical, manifest = None, None
            status, reason = 'QUARANTINED', '승인된 검사기와 이용권 검수가 필요합니다.'
            async with slots:
                scan = await app.state.asset_scanner.scan(data)
                if scan.status == 'INFECTED':
                    raise HTTPException(422, '위험 자료를 거절했습니다.')
                if scan.status == 'CLEAN':
                    try:
                        canonical, manifest = await run_in_threadpool(validate_model if kind == 'GLB' else normalize_photo, data)
                    except AssetValidationError:
                        raise HTTPException(422, '자료 구조·외부 참조·크기/기하 제한을 확인하세요.') from None
                    normalized_scan = await app.state.asset_scanner.scan(canonical)
                    if normalized_scan.status == 'CLEAN':
                        status, reason = 'VALIDATED', '검사 통과. 이용권·대상물/좌표의 사람 검수가 필요합니다.'
                    else:
                        canonical, manifest = None, None
            value = {'id': id, 'state_version': 1, 'kind': kind, 'status': status, 'source': provenance,
                     'fingerprint': fp,
                     'bytes': len(canonical or data), 'sha256': hashlib.sha256(canonical or data).hexdigest(),
                     'reason': reason, 'manifest': manifest.model_dump(mode='json') if manifest else None,
                     'scan': scan.model_dump(mode='json'), 'review': None, 'created_at': utcnow()}
            count, used = store.asset_usage(user['organization_id'])
            if count >= 100 or used + len(canonical or data) > 200 * 1024 * 1024:
                raise HTTPException(413, '자료 처리 후 저장 한도를 초과했습니다.')
            try:
                with store.engine.begin() as connection:
                    connection.execute(records.insert().values(kind='screen_asset', id=id, organization_id=user['organization_id'], version=1, payload=value))
                    connection.execute(asset_blobs.insert().values(organization_id=user['organization_id'], asset_id=id, original=None if canonical else data, canonical=canonical))
                    store.log(connection, user['organization_id'], user['id'], 'SCREEN_ASSET_INTAKE', id)
            except IntegrityError:
                existing = prior()
                if existing is not None:
                    return existing
                raise HTTPException(409, '자료가 동시에 변경됐습니다. 목록을 확인하세요.') from None
            return value

    @router.post('/assets/{id}/review')
    def review(id: str, body: Review, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'edit')
        if not idempotency_key:
            raise HTTPException(428, '멱등키가 필요합니다.')
        def change(value):
            if value['status'] not in ('VALIDATED', 'APPROVED'):
                raise HTTPException(409, '검사 완료 전 승인할 수 없습니다.')
            value['status'] = 'APPROVED' if body.rights_confirmed else 'VALIDATED'
            value['review'] = {'by': user['id'], 'at': utcnow(), 'reference': body.reference, 'rights_confirmed': body.rights_confirmed}
        return store.mutate('screen_asset', id, user['organization_id'], body.expected_state_version, user['id'], 'SCREEN_ASSET_REVIEW', change, key=idempotency_key, request=body.model_dump(exclude={'expected_state_version'}))

    def content(id, org):
        value = approved(store, id, org)
        return Response(store.asset_bytes(id, org), media_type='model/gltf-binary' if value['kind'] == 'GLB' else 'image/png')

    @router.get('/assets/{id}/content')
    def editor_content(id: str, user=Depends(identity)):
        require(user, 'edit')
        return content(id, user['organization_id'])

    @router.get('/board/{run_id}/assets/{id}')
    def board_content(run_id: str, id: str, user=Depends(identity)):
        require(user, 'view')
        run, _ = store.load('screen_run', run_id, user['organization_id'])
        if user['role'] == 'observer' and run['scene']['site']['target_mode'] != 'VIRTUAL':
            raise HTTPException(403, '자료 접근 권한이 없습니다.')
        ids = {asset for building in run['scene']['buildings'] for asset in [building.get('model_asset_id'), *building.get('facade_assets', {}).values()] if asset}
        if id not in ids:
            raise HTTPException(404, '이 현장의 자료가 아닙니다.')
        return content(id, user['organization_id'])
    app.include_router(router)
