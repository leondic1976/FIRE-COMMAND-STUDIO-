"""Same-origin web server with explicit JSON configuration and private storage."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.api.runtime_settings import SettingsError, atomic_json, load_settings, runtime_environment, strict_json
from apps.api.process_lock import AlreadyRunning, InstanceLock


class WebSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: int = Field(default=1, ge=1, le=1)
    mode: Literal['demo', 'production'] = 'demo'
    host: Literal['127.0.0.1', 'localhost', '::1', '0.0.0.0', '::'] = '127.0.0.1'
    port: int = Field(default=8080, ge=1, le=65535)
    public_url: str = 'http://127.0.0.1:8080'
    development_origins: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode='after')
    def safe_network(self):
        if self.mode not in ('demo', 'production') or self.host not in ('127.0.0.1', 'localhost', '::1', '0.0.0.0', '::'):
            raise ValueError('Unsupported server mode or binding')
        url = urlsplit(self.public_url)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise ValueError('A root HTTP(S) origin without credentials is required')
        _ = url.port
        if self.mode == 'production' and (url.scheme != 'https' or self.development_origins):
            raise ValueError('Production requires HTTPS and no development origins')
        if self.mode == 'demo' and (self.host not in ('127.0.0.1', 'localhost', '::1') or not loopback(url.hostname)):
            raise ValueError('Demo mode is limited to the local computer')
        for origin in self.development_origins:
            parsed = urlsplit(origin)
            if parsed.scheme != 'http' or not loopback(parsed.hostname) or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                raise ValueError('Development origins must be exact local origins')
            _ = parsed.port
        self.public_url = canonical_origin(self.public_url)
        self.development_origins = [canonical_origin(origin) for origin in self.development_origins]
        return self


def loopback(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def canonical_origin(value):
    parsed = urlsplit(value)
    host = parsed.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    port = parsed.port
    suffix = ':' + str(port) if port and port != (443 if parsed.scheme == 'https' else 80) else ''
    return parsed.scheme.lower() + '://' + host + suffix


def private_directory(value, frontend=None):
    directory = Path(value).expanduser().resolve()
    public = Path(frontend or Path(__file__).resolve().parent / 'dist').resolve()
    if directory == Path(directory.anchor) or directory.is_relative_to(public) or public.is_relative_to(directory):
        raise SettingsError('웹 정적 자원과 분리된 비공개 데이터 폴더가 필요합니다.')
    return directory


def read_server_settings(directory, overrides=None):
    directory = private_directory(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / 'server.json'
    original = strict_json(path.read_bytes()) if path.exists() else {}
    data = dict(original) if isinstance(original, dict) else original
    if not isinstance(data, dict):
        raise SettingsError('서버 설정 JSON 객체가 필요합니다.')
    data.update(overrides or {})
    if overrides and 'public_url' not in overrides and {'host', 'port'} & overrides.keys() and data.get('mode', 'demo') == 'demo':
        host = data.get('host', '127.0.0.1')
        data['public_url'] = f'http://[{host}]:{data.get("port", 8080)}' if ':' in host else f'http://{host}:{data.get("port", 8080)}'
    try:
        settings = WebSettings.model_validate(data)
    except (ValidationError, ValueError):
        raise SettingsError('서버 설정의 버전·주소·HTTPS·운영 모드를 확인하세요.') from None
    if not path.exists() or original != settings.model_dump():
        if path.exists():
            atomic_json(path.with_name('server.previous.json'), original)
        atomic_json(path, settings.model_dump())
    return settings


def create_web_app(data_directory=None, settings=None, frontend_directory=None):
    frontend = Path(frontend_directory or Path(__file__).resolve().parent / 'dist').resolve()
    directory = private_directory(data_directory or os.getenv('STUDIO_DATA_DIR', 'runtime/web-server'), frontend)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings = WebSettings.model_validate(settings.model_dump()) if settings else read_server_settings(directory)
    origins = {settings.public_url.rstrip('/'), *(origin.rstrip('/') for origin in settings.development_origins)}
    storage = directory / 'storage'
    storage.mkdir(exist_ok=True)
    (directory / 'backups').mkdir(exist_ok=True)
    with runtime_environment(load_settings(directory), {'TRAINING_MODE': settings.mode,
        'COOKIE_SECURE': 'true' if settings.mode == 'production' else 'false',
        'AI_PROVIDER': 'disabled', 'ALLOWED_ORIGINS': ','.join(sorted(origins))}, environment_precedence=True):
        database = os.getenv('DATABASE_URL') or 'sqlite:///' + (storage / 'studio.db').as_posix()
        from apps.api.application import create_app
        app = create_app(database, demo_mode=settings.mode == 'demo', web_directory=frontend)
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    hosts = {urlsplit(settings.public_url).hostname, '127.0.0.1', 'localhost', '[::1]'}
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(host for host in hosts if host))
    app.state.runtime_track = 'web'
    app.state.runtime_directory = directory
    app.state.runtime_settings = settings.model_copy(deep=True)
    app.state.frontend_directory = frontend
    return app


def main(app_factory=create_web_app, default_directory='runtime/web-server', default_port=None, frontend_directory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('STUDIO_DATA_DIR', default_directory)))
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--public-url')
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--allow-development-origin', action='append')
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument('--init', action='store_true', help='JSON 설정만 생성/검증하고 종료')
    operations.add_argument('--check', action='store_true', help='설정·프론트엔드·DB 준비 여부 확인')
    operations.add_argument('--create-account', action='store_true', help='숨김 비밀번호 입력으로 웹 계정 생성')
    operations.add_argument('--backup-to', type=Path, help='일관된 DB 백업과 manifest 저장')
    operations.add_argument('--restore-from', type=Path, help='서버를 중지한 상태에서 검증된 DB 복원')
    parser.add_argument('--organization')
    parser.add_argument('--username')
    parser.add_argument('--role', choices=['admin', 'facilitator', 'evaluator', 'participant', 'board', 'observer'], default='admin')
    parser.add_argument('--person-id')
    args = parser.parse_args()
    private_directory(args.data_dir, Path(frontend_directory or Path(__file__).parent / 'dist'))
    overrides = {name: value for name, value in vars(args).items() if name in ('host', 'port', 'public_url') and value is not None}
    if default_port is not None and 'port' not in overrides and not (args.data_dir / 'server.json').exists():
        overrides['port'] = default_port
    if args.production:
        overrides['mode'] = 'production'
    if args.allow_development_origin:
        overrides['development_origins'] = args.allow_development_origin
    settings = read_server_settings(args.data_dir, overrides)
    if args.init:
        load_settings(args.data_dir)
        print(json.dumps({'configured': True, 'schema_version': 1, 'mode': settings.mode}))
        return
    lock = InstanceLock(private_directory(args.data_dir))
    app = None
    try:
        if not (args.check or args.create_account or args.backup_to):
            lock.acquire()
        app = app_factory(args.data_dir, settings)
        if args.backup_to or args.restore_from:
            from .maintenance import restore_offline, sqlite_path
            from scripts.backup_restore import backup
            database = sqlite_path(app.state.store)
            app.state.store.engine.dispose()
            result = backup(database, args.backup_to) if args.backup_to else restore_offline(args.data_dir, args.restore_from, database)
            print(json.dumps({'backup_created': True, 'schema_versions': result['schema_versions']} if args.backup_to else result))
            return
        if args.create_account:
            if not args.organization or not args.username:
                parser.error('--create-account에는 --organization과 --username이 필요합니다.')
            from scripts.manage import main as manage
            arguments = ['create-account', '--organization', args.organization, '--username', args.username, '--role', args.role]
            if args.person_id:
                arguments += ['--person-id', args.person_id]
            manage(arguments, database_url=app.state.store.url)
            return
        if args.check:
            print(json.dumps({'configured': True, 'mode': settings.mode, 'frontend_built': (app.state.frontend_directory / 'index.html').is_file(), 'schema_version': 2}))
            return
        import uvicorn
        uvicorn.run(app, host=settings.host, port=settings.port, workers=1, proxy_headers=False, access_log=False)
    finally:
        if app is not None:
            app.state.store.engine.dispose()
        lock.release()


if __name__ == '__main__':
    try:
        main()
    except (SettingsError, AlreadyRunning) as error:
        raise SystemExit(str(error)) from None
