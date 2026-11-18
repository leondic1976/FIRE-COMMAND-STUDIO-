"""Run an extracted web distribution with Python only, in fresh synthetic QA data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import zipfile

import httpx


def verify(archive, directory):
    archive, directory = Path(archive).resolve(), Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Use a fresh empty QA directory')
    extracted, data = directory / 'package', directory / 'private-data'
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            if not (extracted / name).resolve().is_relative_to(extracted) or '\\' in name:
                raise ValueError('Invalid archive path')
        source.extractall(extracted)
    manifest = json.loads((extracted / 'SERVER_PACKAGE.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        file = extracted / item['path']
        if not file.resolve().is_relative_to(extracted) or hashlib.sha256(file.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Distribution file hash mismatch')
    env = dict(os.environ)
    for key in ['PYTHONHOME', 'PYTHONPATH', 'DATABASE_URL', 'ALLOWED_ORIGINS', 'TRAINING_MODE', 'COOKIE_SECURE']:
        env.pop(key, None)
    env['PYTHON_DOTENV_DISABLED'] = '1'
    # No Node binary or original checkout is needed by the extracted server.
    env['PATH'] = str(Path(env.get('SystemRoot', 'C:/Windows')) / 'System32') if os.name == 'nt' else '/usr/bin:/bin'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    screen = manifest.get('track') == 'screen'
    command = [sys.executable, '-m', 'screen.server' if screen else 'web.server', '--data-dir', str(data)]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = 'http://127.0.0.1:' + str(port)
    log = (directory / 'synthetic-server.log').open('wb')

    def execute(extra, success=True):
        result = subprocess.run(command + extra, env=env, cwd=extracted, capture_output=True, creationflags=flags, timeout=60)
        if (result.returncode == 0) != success:
            raise RuntimeError('Packaged server maintenance returned an unexpected result')
        return result

    def start():
        process = subprocess.Popen(command + ['--port', str(port)], env=env, cwd=extracted,
            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Packaged server stopped before readiness')
            try:
                if httpx.get(base + '/api/v1/health', trust_env=False, timeout=1).status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        process.terminate()
        process.wait(timeout=10)
        raise RuntimeError('Packaged server readiness timed out')

    def stop(process):
        process.terminate()
        process.wait(timeout=15)

    execute(['--check'])
    process = start()
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            status = client.get('/api/v1/runtime/status').json()
            assert status['track'] == ('screen' if screen else 'web') and status['version'] == manifest.get('core_version', manifest['version'])
            assert client.get('/').status_code == 200
            assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code == 200
            if screen:
                scenario = client.get('/api/screen/scenarios').json()[0]['id']
                created = client.post('/api/screen/runs', json={'scenario_id': scenario}, headers={'Idempotency-Key': 'extracted-screen-qa'}).json()
                screen_id = created['id']
                assert client.get('/api/screen/board/' + screen_id).json()['status'] == 'READY'
                assert 'private_prompt' not in client.get('/api/screen/board/' + screen_id).text
            first = client.post('/api/v1/exercises', json={'template': 'factory', 'name': 'Synthetic packaged server QA'}).json()['id']
            assert client.get('/api/v1/exercises/' + first + '/configuration').json()['format'] == 'FIRE_COMMAND_STUDIO_CONFIGURATION'
            backup = directory / 'consistent-backup.db'
            execute(['--backup-to', str(backup)])
            later = client.post('/api/v1/exercises', json={'template': 'factory', 'name': 'Synthetic later record'}).json()['id']
            execute(['--restore-from', str(backup)], success=False)
    finally:
        stop(process)
    execute(['--restore-from', str(backup)])
    process = start()
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).status_code == 200
            assert client.get('/api/v1/exercises/' + first).status_code == 200
            assert client.get('/api/v1/exercises/' + later).status_code == 404
            if screen:
                assert client.get('/api/screen/board/' + screen_id).json()['status'] == 'READY'
            assert json.loads((data / 'settings.json').read_text())['schema_version'] == 1
            assert json.loads((data / 'server.json').read_text())['port'] == port
    finally:
        stop(process)
        log.close()
    return {'version': manifest['version'], 'source_commit': manifest['source_commit'], 'source_dirty': manifest['source_dirty'],
        'extracted_payload_hashes_verified': len(manifest['files']), 'node_not_required': True,
        'json_configuration': True, 'restart_persistence': True, 'backup_restore_roundtrip': True,
        'active_restore_rejected': True, 'synthetic_only': True, 'public_deployment_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.archive, args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
