"""Reinstall/uninstall a previously installed product in a workspace QA sandbox.

Never targets the normal LocalAppData installation or real user data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import winreg

import httpx


def verify(installer, qa_root):
    workspace = Path(__file__).resolve().parents[1]
    qa_root = qa_root.resolve(strict=True)
    qa_root.relative_to(workspace / 'runtime')
    installation, data = qa_root / 'install', qa_root / 'browser'
    executable = installation / 'FIRECommandStudio.exe'
    uninstaller = installation / 'unins000.exe'
    for folder in [qa_root, installation, data]:
        if folder.is_symlink() or folder.is_junction():
            raise ValueError('QA directories must not redirect to other folders')
    if not executable.is_file() or not (data / 'storage/studio.db').is_file():
        raise ValueError('First install and browser QA must already be complete')
    if any(qa_root.glob('*/instance.json')):
        raise ValueError('Stop every QA service before replacing installed files')
    registry = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6AEB0A45-52B9-4864-B838-A7A911A827E9}_is1'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
        location = Path(winreg.QueryValueEx(key, 'InstallLocation')[0]).resolve()
        if location != installation:
            raise ValueError('Registered product belongs to another installation')
    env = dict(os.environ)
    env['PATH'] = str(Path(env.get('SystemRoot', 'C:/Windows')) / 'System32')
    for name in ['PYTHONHOME', 'PYTHONPATH']:
        env.pop(name, None)
    flags = subprocess.CREATE_NO_WINDOW
    common = [str(executable), '--headless', '--no-browser', '--data-dir', str(data)]

    def command(argv):
        result = subprocess.run(argv, env=env, cwd=qa_root, creationflags=flags, timeout=90)
        if result.returncode:
            raise RuntimeError('QA command returned ' + str(result.returncode))

    backup = data / 'backups' / 'lifecycle.db'
    backup.parent.mkdir(exist_ok=True)
    command(common + ['--backup-to', str(backup)])

    def fingerprint():
        names = ['storage/studio.db', 'backups/lifecycle.db', 'backups/lifecycle.db.manifest.json']
        names += [name for name in ['settings.env', 'settings.json', 'settings.previous.json'] if (data / name).is_file()]
        return {name: hashlib.sha256((data / name).read_bytes()).hexdigest() for name in names}

    def install():
        command([str(installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', '/NOICONS', '/DIR=' + str(installation)])
        assert executable.is_file() and uninstaller.is_file()

    def uninstall():
        # Exact registered workspace installation checked above; user data is outside it.
        command([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'])
        for _ in range(150):
            if not executable.exists() and not uninstaller.exists():
                break
            time.sleep(.1)
        assert not executable.exists() and not uninstaller.exists()

    def launch_and_count():
        process = subprocess.Popen(common + ['--port', '0'], env=env, cwd=qa_root, creationflags=flags)
        try:
            for _ in range(200):
                if (data / 'instance.json').is_file():
                    break
                if process.poll() is not None:
                    raise RuntimeError('Reinstalled executable stopped before readiness')
                time.sleep(.1)
            port = json.loads((data / 'instance.json').read_text())['port']
            with httpx.Client(base_url='http://127.0.0.1:' + str(port), trust_env=False) as client:
                assert client.get('/_desktop/status').json()['loopback_only']
                assert client.post('/api/v1/auth/demo', json={'profile': 'facilitator'}).is_success
                response = client.get('/api/v1/exercises')
                response.raise_for_status()
                count = len(response.json())
                assert count > 0
            return count
        finally:
            command(common + ['--shutdown'])
            process.wait(timeout=20)
            assert process.returncode == 0

    before = fingerprint()
    install()
    assert fingerprint() == before
    count = launch_and_count()
    before = fingerprint()
    uninstall()
    assert fingerprint() == before
    install()
    assert fingerprint() == before
    assert launch_and_count() == count
    before = fingerprint()
    uninstall()
    assert fingerprint() == before
    return {'same_version_reinstall': True, 'uninstall': True,
            'reinstall_after_removal': True, 'training_records_preserved': True,
            'backup_and_settings_preserved': True, 'installed_payload_removed': True,
            'exercise_count_preserved': count, 'different_version_upgrade_tested': False,
            'qa_workspace_only': True, 'normal_user_data_touched': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installer', type=Path)
    parser.add_argument('--qa-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.installer, args.qa_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
