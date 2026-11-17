"""Consistent SQLite backup and verified restore into a NEW file; never overwrite live data."""
import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def backup(source, destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if not source.is_file() or source==destination or destination.exists():
        raise ValueError('원본 파일과 존재하지 않는 별도 백업 경로를 지정하세요.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # sqlite backup() includes committed WAL contents, unlike an ordinary file copy.
    with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True)) as src,closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('백업 무결성 검사 실패')
        versions=dst.execute('SELECT version FROM schema_versions').fetchall()
    manifest={'schema_versions':[v[0] for v in versions],'sha256':digest(destination),'created_at':datetime.now(timezone.utc).isoformat(),'format':'SQLITE_CONSISTENT_BACKUP'}
    destination.with_suffix(destination.suffix+'.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def restore(source,destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    manifest=json.loads(source.with_suffix(source.suffix+'.manifest.json').read_text(encoding='utf-8'))
    if digest(source)!=manifest['sha256']:
        raise ValueError('백업 해시 불일치 — 복구 중단')
    if manifest['schema_versions'] not in ([1],[1,2]):
        raise ValueError('지원하지 않는 스키마 버전 — 마이그레이션 확인 필요')
    return backup(source,destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['backup','restore'])
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    print(json.dumps((backup if args.operation=='backup' else restore)(args.source,args.destination),ensure_ascii=False,indent=2))
