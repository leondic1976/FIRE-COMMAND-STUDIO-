import pytest
from sqlalchemy import select

from apps.api.storage import Store, accounts
from scripts.manage import main


def test_duplicate_account_error_never_prints_password_or_hash(tmp_path, monkeypatch, capsys):
    password = 'synthetic-CLI-password-only'
    monkeypatch.setattr('scripts.manage.getpass.getpass', lambda _: password)
    url = 'sqlite:///' + (tmp_path / 'accounts.db').as_posix()
    arguments = ['create-account', '--organization', 'synthetic-org', '--username', 'synthetic-admin', '--role', 'admin']
    main(arguments, database_url=url)
    with pytest.raises(SystemExit) as error:
        main(arguments, database_url=url)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert password not in output.out + output.err
    assert 'scrypt$' not in output.out + output.err and 'INSERT INTO' not in output.err
    store = Store(url)
    try:
        with store.engine.connect() as connection:
            assert len(connection.execute(select(accounts)).all()) == 1
    finally:
        store.engine.dispose()
