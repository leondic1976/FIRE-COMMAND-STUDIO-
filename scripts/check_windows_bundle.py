"""Check the explicit standalone payload before producing a public release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def inspect(directory):
    directory = Path(directory).resolve()
    if not (directory / 'FIRECommandStudio.exe').is_file():
        raise ValueError('Missing standalone executable')
    files = []
    for source in sorted(directory.rglob('*')):
        if not source.is_file():
            continue
        name = source.relative_to(directory).as_posix()
        if re.search(r'(?i)(?:^|/)(?:\.env(?:\..*)?|instance\.json|studio\.db|auth_sessions|cookies)(?:/|$)', name) or source.suffix.lower() in {'.db','.sqlite','.sqlite3'}:
            raise ValueError('Forbidden runtime payload: ' + name)
        with source.open('rb') as stream:
            if stream.read(16) == b'SQLite format 3\x00':
                raise ValueError('Database content in payload: ' + name)
        if source.suffix in {'.txt','.json','.js','.html','.css'}:
            data = source.read_bytes()
            if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-proj-[A-Za-z0-9_-]{20,}', data):
                raise ValueError('Credential pattern in payload: ' + name)
        with source.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        files.append({'path':name,'bytes':source.stat().st_size,'sha256':digest})
    required = ['_internal/dist/index.html','_internal/notices/THIRD_PARTY_NOTICES.txt','_internal/notices/DEPENDENCY_INVENTORY.json']
    for name in required:
        if not (directory / name).is_file():
            raise ValueError('Missing packaged resource: ' + name)
    return {'files':files,'bytes':sum(file['bytes'] for file in files),'forbidden_runtime_files_found':False,
            'python_version':sys.version.split()[0],'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'files':len(result['files']),'bytes':result['bytes'],'forbidden_runtime_files_found':False}))
