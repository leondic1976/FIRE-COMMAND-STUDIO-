"""Dedicated same-origin screen web server, using the shared private runtime."""
import time
from pathlib import Path

from web.server import create_web_app, main
from .api import install
from apps.api.runtime_settings import SettingsError
from apps.api.process_lock import AlreadyRunning


def create_screen_app(data_directory=None, settings=None, frontend_directory=None, clock=None):
    app = create_web_app(data_directory or 'runtime/screen', settings,
                         frontend_directory or Path(__file__).parent / 'dist')
    anchor_wall, anchor_monotonic = time.time(), time.monotonic()
    install(app, clock or (lambda: anchor_wall + time.monotonic() - anchor_monotonic))
    app.state.runtime_track = 'screen'
    return app


if __name__ == '__main__':
    try:
        main(app_factory=create_screen_app, default_directory='runtime/screen', default_port=8090, frontend_directory=Path(__file__).parent / 'dist')
    except (SettingsError, AlreadyRunning) as error:
        raise SystemExit(str(error)) from None
