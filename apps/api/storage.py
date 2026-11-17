"""Transactional aggregate store. SQLite development, PostgreSQL institutional deployment."""
import copy
import hashlib
import json
import os
from pathlib import Path
from sqlalchemy import JSON, LargeBinary, Column, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, select, update, event,func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from .domain import utcnow
from . import config

metadata = MetaData()
records = Table("records", metadata,
    Column("organization_id", String(80), primary_key=True), Column("kind", String(40), primary_key=True),
    Column("id", String(80), primary_key=True), Column("version", Integer, nullable=False), Column("payload", JSON, nullable=False))
commands = Table("commands", metadata,
    Column("organization_id", String(80), primary_key=True), Column("resource", String(100), primary_key=True),
    Column("key", String(100), primary_key=True), Column("fingerprint", String(64), nullable=False), Column("response", JSON, nullable=False))
events = Table("session_events", metadata,
    Column("organization_id", String(80), primary_key=True), Column("session_id", String(80), primary_key=True),
    Column("seq", Integer, primary_key=True), Column("payload", JSON, nullable=False))
audit = Table("audit_logs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("organization_id", String(80), nullable=False),
    Column("actor_id", String(80), nullable=False), Column("action", String(100), nullable=False),
    Column("resource", String(100), nullable=False), Column("at", String(50), nullable=False))
auth_tokens = Table("auth_sessions", metadata,
    Column("token_hash", String(64), primary_key=True), Column("identity", JSON, nullable=False),
    Column("expires_at", String(50), nullable=False))
accounts = Table("accounts", metadata,
    Column("organization_id", String(80), primary_key=True), Column("username", String(80), primary_key=True),
    Column("password_hash", Text, nullable=False), Column("identity", JSON, nullable=False))
