"""Tenant/role-checked screen contracts and public projections."""
import asyncio
import copy
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import Field, ValidationError
from sqlalchemy import select

from apps.api.auth import identity, require, resolve_token, PERMISSIONS
from apps.api.runtime_settings import SettingsError, strict_json
from apps.api.storage import records
from . import engine
from .contracts import Scenario, Strict

DATA = Path(__file__).parent / 'data'


class Save(Strict):
    expected_state_version: int = Field(ge=1, strict=True)
    scenario: Scenario


class CreateRun(Strict):
    scenario_id: str = Field(min_length=1, max_length=80)


class Command(Strict):
    expected_state_version: int = Field(ge=1, strict=True)
    action: str = Field(max_length=20)
    note: str = Field(default='', max_length=4000)


def install(app, clock):
    store = app.state.store
    router = APIRouter(prefix='/api/screen')
    default = Scenario.model_validate(json.loads((DATA / 'warehouse.json').read_text(encoding='utf-8'))).model_dump(mode='json')
    catalog = json.loads((DATA / 'catalog.json').read_text(encoding='utf-8'))
    allowed_origins = {app.state.runtime_settings.public_url.rstrip('/'), *app.state.runtime_settings.development_origins}

    def check_catalog(scenario):
        ids = {item['id'] for item in catalog['items']}
        if any(event['catalog_id'] not in ids for event in scenario['events']):
            raise HTTPException(422, '등록되지 않은 상황 ID입니다. 카탈로그를 확인하세요.')

    def seeded(user):
        require(user, 'edit')
        if not store.list('screen_scenario', user['organization_id']):
            try:
                store.create('screen_scenario', default['id'], user['organization_id'], {'scenario': default, 'state_version': 1}, user['id'])
            except HTTPException as error:
                if error.status_code != 409:
                    raise

    def access(id, user):
        require(user, 'view')
        run, version = store.load('screen_run', id, user['organization_id'])
        if user['role'] == 'observer' and run['scene']['site']['target_mode'] != 'VIRTUAL':
            raise HTTPException(403, '참관자는 가상 대상물만 열람합니다.')
        return run, version

    def snapshot(id, user, public=False):
        run, _ = access(id, user)
        operator = not public and 'control' in PERMISSIONS.get(user['role'], set())
        return engine.project(run, clock(), operator)

    def check_assets(scenario, user):
        from .assets import approved
        total_bytes = total_triangles = total_pixels = 0
        if scenario['site']['target_mode'] == 'REAL' and not all(building['model_asset_id'] for building in scenario['buildings']):
            raise HTTPException(422, '실제 대상물에는 검수된 각 건물의 실제3D 모델이 필요합니다. 근사/가상을 선택하거나 승인 자료를 연결하세요.')
        for building in scenario['buildings']:
            ids = ([building['model_asset_id']] if building['model_asset_id'] else []) + list(building['facade_assets'].values())
            for asset_id in ids:
                asset = approved(store, asset_id, user['organization_id'])
                expected = 'GLB' if asset_id == building['model_asset_id'] else 'PHOTO'
                if asset['kind'] != expected:
                    raise HTTPException(422, '모델과 방면 사진의 자료 형식을 확인하세요.')
                total_bytes += asset['bytes']
                total_triangles += asset['manifest'].get('triangles', 0)
                total_pixels += asset['manifest'].get('texture_pixels', 0)
        if total_bytes > 64 * 1024 * 1024 or total_triangles > 500000 or total_pixels > 32 * 1024 * 1024:
            raise HTTPException(422, '현장 자료 예산(64MB/50만 삼각형/32M 텍스처 화소)을 초과합니다. 모델·사진을 줄이세요.')

    @router.get('/scenarios')
    def scenarios(user=Depends(identity)):
        seeded(user)
        return [{'id': value['scenario']['id'], 'title': value['scenario']['title'], 'state_version': value['state_version']} for value in store.list('screen_scenario', user['organization_id'])]

    @router.get('/scenarios/{id}')
    def scenario(id: str, user=Depends(identity)):
        require(user, 'edit')
        return store.load('screen_scenario', id, user['organization_id'])[0]

    @router.put('/scenarios/{id}')
    def save(id: str, body: Save, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'edit')
        if not idempotency_key:
            raise HTTPException(428, '멱등키가 필요합니다.')
        value = body.scenario.model_dump(mode='json')
        value['id'] = id
        check_catalog(value)
        def change(payload):
            payload['scenario'] = value
        return store.mutate('screen_scenario', id, user['organization_id'], body.expected_state_version, user['id'], 'SCREEN_SCENARIO_SAVED', change, key=idempotency_key, request=value)

    @router.get('/catalog')
    def get_catalog(user=Depends(identity)):
        require(user, 'edit')
        return catalog

    @router.post('/scenarios/validate')
    def validate(body: Scenario, user=Depends(identity)):
        require(user, 'edit')
        value = body.model_dump(mode='json')
        check_catalog(value)
        check_assets(value, user)
        return value

    @router.get('/scenarios/{id}/download')
    def download(id: str, user=Depends(identity)):
        require(user, 'edit')
        value = copy.deepcopy(store.load('screen_scenario', id, user['organization_id'])[0]['scenario'])
        for building in value['buildings']:
            building.update(model_asset_id=None, facade_assets={})
        value['site']['target_mode'] = 'VIRTUAL' if value['site']['target_mode'] == 'VIRTUAL' else 'APPROXIMATE'
        return Response(json.dumps(value, ensure_ascii=False, indent=2) + '\n', media_type='application/json', headers={'Content-Disposition': 'attachment; filename="screen-scenario.json"'})

    @router.post('/scenarios/import', status_code=201)
    async def import_file(file: UploadFile = File(...), user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'edit')
        try:
            data = await file.read(2 * 1024 * 1024 + 1)
            raw = strict_json(data, 2 * 1024 * 1024)
            if type(raw.get('schema_version')) is not int:
                raise ValueError('Version')
            value = Scenario.model_validate(raw).model_dump(mode='json')
        except (SettingsError, ValidationError, ValueError, AttributeError):
            raise HTTPException(422, 'JSON 형식·버전·필수 항목과 최소60초 간격을 확인하세요.') from None
        check_catalog(value)
        request = copy.deepcopy(value)
        value['id'] = 'scenario-' + uuid4().hex[:16]
        for building in value['buildings']:
            building.update(model_asset_id=None, facade_assets={})
        if value['site']['target_mode'] != 'VIRTUAL':
            value['site']['target_mode'] = 'APPROXIMATE'
            value['site']['source']['accuracy'] = 'approximate'
        return store.create_idempotent('screen_scenario', value['id'], user['organization_id'], {'scenario': value, 'state_version': 1}, user['id'], idempotency_key, request)

    @router.get('/runs')
    def runs(user=Depends(identity)):
        require(user, 'view')
        return [{key: value[key] for key in ['id', 'title', 'status', 'state_version']} for value in sorted(store.list('screen_run', user['organization_id']), key=lambda value: value.get('created_at', 0), reverse=True)
                if user['role'] != 'observer' or value['scene']['site']['target_mode'] == 'VIRTUAL']

    @router.post('/runs', status_code=201)
    def create(body: CreateRun, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'control')
        value = store.load('screen_scenario', body.scenario_id, user['organization_id'])[0]['scenario']
        check_assets(value, user)
        run = engine.new_run(value, clock())
        return store.create_idempotent('screen_run', run['id'], user['organization_id'], run, user['id'], idempotency_key, body.model_dump())

    @router.get('/runs/{id}')
    def get_run(id: str, user=Depends(identity)):
        return snapshot(id, user)

    @router.get('/board/{id}')
    def board(id: str, user=Depends(identity)):
        return snapshot(id, user, True)

    @router.post('/runs/{id}/commands')
    def control(id: str, body: Command, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'control')
        if not idempotency_key:
            raise HTTPException(428, '멱등키가 필요합니다.')
        return store.mutate('screen_run', id, user['organization_id'], body.expected_state_version, user['id'], 'SCREEN_' + body.action.upper(),
            lambda run: engine.command(run, body.action, clock(), body.note), key=idempotency_key, request=body.model_dump(exclude={'expected_state_version'}))

    @router.get('/runs/{id}/report')
    def report(id: str, user=Depends(identity)):
        require(user, 'control')
        run, _ = access(id, user)
        value = {key: run[key] for key in ['id', 'title', 'status', 'seq', 'messages', 'notes', 'log']}
        return Response(json.dumps(value, ensure_ascii=False, indent=2) + '\n', media_type='application/json', headers={'Content-Disposition': 'attachment; filename="screen-meeting-record.json"'})

    @app.websocket('/ws/screen/{id}')
    @app.websocket('/ws/screen/board/{id}')
    async def stream(ws: WebSocket, id: str):
        public = ws.url.path.startswith('/ws/screen/board/')
        if ws.headers.get('origin') not in allowed_origins:
            await ws.close(code=1008)
            return
        try:
            user = resolve_token(store, ws.cookies.get('studio_session'))
            access(id, user)
        except HTTPException:
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while True:
                user = resolve_token(store, ws.cookies.get('studio_session'))
                await ws.send_json(snapshot(id, user, public))
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=1)
                except asyncio.TimeoutError:
                    pass
        except HTTPException:
            await ws.close(code=1008)
        except (WebSocketDisconnect, RuntimeError):
            pass

    # create_web_app registers its SPA fallback last. Keep the new API before it.
    fallback = next(route for route in app.router.routes if getattr(route, 'path', '') == '/{path:path}')
    app.router.routes.remove(fallback)
    app.include_router(router)
    from .assets import install_assets
    install_assets(app)
    app.router.routes.append(fallback)
    previous_lifespan = app.router.lifespan_context

    def tick_all(recovery=False):
        with store.engine.connect() as connection:
            rows = connection.execute(select(records.c.id, records.c.organization_id, records.c.version, records.c.payload).where(records.c.kind == 'screen_run')).mappings().all()
        now = clock()
        for row in rows:
            run = row['payload']
            if run['status'] != 'RUNNING':
                continue
            due = engine.next_due(run)
            if recovery or (due is not None and run['scenario']['mode'] == 'auto' and engine.elapsed(run, now) >= due) or now - run['checkpoint_at'] >= 5:
                try:
                    store.mutate('screen_run', row['id'], row['organization_id'], row['version'], 'server', 'SCREEN_RECOVERED' if recovery else 'SCREEN_TICK',
                        lambda value: engine.recover(value, now) if recovery else engine.tick(value, now))
                except HTTPException as error:
                    if error.status_code != 409:
                        raise

    app.state.screen_tick = tick_all

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application):
            tick_all(True)
            async def scheduler():
                while True:
                    await asyncio.to_thread(tick_all)
                    await asyncio.sleep(.25)
            task = asyncio.create_task(scheduler())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
    app.router.lifespan_context = lifespan
