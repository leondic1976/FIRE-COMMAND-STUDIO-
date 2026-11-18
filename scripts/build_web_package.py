"""Package explicit web-server resources; exclude private configuration and data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

from apps.version import VERSION


def build(root, destination, *, allow_dirty=False):
    root = Path(root).resolve()
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
    if status.strip() and not allow_dirty:
        raise ValueError('Commit the verified source before producing a release package')
    required = ['requirements.txt', 'package.json', 'package-lock.json', 'apps/version.py',
        'web/README.md', 'web/package.json', 'web/index.html', 'web/tsconfig.json', 'web/vite.config.ts',
        'web/Dockerfile', 'web/compose.yaml', 'web/Caddyfile', '.dockerignore',
        'docs/WEB_DEPLOYMENT.md', 'scripts/manage.py', 'scripts/backup_restore.py',
        'scripts/convert_ifc.py', 'scripts/prepare_ifc_tool.py', 'scripts/prepare_media_tool.py',
        'scripts/desktop_notices.py', 'scripts/dependency_inventory.py', 'scripts/audit_python_dependencies.py']
    sources = {name: root / name for name in required}
    for path in (root / 'web').glob('*.py'):
        sources[path.relative_to(root).as_posix()] = path
    for folder, pattern in [('apps/api', '*.py'), ('apps/web', '*'), ('data', '*.json'), ('packages', '*'),
                            ('web/src', '*'), ('web/config', '*.json'), ('web/dist', '*')]:
        for path in (root / folder).rglob(pattern):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            sources[path.relative_to(root).as_posix()] = path
    for name in ['THIRD_PARTY_NOTICES.txt', 'DEPENDENCY_INVENTORY.json']:
        sources['notices/' + name] = root / 'runtime/desktop-notices' / name
    if not (root / 'web/dist/index.html').is_file():
        raise ValueError('Build the web workspace before packaging')
    files = []
    forbidden = re.compile(r'(?i)(?:^|/)(?:settings\.json|settings\.previous\.json|server\.json|server\.previous\.json|instance\.json|\.env(?:\..*)?|cookies)(?:/|$)')
    for name, path in sorted(sources.items()):
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or redirected release resource: ' + name)
        if forbidden.search(name) or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3'}:
            raise ValueError('Private runtime file in release: ' + name)
        data = path.read_bytes()
        if data.startswith(b'SQLite format 3\0') or re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-proj-[A-Za-z0-9_-]{20,}', data):
            raise ValueError('Private content in release: ' + name)
        files.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'application': 'FIRE-COMMAND STUDIO', 'version': VERSION,
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'source_dirty': bool(status.strip()), 'track': 'web-server', 'configuration_schema': 1,
        'user_data_included': False, 'files': files}
    destination = Path(destination).resolve()
    if destination == root or destination.is_relative_to(root / 'web/dist'):
        raise ValueError('Use a separate output directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(sources[item['path']], item['path'])
        archive.writestr('SERVER_PACKAGE.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    destination.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'version': VERSION, 'files': len(files), 'bytes': destination.stat().st_size,
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'source_dirty': manifest['source_dirty']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-dirty', action='store_true', help='QA candidate only, never a release')
    args = parser.parse_args()
    print(json.dumps(build(Path.cwd(), args.output, allow_dirty=args.allow_dirty)))
