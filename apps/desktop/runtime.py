"""Loopback-only service with per-user storage and an exclusive instance lock."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import secrets
import socket
import sqlite3
import threading
import time
from contextlib import closing
from uuid import uuid4
from urllib.error import URLError
from urllib.request import Request, urlopen

from . import APPLICATION_ID, VERSION

SETTINGS_KEYS = {'EXTERNAL_DATA_APPROVED','EXTERNAL_DATA_APPROVAL_REF','DATA_GOV_BUILDING_KEY','KMA_SERVICE_KEY','DATA_GOV_HYDRANT_KEY','HYDRANT_DATASET_PATH','HYDRANT_CATALOG_URL','VITE_KAKAO_MAPS_APPROVED','VITE_KAKAO_JAVASCRIPT_KEY','ASSET_SCAN_APPROVED','ASSET_SCAN_APPROVAL_REF','CLAMD_PORT','MEDIA_PROCESSING_APPROVED','MEDIA_PROCESSING_APPROVAL_REF','MEDIA_HOST_ISOLATION_CONFIRMED','MEDIA_TOOL_MANIFEST','MEDIA_TOOL_MANIFEST_SHA256','IFC_CONVERSION_APPROVED','IFC_CONVERSION_APPROVAL_REF','IFC_OFFLINE_HOST_CONFIRMED','IFC_TOOL_MANIFEST','IFC_TOOL_MANIFEST_SHA256'}


class AlreadyRunning(RuntimeError):
    pass


def load_settings(directory):
    """Explicit private user settings; authority/secret values are never bundled."""
    from dotenv import dotenv_values
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    settings = directory / 'settings.env'
    if not settings.exists():
        settings.write_text('# 승인된 기관 설정만 입력하세요. 이 파일을 Git/채팅에 넣지 마세요.\n'
                            'ASSET_SCAN_APPROVED=false\nASSET_SCAN_APPROVAL_REF=\nCLAMD_PORT=3310\n'
                            'EXTERNAL_DATA_APPROVED=false\nEXTERNAL_DATA_APPROVAL_REF=\n'
                            'IFC_CONVERSION_APPROVED=false\nIFC_CONVERSION_APPROVAL_REF=\n'
                            'IFC_OFFLINE_HOST_CONFIRMED=false\nIFC_TOOL_MANIFEST=\nIFC_TOOL_MANIFEST_SHA256=\n'
                            'MEDIA_PROCESSING_APPROVED=false\nMEDIA_PROCESSING_APPROVAL_REF=\n'
                            'MEDIA_HOST_ISOLATION_CONFIRMED=false\nMEDIA_TOOL_MANIFEST=\nMEDIA_TOOL_MANIFEST_SHA256=\n', encoding='utf-8')
    for key, value in dotenv_values(settings).items():
        if key in SETTINGS_KEYS and value is not None:
            os.environ[key] = value
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'


def data_directory(override=None):
    base = Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'FIRECommandStudio'
    result = base.expanduser().resolve()
    if result == Path(result.anchor):
        raise ValueError('사용자 데이터 폴더를 지정하세요.')
    return result


def storage_id(directory):
    return hashlib.sha256(str(Path(directory).resolve()).casefold().encode()).hexdigest()[:24]


class InstanceLock:
    def __init__(self, directory):
        self.path = Path(directory) / 'instance.lock'
        self.stream = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open('a+b')
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise AlreadyRunning('같은 저장소의 스튜디오가 이미 실행 중입니다.') from None
        self.stream = stream

    def release(self):
        if self.stream is None:
            return
        stream, self.stream = self.stream, None
        try:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def _local_json(url, *, method='GET', token=None):
    headers = {'X-Desktop-Key': token} if token else {}
    request = Request(url, method=method, headers=headers, data=b'' if method == 'POST' else None)
    # Never use an ambient proxy for loopback or expose launch credentials there.
    from urllib.request import ProxyHandler, build_opener
    with build_opener(ProxyHandler({})).open(request, timeout=2) as response:
        return json.load(response)


def running_instance(directory):
    try:
        record = json.loads((Path(directory) / 'instance.json').read_text(encoding='utf-8'))
        port = record['port']
        if type(port) is not int or not 1 <= port <= 65535:
            return None
        url = f'http://127.0.0.1:{port}'
        state = _local_json(url + '/_desktop/status')
        if state.get('application') != APPLICATION_ID or state.get('storage_id') != storage_id(directory):
            return None
        return {'url': url, 'record': record, 'state': state}
    except (OSError, URLError, ValueError, KeyError, TypeError):
        return None


def stop_instance(directory):
    existing = running_instance(directory)
    if not existing:
        return False
    token = existing['record'].get('stop_key')
    if not isinstance(token, str) or len(token) != 64:
        return False
    return _local_json(existing['url'] + '/_desktop/shutdown', method='POST', token=token).get('stopping') is True


class DesktopService:
    def __init__(self, directory=None, preferred_port=8765):
        self.directory = data_directory(directory)
        self.preferred_port = preferred_port
        self.lock = InstanceLock(self.directory)
        self.server = None
        self.thread = None
        self.socket = None
        self.url = None
        self.failure = None
        self._stop_key = secrets.token_hex(32)

    def start(self):
        if type(self.preferred_port) is not int or not 0 <= self.preferred_port <= 65535:
            raise ValueError('유효한 포트가 필요합니다.')
        self.lock.acquire()
        try:
            self._start()
            return self.url
        except BaseException:
            self.stop()
            raise

    def _start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        for folder in ['storage', 'backups']:
            (self.directory / folder).mkdir(exist_ok=True)
        # Explicit settings only. No source-tree .env or developer runtime is used.
        load_settings(self.directory)
        os.environ['TRAINING_MODE'] = 'demo'
        os.environ['COOKIE_SECURE'] = 'false'
        os.environ['AI_PROVIDER'] = 'disabled'
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(('127.0.0.1', self.preferred_port))
        except OSError:
            listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        listener.setblocking(False)
        self.socket = listener
        port = listener.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}'
        os.environ['ALLOWED_ORIGINS'] = f'{self.url},http://localhost:{port}'
        database = self.directory / 'storage' / 'studio.db'
        database_url = 'sqlite:///' + database.as_posix()
        os.environ['DATABASE_URL'] = database_url
        from apps.api.application import create_app
        from fastapi import Header, HTTPException
        import uvicorn
        app = create_app(db_url=database_url, demo_mode=True)
        self.app = app
        public_map_key = os.environ.get('VITE_KAKAO_JAVASCRIPT_KEY', '')
        map_approved = os.environ.get('VITE_KAKAO_MAPS_APPROVED') == 'true' and re.fullmatch('[a-fA-F0-9]{32}', public_map_key) is not None

        @app.get('/_desktop/status')
        def desktop_status():
            return {'application': APPLICATION_ID, 'version': VERSION, 'storage_id': storage_id(self.directory), 'loopback_only': True}

        @app.get('/_desktop/map-config')
        def desktop_map_config():
            return {'approved': map_approved, 'public_key': public_map_key if map_approved else ''}

        @app.post('/_desktop/shutdown')
        def desktop_shutdown(x_desktop_key: str | None = Header(None)):
            if not x_desktop_key or not hmac.compare_digest(x_desktop_key, self._stop_key):
                raise HTTPException(403, '종료 권한이 없습니다.')
            self.server.should_exit = True
            return {'stopping': True}

        # create_app already includes the SPA fallback. Desktop control routes
        # must precede it, otherwise a status request receives index.html.
        controls = [route for route in app.router.routes if getattr(route, 'path', '').startswith('/_desktop/')]
        app.router.routes[:] = controls + [route for route in app.router.routes if route not in controls]
        self.server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_config=None, access_log=False, loop='asyncio', ws='websockets-sansio'))

        def serve():
            try:
                self.server.run(sockets=[listener])
            except BaseException as exc:
                # Operational class only: no payloads, cookie values or secrets.
                self.failure = type(exc).__name__

        self.thread = threading.Thread(target=serve, name='fire-command-local', daemon=False)
        self.thread.start()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if not self.thread.is_alive():
                raise RuntimeError('로컬 스튜디오를 실행하지 못했습니다.')
            if self.server.started:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('로컬 스튜디오 준비 시간이 초과됐습니다.')
        temporary = self.directory / 'instance.json.tmp'
        temporary.write_text(json.dumps({'application': APPLICATION_ID, 'version': VERSION, 'pid': os.getpid(), 'port': port, 'stop_key': self._stop_key}), encoding='utf-8')
        temporary.replace(self.directory / 'instance.json')

    def stop(self):
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                raise RuntimeError('훈련 기록 정리가 끝나지 않았습니다. 잠시 후 다시 종료하세요.')
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        # Only the owner may clear its descriptor; never erase a live peer's file.
        if self.lock.stream is not None:
            (self.directory / 'instance.json').unlink(missing_ok=True)
            if hasattr(self, 'app'):
                self.app.state.store.engine.dispose()
        self.lock.release()

    def create_backup(self, destination):
        from scripts.backup_restore import backup
        return backup(self.directory / 'storage' / 'studio.db', Path(destination))

    def restore_backup(self, source):
        """Validate/stage first; preserve a consistent current backup before swap."""
        from scripts.backup_restore import restore
        source = Path(source).resolve()
        live = self.directory / 'storage' / 'studio.db'
        if source == live.resolve() or not source.is_file() or not 0 < source.stat().st_size <= 2 * 1024**3:
            raise ValueError('별도의2GiB 이하 스튜디오 백업을 선택하세요.')
        manifest_file = source.with_suffix(source.suffix + '.manifest.json')
        if not manifest_file.is_file() or manifest_file.stat().st_size > 1024 * 1024:
            raise ValueError('백업과 함께 생성된 manifest 파일이 필요합니다.')
        identifier = uuid4().hex
        staged = live.parent / ('restore-' + identifier + '.db')
        previous = self.directory / 'backups' / ('before-restore-' + identifier + '.db')
        swapped = False
        try:
            restored = restore(source, staged)
            self.stop()
            self.create_backup(previous)
            with closing(sqlite3.connect(live)) as connection:
                if connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] != 0:
                    raise RuntimeError('기존 기록을 사용 중인 작업이 있어 복원을 보류합니다.')
            for suffix in ['-wal', '-shm']:
                live.with_name(live.name + suffix).unlink(missing_ok=True)
            staged.replace(live)
            swapped = True
            self._stop_key = secrets.token_hex(32)
            self.start()
            receipt = {'source_sha256': restored['sha256'], 'previous_backup': previous.name, 'restored': True}
            (self.directory / 'backups' / ('restore-' + identifier + '.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            return receipt
        except BaseException:
            if self.thread is None or not self.thread.is_alive():
                if swapped:
                    rollback = live.parent / ('rollback-' + identifier + '.db')
                    restore(previous, rollback)
                    rollback.replace(live)
                    rollback.with_suffix('.db.manifest.json').unlink(missing_ok=True)
                self._stop_key = secrets.token_hex(32)
                self.start()
            raise
        finally:
            # Only invocation-owned staging files, never user-selected backups.
            staged.unlink(missing_ok=True)
            staged.with_suffix('.db.manifest.json').unlink(missing_ok=True)