schema_versions = Table("schema_versions", metadata, Column("version", Integer, primary_key=True), Column("applied_at", String(50)))
asset_blobs = Table('asset_blobs',metadata,
    Column('organization_id',String(80),primary_key=True),Column('asset_id',String(80),primary_key=True),
    Column('original',LargeBinary,nullable=True),Column('canonical',LargeBinary,nullable=True))


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class Store:
    def __init__(self, url: str | None = None):
        url = url or os.environ.get("DATABASE_URL", "sqlite:///./runtime/studio.db")
        if url.startswith("sqlite:///./"):
            Path(url[len("sqlite:///./"):]).parent.mkdir(parents=True, exist_ok=True)
        self.url = url
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15} if url.startswith("sqlite") else {}, pool_pre_ping=True)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def configure_sqlite(conn, _):
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("PRAGMA busy_timeout=15000")
                conn.execute("PRAGMA journal_mode=WAL")
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            applied = conn.execute(select(schema_versions.c.version)).scalars().all()
            if not applied:
                conn.execute(schema_versions.insert().values(version=1, applied_at=utcnow()))
                applied=[1]
            if max(applied)==1:
                conn.execute(schema_versions.insert().values(version=2,applied_at=utcnow()))
            elif max(applied) != 2:
                raise RuntimeError("지원하지 않는 DB 스키마입니다. 승인된 마이그레이션 또는 백업 복구가 필요합니다.")

    @staticmethod
    def where(kind, id, org):
        return (records.c.kind == kind) & (records.c.id == id) & (records.c.organization_id == org)

    def load(self, kind, id, org):
        with self.engine.connect() as conn:
            row = conn.execute(select(records).where(self.where(kind, id, org))).mappings().first()
            if not row:
                raise HTTPException(404, "자료를 찾을 수 없습니다.")
            return copy.deepcopy(row["payload"]), row["version"]

    def list(self, kind, org):
        with self.engine.connect() as conn:
            return [copy.deepcopy(r) for r in conn.execute(select(records.c.payload).where((records.c.kind == kind) & (records.c.organization_id == org))).scalars()]

    def create(self, kind, id, org, payload, actor="system"):
        with self.engine.begin() as conn:
            try:
                conn.execute(records.insert().values(kind=kind, id=id, organization_id=org, version=1, payload=payload))
                self.log(conn, org, actor, "CREATE", f"{kind}/{id}")
            except IntegrityError:
                raise HTTPException(409, "이미 존재하는 ID입니다.")
        return payload

    def create_asset(self,id,org,payload,original,canonical,actor):
        """Metadata and private bytes commit together; no static file URL exists."""
        with self.engine.begin() as conn:
            try:
                conn.execute(records.insert().values(kind='asset',id=id,organization_id=org,version=1,payload=payload))
                conn.execute(asset_blobs.insert().values(organization_id=org,asset_id=id,original=original,canonical=canonical))
                self.log(conn,org,actor,'ASSET_INTAKE','asset/'+id)
            except IntegrityError:raise HTTPException(409,'같은 자산 수집 요청이 이미 저장됐습니다.')
        return payload

    def asset_bytes(self,id,org,original=False):
        with self.engine.connect() as conn:
            value=conn.execute(select(asset_blobs.c.original if original else asset_blobs.c.canonical).where(
                (asset_blobs.c.organization_id==org)&(asset_blobs.c.asset_id==id))).scalar_one_or_none()
        if value is None:raise HTTPException(409,'자산 콘텐츠가 없거나 검사·정규화되지 않았습니다.')
        return value

    def asset_usage(self,org):
        with self.engine.connect() as conn:
            row=conn.execute(select(func.count(asset_blobs.c.asset_id),func.sum(func.coalesce(func.length(asset_blobs.c.original),0)+func.coalesce(func.length(asset_blobs.c.canonical),0))).where(asset_blobs.c.organization_id==org)).one()
        return int(row[0]),int(row[1] or 0)

    def asset_summaries(self,org):
        fields=['id','status','kind','provenance','created_at','canonical_sha256','canonical_bytes']
        with self.engine.connect() as conn:
            rows=conn.execute(select(*[records.c.payload[key].label(key) for key in fields],records.c.version.label('state_version')).where(
                (records.c.organization_id==org)&(records.c.kind=='asset')).order_by(records.c.payload['created_at'].as_string().desc()).limit(100)).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def log(conn, org, actor, action, resource):
        conn.execute(audit.insert().values(organization_id=org, actor_id=actor, action=action, resource=resource, at=utcnow()))

    def mutate(self, kind, id, org, expected, actor, action, transform, key=None, request=None,blob_update=None):
        if expected is None:
            raise HTTPException(428, "expected_state_version이 필요합니다.")
        if key and (not 8 <= len(key) <= 100):
            raise HTTPException(400, "멱등키는 8~100자입니다.")
        resource = f"{kind}/{id}"
        fp = fingerprint({"actor": actor, "action": action, "request": request})
        with self.engine.begin() as conn:
            if key:
                prior = conn.execute(select(commands).where((commands.c.organization_id == org) & (commands.c.resource == resource) & (commands.c.key == key))).mappings().first()
                if prior:
                    if prior["fingerprint"] != fp:
                        raise HTTPException(409, "같은 멱등키에 다른 명령을 사용할 수 없습니다.")
                    return prior["response"]
            row = conn.execute(select(records).where(self.where(kind, id, org))).mappings().first()
            if not row:
                raise HTTPException(404, "자료를 찾을 수 없습니다.")
            if row["version"] != expected:
                raise HTTPException(409, "다른 변경이 반영되었습니다. 새로고침 후 다시 시도하세요.")
            payload = copy.deepcopy(row["payload"])
            old_seq = payload.get("seq", 0)
            transform(payload)
            payload["state_version"] = expected + 1
            result = conn.execute(update(records).where(self.where(kind, id, org) & (records.c.version == expected)).values(payload=payload, version=expected+1))
            if result.rowcount != 1:
                raise HTTPException(409, "동시 수정 충돌입니다.")
            if blob_update is not None:
                if kind!='asset':raise ValueError('Blob writes require an asset aggregate')
                original,canonical=blob_update
                updated=conn.execute(update(asset_blobs).where((asset_blobs.c.organization_id==org)&(asset_blobs.c.asset_id==id)).values(original=original,canonical=canonical))
                if updated.rowcount!=1:raise HTTPException(409,'자산 바이트 저장본이 없습니다.')
            if kind == "session":
                for entry in payload.get("log", []):
                    if entry["seq"] > old_seq:
                        conn.execute(events.insert().values(organization_id=org, session_id=id, seq=entry["seq"], payload=entry))
            self.log(conn, org, actor, action, resource)
            response = {"state_version": expected+1, "seq": payload.get("seq", 0), "id": id}
            if key:
                conn.execute(commands.insert().values(organization_id=org, resource=resource, key=key, fingerprint=fp, response=response))
            return response
