"""Offline server maintenance. Caller must hold the shared data-directory lock."""
from contextlib import closing
from pathlib import Path
import sqlite3
from uuid import uuid4

from apps.api.storage import Store
from scripts.backup_restore import backup, restore


def sqlite_path(store):
    if store.engine.url.get_backend_name() != 'sqlite' or store.engine.url.database in (None, ':memory:'):
        raise ValueError('이 명령은 파일 SQLite 전용입니다. PostgreSQL은 기관 DB 백업·복구 절차를 사용하세요.')
    return Path(store.engine.url.database).resolve()


def checkpoint(path):
    with closing(sqlite3.connect(path)) as connection:
        if connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] != 0:
            raise RuntimeError('사용 중인 기록이 있습니다. 모든 서비스·관리 작업을 중지하세요.')


def restore_offline(directory, source, live):
    source, live, directory = Path(source).resolve(), Path(live).resolve(), Path(directory).resolve()
    manifest = source.with_suffix(source.suffix + '.manifest.json')
    if source == live or not source.is_file() or not 0 < source.stat().st_size <= 2 * 1024**3:
        raise ValueError('별도의 2GiB 이하 백업 파일을 선택하세요.')
    if not manifest.is_file() or manifest.stat().st_size > 1024 * 1024:
        raise ValueError('백업과 함께 저장한 manifest 파일이 필요합니다.')
    identifier = uuid4().hex
    staged = live.parent / ('restore-' + identifier + '.db')
    previous = directory / 'backups' / ('before-restore-' + identifier + '.db')
    try:
        restore(source, staged)
        check = Store('sqlite:///' + staged.as_posix())
        check.engine.dispose()
        checkpoint(staged)
        backup(live, previous)
        checkpoint(live)
        for suffix in ['-wal', '-shm']:
            live.with_name(live.name + suffix).unlink(missing_ok=True)
        staged.replace(live)
        return {'restored': True, 'schema_version': 2, 'previous_backup': previous.name}
    finally:
        for file in [staged, staged.with_suffix('.db.manifest.json'), staged.with_name(staged.name + '-wal'), staged.with_name(staged.name + '-shm')]:
            file.unlink(missing_ok=True)
