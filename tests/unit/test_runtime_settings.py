import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.api.runtime_settings import SettingsDocument, SettingsError, apply_settings, load_settings, save_settings, validate_settings


@pytest.fixture(autouse=True)
def preserve_process_environment():
    with patch.dict(os.environ, dict(os.environ), clear=True):
        yield


def test_defaults_and_existing_env_migrate_once_without_losing_the_original(tmp_path):
    legacy = tmp_path / 'settings.env'
    content = 'VITE_KAKAO_MAPS_APPROVED=true\nVITE_KAKAO_JAVASCRIPT_KEY=' + '0' * 32 + '\nCLAMD_PORT=3311\nDATABASE_URL=DO_NOT_USE\n'
    legacy.write_text(content)
    result = load_settings(tmp_path)
    assert legacy.read_text() == content
    assert result.settings['VITE_KAKAO_MAPS_APPROVED'] is True
    assert result.settings['CLAMD_PORT'] == 3311
    assert 'DATABASE_URL' not in result.settings
    saved = json.loads((tmp_path / 'settings.json').read_text())
    assert saved['schema_version'] == 1 and not saved['settings']['ASSET_SCAN_APPROVED']
    legacy.write_text('VITE_KAKAO_MAPS_APPROVED=false')
    assert load_settings(tmp_path) == result


@pytest.mark.parametrize('document', [
    b'{"schema_version":2}', b'{"schema_version":1,"schema_version":1}',
    b'{"settings":{"DATABASE_URL":"anything"}}',
    b'{"settings":{"ASSET_SCAN_APPROVED":"true"}}',
    b'{"settings":{"CLAMD_PORT":true}}', b'{"settings":{"CLAMD_PORT":70000}}',
    b'{"settings":{"CLAMD_PORT":NaN}}', b'{' + b' ' * (128 * 1024) + b'}',
], ids=['version', 'duplicate', 'unknown-key', 'string-approval', 'boolean-port', 'port-range', 'non-finite', 'oversize'])
def test_invalid_settings_are_rejected_without_echoing_secret_values(document):
    with pytest.raises(SettingsError) as error:
        validate_settings(document)
    assert 'anything' not in str(error.value)


def test_atomic_replacement_failure_keeps_original_and_valid_backup(tmp_path, monkeypatch):
    old = load_settings(tmp_path)
    before = (tmp_path / 'settings.json').read_bytes()
    import apps.api.runtime_settings as module
    replace = module.os.replace

    def fail(source, destination):
        if Path(destination).name == 'settings.json':
            raise OSError('synthetic replacement failure')
        return replace(source, destination)

    monkeypatch.setattr(module.os, 'replace', fail)
    with pytest.raises(OSError):
        save_settings(tmp_path, SettingsDocument(settings={'CLAMD_PORT': 3311}))
    assert (tmp_path / 'settings.json').read_bytes() == before
    assert validate_settings((tmp_path / 'settings.previous.json').read_bytes()) == old
    assert not list(tmp_path.glob('*.tmp'))


def test_environment_precedence_is_explicit(monkeypatch):
    monkeypatch.setenv('CLAMD_PORT', '3322')
    settings = SettingsDocument(settings={'CLAMD_PORT': 3311})
    apply_settings(settings, environment_precedence=True)
    assert __import__('os').environ['CLAMD_PORT'] == '3322'
    apply_settings(settings)
    assert __import__('os').environ['CLAMD_PORT'] == '3311'
