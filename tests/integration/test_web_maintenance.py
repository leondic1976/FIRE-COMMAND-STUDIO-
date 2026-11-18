import json

import pytest

from apps.api.storage import Store
from scripts.backup_restore import backup
from web.maintenance import restore_offline


def test_server_restore_preserves_a_verified_previous_backup(tmp_path):
    folder = tmp_path / 'data'
    (folder / 'storage').mkdir(parents=True)
    database = folder / 'storage/studio.db'
    store = Store('sqlite:///' + database.as_posix())
    store.create('exercise', 'synthetic-first', 'org', {'id': 'synthetic-first'})
    archive = tmp_path / 'archive.db'
    backup(database, archive)
    store.create('exercise', 'synthetic-later', 'org', {'id': 'synthetic-later'})
    store.engine.dispose()
    result = restore_offline(folder, archive, database)
    restored = Store('sqlite:///' + database.as_posix())
    previous = Store('sqlite:///' + (folder / 'backups' / result['previous_backup']).as_posix())
    try:
        assert len(restored.list('exercise', 'org')) == 1
        assert len(previous.list('exercise', 'org')) == 2
    finally:
        restored.engine.dispose()
        previous.engine.dispose()


def test_corrupted_server_backup_never_changes_current_data(tmp_path):
    folder = tmp_path / 'data'
    (folder / 'storage').mkdir(parents=True)
    database = folder / 'storage/studio.db'
    store = Store('sqlite:///' + database.as_posix())
    store.create('exercise', 'synthetic-current', 'org', {'id': 'synthetic-current'})
    archive = tmp_path / 'archive.db'
    backup(database, archive)
    store.engine.dispose()
    manifest = archive.with_suffix('.db.manifest.json')
    value = json.loads(manifest.read_text())
    value['sha256'] = '0' * 64
    manifest.write_text(json.dumps(value))
    before = database.read_bytes()
    with pytest.raises(ValueError):
        restore_offline(folder, archive, database)
    assert database.read_bytes() == before
    assert not list(database.parent.glob('restore-*'))
