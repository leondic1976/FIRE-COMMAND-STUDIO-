from pathlib import Path
import pytest
from apps.api.runtime_settings import SettingsError
from web.server import main


def test_screen_private_directory_is_checked_before_any_configuration_write(tmp_path, monkeypatch):
    public = tmp_path / 'screen-public'
    forbidden = public / 'assets/private'
    monkeypatch.setattr('sys.argv', ['screen', '--init', '--data-dir', str(forbidden)])
    with pytest.raises(SettingsError):
        main(default_port=8090, frontend_directory=public)
    assert not forbidden.exists()
