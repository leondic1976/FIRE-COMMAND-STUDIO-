import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from sqlalchemy import select, delete
from .storage import auth_tokens, accounts

PERMISSIONS = {
    "admin": {"edit", "control", "evaluate", "participate", "view", "export", "audit"},
    "facilitator": {"edit", "control", "evaluate", "participate", "view", "export"},
    "evaluator": {"evaluate", "view", "export"},
    "participant": {"participate", "view"},
    "board": {"view"}, "observer": {"view"},
}


def password_hash(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=5, maxmem=64*1024*1024)
    return f"scrypt$16384$8$5${salt.hex()}${key.hex()}"


def password_valid(password, hashed):
    try:
        if hashed.startswith("scrypt$"):
            kind,n,r,p,salt,expected = hashed.split("$")
            if (int(n),int(r),int(p)) != (16384,8,5):
                return False
            parallelism = 5
        else:
            salt,expected = hashed.split(":")
            parallelism = 1  # Legacy hashes are upgraded after a successful login.
        if len(salt) != 32 or len(expected) != 128:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=parallelism, maxmem=64*1024*1024).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError,TypeError):
        return False


def issue_token(store, identity):
    token = secrets.token_urlsafe(40)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    with store.engine.begin() as conn:
        conn.execute(auth_tokens.insert().values(token_hash=hashlib.sha256(token.encode()).hexdigest(), identity=identity, expires_at=expiry))
    return token


def resolve_token(store, token):
    if not token:
        raise HTTPException(401, "로그인이 필요합니다.")
    with store.engine.connect() as conn:
        row = conn.execute(select(auth_tokens).where(auth_tokens.c.token_hash == hashlib.sha256(token.encode()).hexdigest())).mappings().first()
    if not row or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(401, "세션이 만료되었거나 철회되었습니다.")
    return row["identity"]


def identity(request: Request):
    return resolve_token(request.app.state.store, request.cookies.get("studio_session"))


def require(user, permission):
    if permission not in PERMISSIONS.get(user["role"], set()):
        raise HTTPException(403, "이 작업에 필요한 권한이 없습니다.")


def revoke(store, token):
    if token:
        with store.engine.begin() as conn:
            conn.execute(delete(auth_tokens).where(auth_tokens.c.token_hash == hashlib.sha256(token.encode()).hexdigest()))


def login_password(store, org, username, password):
    with store.engine.connect() as conn:
        row = conn.execute(select(accounts).where((accounts.c.organization_id == org) & (accounts.c.username == username))).mappings().first()
    dummy = "scrypt$16384$8$5$00000000000000000000000000000000$" + "0" * 128
    ok = password_valid(password, row["password_hash"] if row else dummy)
    if not row or not ok:
        raise HTTPException(401, "기관/계정 또는 비밀번호가 올바르지 않습니다.")
    if not row["password_hash"].startswith("scrypt$"):
        with store.engine.begin() as conn:
            conn.execute(accounts.update().where((accounts.c.organization_id == org) & (accounts.c.username == username)).values(password_hash=password_hash(password)))
    return row["identity"]
