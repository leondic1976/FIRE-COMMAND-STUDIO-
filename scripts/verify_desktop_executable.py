"""Real frozen executable smoke, persistence and backup roundtrip in fresh QA data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import httpx


def verify(executable, directory):
    executable, directory = Path(executable).resolve(), Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Use a new empty QA data directory')
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for name in ['PYTHONPATH', 'PYTHONHOME']:
        env.pop(name, None)
    env['PATH'] = str(Path(env.get('SystemRoot', 'C:/Windows')) / 'System32')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    common = [str(executable), '--headless', '--no-browser', '--data-dir', str(directory)]

    def command(extra):
        result = subprocess.run(common + extra, env=env, cwd=directory, creationflags=flags, timeout=60)
        if result.returncode:
            raise RuntimeError('Frozen command failed: ' + extra[0])

    def launch():
        process = subprocess.Popen(common + ['--port', '0'], env=env, cwd=directory, creationflags=flags)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Frozen application terminated before readiness')
            descriptor = directory / 'instance.json'
            if descriptor.exists():
                port = json.loads(descriptor.read_text(encoding='utf-8'))['port']
                return process, 'http://127.0.0.1:' + str(port)
            time.sleep(.1)
        process.terminate()
        process.wait(timeout=10)
        raise RuntimeError('Frozen application readiness timed out')

    def stop(process):
        command(['--shutdown'])
        process.wait(timeout=20)
        if process.returncode:
            raise RuntimeError('Frozen application did not shut down cleanly')

    command(['--self-check'])
    check = json.loads((directory / 'installation-check.json').read_text())
    assert check['png_normalization'] and check['xlsx_structure'] and not check['av_scan_performed']
    process, base = launch()
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.get('/_desktop/status').json()['loopback_only'] is True
            assert client.post('/_desktop/shutdown').status_code == 403
            assert client.get('/api/v1/clock').status_code == 401
            assert client.get('/api/v1/health').json()['schema_version'] == 2
            assert client.get('/').status_code == 200
            assert client.post('/api/v1/auth/demo', json={'profile':'facilitator'}).status_code == 200
            first = client.post('/api/v1/exercises', json={'template':'factory','name':'Synthetic frozen installer QA'}).json()['id']
            archive = directory / 'synthetic-backup.db'
            command(['--backup-to', str(archive)])
            later = client.post('/api/v1/exercises', json={'template':'factory','name':'Synthetic later record'}).json()['id']
    finally:
        stop(process)
    command(['--restore-from', str(archive), '--port', '0'])
    process, base = launch()
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.post('/api/v1/auth/demo', json={'profile':'facilitator'}).status_code == 200
            assert client.get('/api/v1/exercises/' + first).status_code == 200
            assert client.get('/api/v1/exercises/' + later).status_code == 404
    finally:
        stop(process)
    return {'frozen_executable':True,'python_removed_from_path':True,'png_and_xlsx_processed':True,
            'native_schema_version':2,'per_user_persistence':True,'backup_restore_roundtrip':True,
            'unauthorized_shutdown_rejected':True,'browser_tests_included':False,
            'build_interpreter':check['python'],'synthetic_only':True,'real_av_scan_claimed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.executable, args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
