import sqlite3
from pathlib import Path
import pytest
from scripts.backup_restore import backup,restore
from tests.conftest import release_n


def test_ac35_backup_restore_includes_wal_and_events(client,session_id,app,tmp_path):
    release_n(client,session_id,3)
    source=Path(app.state.store.url.removeprefix('sqlite:///'))
    archive=tmp_path/'backup.db';target=tmp_path/'restored.db'
    manifest=backup(source,archive)
    assert manifest['schema_versions']==[1,2]
    restore(archive,target)
    with sqlite3.connect(source) as original,sqlite3.connect(target) as recovered:
        for table in ['records','session_events','audit_logs']:
            assert original.execute(f'SELECT * FROM {table}').fetchall()==recovered.execute(f'SELECT * FROM {table}').fetchall()
    with pytest.raises(ValueError):restore(archive,target)
    archive.write_bytes(archive.read_bytes()+b'corruption')
    with pytest.raises(ValueError,match='해시'):restore(archive,tmp_path/'corrupt.db')
