"""Portable training definitions. Approval and execution records never transfer."""
import hashlib
import json
from typing import Literal
from uuid import uuid4

from fastapi import Depends, File, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .auth import identity, require
from .domain import Exercise, utcnow, validate_exercise
from .runtime_settings import SettingsError, strict_json


MAX_CONFIGURATION_BYTES = 2 * 1024 * 1024
WARNINGS = [
    '새 편집본으로 불러옵니다. 기존 훈련과 실행 기록은 변경하지 않습니다.',
    '숙지·구두 확인·리허설·발행·기관 승인과 자료 검수는 다시 확인해야 합니다.',
    '자산·영상·공공자료 연결은 이전하지 않습니다. 원본 자료를 다시 등록·검토하세요.',
]


def digest(configuration):
    encoded = json.dumps(configuration, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


class ConfigurationFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['FIRE_COMMAND_STUDIO_CONFIGURATION']
    schema_version: Literal[1]
    created_at: str = Field(max_length=80)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    configuration: Exercise


def definition(exercise):
    data = exercise.model_dump(mode='json')
    data.update(readiness={}, reviews={}, published=False, rehearsal_passed=False, revision=1,
                organization_approval='', publication=None, rehearsal_report=None, asset_reviews=[], external_reviews=[],
                practice_owner_person_id=None)
    data['subject']['asset_bindings'] = []
    data['subject']['external_layers'] = []
    data['subject']['features'] = [item for item in data['subject']['features'] if item.get('data_origin') != 'REFERENCE']
    for item in data['events']:
        item['media_cues'] = []
    return data


def export_configuration(exercise):
    data = definition(exercise)
    result = {'format': 'FIRE_COMMAND_STUDIO_CONFIGURATION', 'schema_version': 1,
              'created_at': utcnow(), 'sha256': digest(data), 'configuration': data}
    return (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def read_configuration(data):
    try:
        raw = strict_json(data, MAX_CONFIGURATION_BYTES)
        if not isinstance(raw, dict) or raw.get('schema_version') != 1 or type(raw.get('schema_version')) is not int:
            raise SettingsError('Unsupported version')
        document = ConfigurationFile.model_validate(raw)
        # Verify the original JSON representation; model defaults/coercions must
        # not turn an altered file into a matching checksum.
        if digest(raw['configuration']) != document.sha256:
            raise SettingsError('Checksum mismatch')
        return document
    except (SettingsError, ValidationError, ValueError, TypeError, KeyError, RecursionError):
        raise HTTPException(422, '훈련 설정 JSON의 형식·버전·체크섬·필수 항목을 확인하세요.') from None


def import_definition(document):
    data = definition(document.configuration)
    data['id'] = 'exercise-' + uuid4().hex[:12]
    data['subject']['source'].update(rights='unknown', reviewer='', confidence='unverified')
    data['subject']['interior_verified'] = False
    if data['subject']['model_accuracy'] == 'VERIFIED':
        data['subject']['model_accuracy'] = 'APPROXIMATE'
    return Exercise.model_validate(data)


def install_configuration_routes(app):
    async def uploaded(file):
        data = await file.read(MAX_CONFIGURATION_BYTES + 1)
        if len(data) > MAX_CONFIGURATION_BYTES:
            raise HTTPException(413, '훈련 설정 JSON은 2MB 이하여야 합니다.')
        return read_configuration(data)

    @app.get('/api/v1/exercises/{id}/configuration')
    def export(id: str, user=Depends(identity)):
        require(user, 'edit')
        data, _ = app.state.store.load('exercise', id, user['organization_id'])
        exercise = Exercise.model_validate({k: v for k, v in data.items() if k != 'state_version'})
        content = export_configuration(exercise)
        if len(content) > MAX_CONFIGURATION_BYTES:
            raise HTTPException(413, '설정이 2MB를 초과합니다. 설정을 나누거나 전체 백업을 사용하세요.')
        return Response(content, media_type='application/json', headers={'Content-Disposition': 'attachment; filename="training-configuration.json"'})

    @app.post('/api/v1/configurations/preview')
    async def preview(file: UploadFile = File(...), user=Depends(identity)):
        require(user, 'edit')
        document = await uploaded(file)
        exercise = import_definition(document)
        return {'name': exercise.name, 'roles': len(exercise.roles), 'persons': len(exercise.persons),
                'events': len(exercise.events), 'warnings': WARNINGS, 'issues': validate_exercise(exercise, False),
                'sha256': document.sha256}

    @app.post('/api/v1/configurations/import', status_code=201)
    async def import_file(file: UploadFile = File(...), user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, 'edit')
        document = await uploaded(file)
        exercise = import_definition(document)
        payload = {**exercise.model_dump(mode='json'), 'state_version': 1}
        return app.state.store.create_idempotent('exercise', exercise.id, user['organization_id'], payload,
                                                user['id'], idempotency_key, {'configuration_sha256': document.sha256})
