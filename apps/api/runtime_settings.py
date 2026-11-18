"""Private, versioned JSON settings shared by web and Windows runtimes."""
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SETTINGS_KEYS = {'EXTERNAL_DATA_APPROVED', 'EXTERNAL_DATA_APPROVAL_REF', 'DATA_GOV_BUILDING_KEY',
    'KMA_SERVICE_KEY', 'DATA_GOV_HYDRANT_KEY', 'HYDRANT_DATASET_PATH', 'HYDRANT_CATALOG_URL',
    'VITE_KAKAO_MAPS_APPROVED', 'VITE_KAKAO_JAVASCRIPT_KEY', 'ASSET_SCAN_APPROVED',
    'ASSET_SCAN_APPROVAL_REF', 'CLAMD_PORT', 'MEDIA_PROCESSING_APPROVED', 'MEDIA_PROCESSING_APPROVAL_REF',
    'MEDIA_HOST_ISOLATION_CONFIRMED', 'MEDIA_TOOL_MANIFEST', 'MEDIA_TOOL_MANIFEST_SHA256',
    'IFC_CONVERSION_APPROVED', 'IFC_CONVERSION_APPROVAL_REF', 'IFC_OFFLINE_HOST_CONFIRMED',
    'IFC_TOOL_MANIFEST', 'IFC_TOOL_MANIFEST_SHA256'}
BOOLEAN_KEYS = {key for key in SETTINGS_KEYS if key.endswith(('_APPROVED', '_CONFIRMED'))}
DEFAULT_SETTINGS = {**{key: False for key in BOOLEAN_KEYS}, 'CLAMD_PORT': 3310}
MAX_SETTINGS_BYTES = 128 * 1024
_environment_lock = RLock()


class SettingsError(ValueError):
    pass


def strict_json(data, maximum=MAX_SETTINGS_BYTES):
    if not data or len(data) > maximum:
        raise SettingsError('JSON 파일 크기 제한을 확인하세요.')

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise SettingsError('JSON에 중복 항목이 있습니다.')
            result[key] = value
        return result

    def constant(_):
        raise SettingsError('JSON에는 유한한 값만 사용할 수 있습니다.')

    try:
        return json.loads(data.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError):
        raise SettingsError('올바른 UTF-8 JSON 파일이 필요합니다. 중복 항목과 파일 구조를 확인하세요.') from None


class SettingsDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: int = Field(default=1, ge=1, le=1)
    settings: dict[str, str | bool | int] = Field(default_factory=lambda: dict(DEFAULT_SETTINGS))

    @field_validator('settings', mode='before')
    @classmethod
    def allowed_settings(cls, value):
        if not isinstance(value, dict) or set(value) - SETTINGS_KEYS:
            raise ValueError('Unsupported settings')
        result = {**DEFAULT_SETTINGS, **value}
        for key, item in result.items():
            if key in BOOLEAN_KEYS:
                if type(item) is not bool:
                    raise ValueError('Approval flags must be boolean')
            elif key == 'CLAMD_PORT':
                if type(item) is not int or not 1 <= item <= 65535:
                    raise ValueError('Invalid local scanner port')
            elif not isinstance(item, str) or len(item) > 8192 or any(c in item for c in '\x00\r\n'):
                raise ValueError('Invalid setting value')
        return result


def atomic_json(path, document):
    """Validate before calling; failed replacement leaves the existing file intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.' + path.name + '-', suffix='.tmp', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            os.chmod(temporary, 0o600)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_settings(data):
    try:
        return SettingsDocument.model_validate(strict_json(data))
    except ValidationError:
        # Pydantic errors may include a secret input. Never print or return them.
        raise SettingsError('실행 설정 JSON의 버전·항목·값을 확인하세요.') from None


def save_settings(directory, document):
    document = validate_settings(document.model_dump_json().encode('utf-8'))
    Path(directory).mkdir(parents=True, exist_ok=True, mode=0o700)
    path = Path(directory) / 'settings.json'
    if path.exists():
        previous = validate_settings(path.read_bytes())
        atomic_json(path.with_name('settings.previous.json'), previous.model_dump())
    atomic_json(path, document.model_dump())
    return path


def load_settings(directory):
    with _environment_lock:
        return _load_settings(directory)


def _load_settings(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / 'settings.json'
    if path.exists():
        return validate_settings(path.read_bytes())
    values = {}
    legacy = directory / 'settings.env'
    if legacy.exists():
        if legacy.stat().st_size > MAX_SETTINGS_BYTES:
            raise SettingsError('이전 실행 설정 파일 크기 제한을 확인하세요.')
        from dotenv import dotenv_values
        for key, value in dotenv_values(legacy).items():
            if key not in SETTINGS_KEYS or value is None:
                continue
            if key in BOOLEAN_KEYS:
                if value not in ('true', 'false'):
                    raise SettingsError('이전 승인 설정 값은 true 또는 false여야 합니다.')
                values[key] = value == 'true'
            elif key == 'CLAMD_PORT':
                try:
                    values[key] = int(value)
                except ValueError:
                    raise SettingsError('이전 검사기 포트 설정을 확인하세요.') from None
            else:
                values[key] = value
    document = validate_settings(json.dumps({'schema_version': 1, 'settings': values}).encode())
    save_settings(directory, document)
    return document


def apply_settings(document, *, environment_precedence=False):
    for key, value in document.settings.items():
        text = str(value).lower() if type(value) is bool else str(value)
        if not environment_precedence or key not in os.environ:
            os.environ[key] = text
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'


@contextmanager
def runtime_environment(document, overrides=None, *, environment_precedence=False):
    """Construct an application snapshot without changing other app instances."""
    overrides = overrides or {}
    keys = SETTINGS_KEYS | set(overrides) | {'PYTHON_DOTENV_DISABLED'}
    with _environment_lock:
        previous = {key: os.environ.get(key) for key in keys}
        try:
            apply_settings(document, environment_precedence=environment_precedence)
            os.environ.update(overrides)
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
